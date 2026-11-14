"""Serves georeferenced RGBA PNG overlays for MapLibre image sources (SRS §7.1).

Lookup order for ?date=YYYY-MM-DD: <layer>_<date>.png -> <layer>.png (season layers
such as hydroperiod / gmm_regimes / jrc_anomaly have no per-date file) -> a clean
transparent 1x1 placeholder PNG with a warning header instead of a 404, so the map
keeps rendering.
"""
from __future__ import annotations

import base64
import re

from fastapi import APIRouter
from fastapi.responses import Response

from ..data_store import store

router = APIRouter(tags=["layers"])

# Valid 1x1 fully transparent RGBA PNG.
_TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNgYGBgAAAABQABeqhXUAAAAABJRU5ErkJggg=="
)

ALLOWED_LAYERS = {"open_water", "flooded_veg", "hydroperiod", "gmm_regimes", "jrc_anomaly", "context_layers"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AOI_RE = re.compile(r"^[a-z0-9_]+$")


def _placeholder(warning: str) -> Response:
    return Response(
        content=_TRANSPARENT_PNG,
        media_type="image/png",
        headers={"X-GeoSAR-Warning": warning, "X-GeoSAR-Fallback": "true"},
    )


@router.get("/layers/{aoi_id}/{layer_id}.png")
def layer_png(aoi_id: str, layer_id: str, date: str | None = None) -> Response:
    if layer_id not in ALLOWED_LAYERS:
        return _placeholder(f"unknown_layer:{layer_id}")
    if not _AOI_RE.match(aoi_id):
        return _placeholder("invalid_aoi")
    if date is not None and not _DATE_RE.match(date):
        return _placeholder("invalid_date")  # also blocks path traversal via ?date=

    overlays = store.aoi_dir(aoi_id) / "overlays"
    candidates = ([f"{layer_id}_{date}.png"] if date else []) + [f"{layer_id}.png"]
    for filename in candidates:
        overlay = overlays / filename
        if overlay.is_file():
            return Response(
                content=overlay.read_bytes(),
                media_type="image/png",
                headers={
                    "X-GeoSAR-Fallback": "false",
                    "X-GeoSAR-Overlay": filename,
                    "Cache-Control": "public, max-age=3600",
                },
            )
    return _placeholder(f"overlay_not_found:{candidates[0]}")
