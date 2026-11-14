"""RGBA PNG overlay endpoint (SRS §7.1 layers row, §8.1)."""
from __future__ import annotations

import struct
import zlib

import pytest

from app.data_store import store
from app.routers.layers import ALLOWED_LAYERS, _TRANSPARENT_PNG
from conftest import AOI_IDS

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _decode_png(data: bytes) -> dict:
    """Minimal PNG validator: checks signature, every chunk CRC, and that IDAT inflates."""
    assert data[:8] == PNG_SIG, "bad PNG signature"
    i, idat, info = 8, b"", {}
    while i < len(data):
        assert i + 8 <= len(data), "truncated chunk header"
        (length,) = struct.unpack(">I", data[i:i + 4])
        ctype = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + length]
        assert i + 12 + length <= len(data), f"truncated {ctype!r} chunk"
        (crc,) = struct.unpack(">I", data[i + 8 + length:i + 12 + length])
        assert crc == zlib.crc32(ctype + body) & 0xFFFFFFFF, f"bad CRC in {ctype!r}"
        if ctype == b"IHDR":
            w, h, depth, color = struct.unpack(">IIBB", body[:10])
            info.update(width=w, height=h, depth=depth, color=color)
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        i += 12 + length
    raw = zlib.decompress(idat)  # raises if the stream is corrupt
    info["raw"] = raw
    return info


def test_placeholder_png_is_a_valid_decodable_image():
    """Regression: a corrupt placeholder makes MapLibre log 'source image could not be decoded'."""
    info = _decode_png(_TRANSPARENT_PNG)
    assert (info["width"], info["height"]) == (1, 1)
    assert info["color"] == 6, "placeholder must be RGBA (color type 6)"
    assert info["raw"][-1] == 0, "placeholder pixel must be fully transparent (alpha=0)"


@pytest.mark.parametrize("aoi_id", AOI_IDS)
@pytest.mark.parametrize("layer_id", sorted(ALLOWED_LAYERS))
def test_every_allowed_layer_returns_png(client, aoi_id, layer_id):
    res = client.get(f"/api/v1/layers/{aoi_id}/{layer_id}.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == PNG_SIG
    assert res.headers["x-geosar-fallback"] in {"true", "false"}


def test_unknown_layer_returns_placeholder_with_warning(client):
    res = client.get("/api/v1/layers/aoi_assam_majuli/evil_layer.png")
    assert res.status_code == 200
    assert res.headers["x-geosar-fallback"] == "true"
    assert res.headers["x-geosar-warning"] == "unknown_layer:evil_layer"


def test_missing_overlay_returns_placeholder_with_warning(client, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: tmp_path)
    res = client.get("/api/v1/layers/aoi_assam_majuli/open_water.png?date=2026-07-22")
    assert res.headers["x-geosar-fallback"] == "true"
    assert res.headers["x-geosar-warning"] == "overlay_not_found:open_water_2026-07-22.png"


def test_existing_dated_overlay_is_served_with_cache_header(client, monkeypatch, tmp_path):
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    payload = PNG_SIG + b"fake-overlay-bytes"
    (overlays / "flooded_veg_2026-07-22.png").write_bytes(payload)
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: tmp_path)

    res = client.get("/api/v1/layers/aoi_assam_majuli/flooded_veg.png?date=2026-07-22")
    assert res.content == payload
    assert res.headers["x-geosar-fallback"] == "false"
    assert "max-age" in res.headers["cache-control"]


def test_undated_overlay_is_served(client, monkeypatch, tmp_path):
    (tmp_path / "overlays").mkdir()
    (tmp_path / "overlays" / "hydroperiod.png").write_bytes(PNG_SIG + b"h")
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: tmp_path)
    res = client.get("/api/v1/layers/aoi_assam_majuli/hydroperiod.png")
    assert res.headers["x-geosar-fallback"] == "false"


@pytest.mark.parametrize("date", [
    "x/../../../secret",
    "x\\..\\..\\..\\secret",
    "../../../secret",
])
def test_date_param_cannot_escape_overlay_directory(client, monkeypatch, tmp_path, date):
    """Security: ?date= must not allow reading files outside data_store/<aoi>/overlays."""
    aoi_dir = tmp_path / "aoi"
    (aoi_dir / "overlays").mkdir(parents=True)
    secret = PNG_SIG + b"SECRET-FILE-OUTSIDE-OVERLAYS"
    (tmp_path / "secret.png").write_bytes(secret)
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: aoi_dir)

    res = client.get("/api/v1/layers/aoi_assam_majuli/open_water.png", params={"date": date})
    assert res.status_code == 200
    assert b"SECRET-FILE-OUTSIDE-OVERLAYS" not in res.content
    assert res.headers["x-geosar-fallback"] == "true"


def test_unknown_aoi_layer_request_does_not_500(client):
    res = client.get("/api/v1/layers/not_an_aoi/open_water.png")
    assert res.status_code == 200
    assert res.headers["x-geosar-fallback"] == "true"
