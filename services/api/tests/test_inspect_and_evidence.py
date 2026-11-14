"""Pixel inspect (trajectory, hydroperiod, regime) + Radar Evidence Card.

SRS refs: §5.3 (M of N), §5.4 (regimes), §7.1 inspect/evidence rows,
§7.2 rule 1 (out-of-bounds), §7.2 rule 2 (LLM timeout), §7.3 (card), §10 (honest language).
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import Settings
from app.services import evidence_narrator, raster_sampler
from app.services.evidence_narrator import deterministic_card
from app.services.raster_sampler import _latlon_to_rc
from conftest import assert_envelope
from helpers import DATES, FakeResponse, make_fake_async_client, write_cube

ASSAM = "aoi_assam_majuli"
ASSAM_BOUNDS = [93.90, 26.75, 94.30, 27.05]  # west, south, east, north
OUTSIDE_MSG = ("Clicked coordinate lies outside the pre-computed NISAR AOI footprint. "
               "Click inside the highlighted cyan telemetry boundary.")


@pytest.fixture
def synthetic_cube(monkeypatch, tmp_path):
    write_cube(tmp_path, ASSAM)
    monkeypatch.setattr(raster_sampler, "DATA_STORE", tmp_path)
    return tmp_path


@pytest.fixture
def no_cube(monkeypatch, tmp_path):
    monkeypatch.setattr(raster_sampler, "DATA_STORE", tmp_path)
    return tmp_path


# ================================================================ inspect: bounds (§7.2 rule 1)
@pytest.mark.parametrize("lat,lon", [
    (0.0, 0.0), (26.74, 94.0), (27.06, 94.0), (26.9, 93.89), (26.9, 94.31), (21.3, 79.1),
])
def test_click_outside_aoi_returns_friendly_status(client, lat, lon):
    res = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": lat, "lon": lon})
    assert res.status_code == 200
    body = res.json()
    assert_envelope(body)
    assert body["status"] == "outside_aoi"
    assert body["warning"] == OUTSIDE_MSG
    assert body["data"] == {"lat": lat, "lon": lon}


@pytest.mark.parametrize("lat,lon", [(26.75, 93.90), (27.05, 94.30), (26.75, 94.30), (27.05, 93.90)])
def test_click_exactly_on_boundary_is_inside(client, no_cube, lat, lon):
    body = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": lat, "lon": lon}).json()
    assert body["status"] != "outside_aoi"


def test_inspect_unknown_aoi(client):
    body = client.get("/api/v1/aois/nope/inspect", params={"lat": 1, "lon": 1}).json()
    assert body["status"] == "unknown_aoi"


@pytest.mark.parametrize("params", [{"lat": "abc", "lon": 94.1}, {"lat": 26.9}, {}])
def test_inspect_bad_params_never_500(client, params):
    res = client.get(f"/api/v1/aois/{ASSAM}/inspect", params=params)
    assert res.status_code != 500


# ================================================================ inspect: nodata fallback
def test_inspect_without_cube_returns_nodata_card(client, no_cube):
    body = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 26.9, "lon": 94.1}).json()
    assert body["status"] == "nodata"
    assert body["fallback_active"] is True
    assert body["data"]["hh_db"] == [] and body["data"]["hv_db"] == []
    assert body["data"]["hydroperiod"] == {"m": None, "n": None, "pct": None}


def test_corrupt_cube_degrades_to_nodata(client, monkeypatch, tmp_path):
    (tmp_path / ASSAM).mkdir()
    (tmp_path / ASSAM / "time_series_cube.npz").write_bytes(b"not a zip file")
    monkeypatch.setattr(raster_sampler, "DATA_STORE", tmp_path)
    body = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 26.9, "lon": 94.1}).json()
    assert body["status"] == "nodata"


# ================================================================ inspect: real cube (§5.3, §5.4)
def test_inspect_returns_full_trajectory_for_clicked_pixel(client, synthetic_cube):
    # NW corner -> row 0, col 0
    body = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 27.05, "lon": 93.90}).json()
    assert body["status"] == "ok" and body["fallback_active"] is False
    d = body["data"]
    assert d["dates"] == DATES
    assert len(d["hh_db"]) == len(d["hv_db"]) == len(DATES)
    assert d["hh_db"][3] == pytest.approx(-7.2, abs=1e-4)
    assert d["hv_db"][3] == pytest.approx(-18.4, abs=1e-4)


def test_inspect_hydroperiod_is_m_of_n(client, synthetic_cube):
    d = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 27.05, "lon": 93.90}).json()["data"]
    hp = d["hydroperiod"]
    assert (hp["m_open"], hp["m_flooded_veg"]) == (2, 4)
    assert (hp["m"], hp["n"]) == (6, 9)          # M = M_open + M_fveg
    assert hp["pct"] == 66.7


def test_inspect_regime_jrc_worldcover(client, synthetic_cube):
    d = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 27.05, "lon": 93.90}).json()["data"]
    assert d["gmm_regime"] == "Seasonally Flooded Canopy / Tall Grassland"
    assert d["jrc_occurrence_pct"] == 14.0
    assert d["worldcover_class"] == 90


def test_inspect_dry_pixel(client, synthetic_cube):
    d = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 26.75, "lon": 94.30}).json()["data"]
    assert d["hydroperiod"]["m"] == 0 and d["hydroperiod"]["pct"] == 0.0
    assert d["gmm_regime"] == "Stable Dry Upland / Levee"


def test_inspect_minimal_cube_without_optional_arrays(client, monkeypatch, tmp_path):
    """Plan B / single-pol: cube may lack hv_db, gmm, jrc... must still answer cleanly."""
    write_cube(tmp_path, ASSAM, full=False)
    monkeypatch.setattr(raster_sampler, "DATA_STORE", tmp_path)
    body = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 26.9, "lon": 94.1}).json()
    assert body["status"] == "ok"
    d = body["data"]
    assert d["hv_db"] == []
    assert d["gmm_regime"] is None and d["jrc_occurrence_pct"] is None
    # Dates fall back to the manifest timeline (ISO strings); if the cube has MORE steps than the
    # manifest, the extra steps get t<n> labels instead of crashing /inspect.
    assert len(d["dates"]) == len(d["hh_db"]) > 0
    assert all(isinstance(x, str) for x in d["dates"])
    timeline_dates = [t["date"] for t in __import__("app.data_store", fromlist=["store"]).store.get(ASSAM)["timeline"]]
    assert d["dates"][:len(timeline_dates)] == timeline_dates[:len(d["dates"])]


def test_inspect_zero_valid_observations_does_not_divide_by_zero(client, monkeypatch, tmp_path):
    import numpy as np
    path = write_cube(tmp_path, ASSAM)
    arrays = dict(np.load(path))
    arrays["n_valid"] = np.zeros_like(arrays["n_valid"])
    np.savez_compressed(path, **arrays)
    monkeypatch.setattr(raster_sampler, "DATA_STORE", tmp_path)
    body = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 26.9, "lon": 94.1}).json()
    assert body["status"] == "nodata"          # masked / outside swath everywhere
    assert body["data"]["hydroperiod"]["pct"] is None


def test_unhandled_error_is_wrapped_not_raw_500(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr("app.routers.inspect.sample_pixel", boom)
    res = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 26.9, "lon": 94.1})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "error" and body["fallback_active"] is True
    assert "RuntimeError" in body["warning"]


# ================================================================ pixel mapping unit tests
@pytest.mark.parametrize("lat,lon,expected", [
    (27.05, 93.90, (0, 0)),      # NW
    (26.75, 94.30, (9, 9)),      # SE
    (27.05, 94.30, (0, 9)),      # NE
    (26.75, 93.90, (9, 0)),      # SW
    (99.0, -999.0, (0, 0)),      # clamped
    (-99.0, 999.0, (9, 9)),      # clamped
])
def test_latlon_to_rowcol(lat, lon, expected):
    assert _latlon_to_rc(lat, lon, ASSAM_BOUNDS, (10, 10)) == expected


# ================================================================ evidence card: deterministic (§7.3)
SRS_EXAMPLE = {
    "lat": 26.9421, "lon": 94.1834,
    "hydroperiod": {"m": 6, "n": 9, "pct": 66.7},
    "gmm_regime": "Seasonally Flooded Canopy / Tall Grassland",
    "jrc_occurrence_pct": 14, "worldcover_class": 90,
    "delta_hh_db": 4.6, "peak_date": "2026-07-22", "peak_maturity": "PROVISIONAL",
}
CAVEAT = ("This is a radar-derived surface/canopy-water indication for field inspection, "
          "not a confirmed flood-depth measurement.")


def test_card_reproduces_srs_example():
    c = deterministic_card(SRS_EXAMPLE)
    assert c["mode"] == "deterministic"
    assert c["location"] == "26.9421, 94.1834"
    assert c["hydrological_regime"] == "Seasonally Flooded Canopy / Tall Grassland"
    assert c["monsoon_persistence"] == "Wet in 6 of 9 valid NISAR L-band observations (66.7%)."
    assert "2026-07-22" in c["radar_physics_evidence"]
    assert "PROVISIONAL" in c["radar_physics_evidence"]
    assert "+4.6 dB" in c["radar_physics_evidence"]
    assert "double-bounce" in c["radar_physics_evidence"]
    assert "Herbaceous Wetland" in c["land_cover_context"]
    assert "14%" in c["land_cover_context"] and "cannot penetrate canopy" in c["land_cover_context"]
    assert c["confidence"] == "Moderate-High"
    assert c["caveat"] == CAVEAT


def test_card_below_threshold_surge():
    c = deterministic_card({**SRS_EXAMPLE, "delta_hh_db": 2.0})
    assert "+2.0 dB" in c["radar_physics_evidence"]
    assert "below the +3.0 dB double-bounce threshold" in c["radar_physics_evidence"]
    assert c["confidence"] == "Moderate"


def test_card_threshold_is_inclusive_at_3db():
    c = deterministic_card({**SRS_EXAMPLE, "delta_hh_db": 3.0})
    assert "consistent with L-band dihedral double-bounce" in c["radar_physics_evidence"]


@pytest.mark.parametrize("m,n,delta,expected", [
    (6, 9, 4.6, "Moderate-High"),
    (5, 10, 3.0, "Moderate-High"),   # exactly 50 %
    (4, 10, 4.0, "Moderate"),        # 40 % wet
    (3, 10, 1.0, "Moderate"),        # 30 % boundary
    (2, 10, 5.0, "Low"),
    (0, 9, 5.0, "Low"),
    (6, 9, None, "Low"),             # no radar evidence -> never above Low
])
def test_card_confidence_levels(m, n, delta, expected):
    c = deterministic_card({"hydroperiod": {"m": m, "n": n}, "delta_hh_db": delta, "peak_date": "2026-07-22"})
    assert c["confidence"] == expected


def test_card_with_empty_telemetry_is_safe():
    c = deterministic_card({})
    assert c["location"] is None
    assert c["monsoon_persistence"] == "Hydroperiod not available for this pixel."
    assert c["radar_physics_evidence"] == "No double-bounce surge recorded at this pixel."
    assert "not loaded" in c["land_cover_context"]
    assert c["confidence"] == "Low"
    assert c["caveat"] == CAVEAT


def test_card_zero_valid_observations():
    c = deterministic_card({"hydroperiod": {"m": 0, "n": 0}})
    assert c["monsoon_persistence"] == "Hydroperiod not available for this pixel."


@pytest.mark.parametrize("wc,label", [(10, "Tree Cover"), (30, "Grassland"), (40, "Cropland"),
                                      (90, "Herbaceous Wetland"), (95, "Mangroves"), (999, "Unclassified")])
def test_card_worldcover_labels(wc, label):
    assert label in deterministic_card({"worldcover_class": wc})["land_cover_context"]


def test_card_high_jrc_is_not_flagged_low():
    text = deterministic_card({"jrc_occurrence_pct": 85})["land_cover_context"]
    assert "85%" in text and "low" not in text.lower().split("85%")[1]


@pytest.mark.parametrize("telemetry", [SRS_EXAMPLE, {}, {**SRS_EXAMPLE, "delta_hh_db": -2.0}])
def test_card_never_uses_forbidden_pitch_language(telemetry):
    """§10: never claim accuracy %, damage, stranded people, depth predictions, 'AI detects'."""
    text = " ".join(str(v) for v in deterministic_card(telemetry).values()).lower()
    for phrase in ("accuracy", "washed out", "stranded", "ai detects", "predict"):
        assert phrase not in text, phrase


# ================================================================ evidence card endpoint
def test_evidence_card_endpoint_deterministic_mode(client):
    body = client.post("/api/v1/evidence-card",
                       json={"aoi_id": ASSAM, "lat": 26.9421, "lon": 94.1834, "telemetry": SRS_EXAMPLE}).json()
    assert_envelope(body)
    assert body["aoi_id"] == ASSAM
    assert body["source_mode"] == "LOCAL_VERIFIED_CACHE"
    assert body["fallback_active"] is False
    assert body["data"]["card"]["mode"] == "deterministic"


def test_evidence_card_endpoint_accepts_empty_body(client):
    body = client.post("/api/v1/evidence-card", json={}).json()
    assert body["status"] == "ok"
    assert body["data"]["card"]["confidence"] == "Low"


def test_evidence_card_endpoint_rejects_non_json_without_500(client):
    res = client.post("/api/v1/evidence-card", content=b"garbage",
                      headers={"content-type": "application/json"})
    assert res.status_code != 500


def test_inspect_output_feeds_evidence_card_with_radar_evidence(client, synthetic_cube):
    """Integration (§7.3): clicking a surging pixel must yield a card WITH the dB surge.

    /inspect must therefore supply delta_hh_db + peak_date (or the card must derive them).
    """
    inspect = client.get(f"/api/v1/aois/{ASSAM}/inspect", params={"lat": 27.05, "lon": 93.90}).json()
    card = client.post("/api/v1/evidence-card",
                       json={"aoi_id": ASSAM, "telemetry": inspect["data"]}).json()["data"]["card"]
    assert "Wet in 6 of 9" in card["monsoon_persistence"]
    assert "No double-bounce surge recorded" not in card["radar_physics_evidence"]
    assert "2026-07-22" in card["radar_physics_evidence"]


# ================================================================ evidence card: LLM path (§7.2 rule 2)
def _llm_settings():
    return Settings(llm_api_key="test-key", llm_api_base="http://llm.invalid/v1",
                    llm_model="test-model", llm_fallback_models="", _env_file=None)


def test_llm_narrator_success(monkeypatch):
    calls: list = []
    resp = FakeResponse({"choices": [{"message": {"content": "Plain-language narration."}}]})
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient",
                        make_fake_async_client(response=resp, calls=calls))
    card, mode, fallback, warning = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert mode == "LIVE_API" and fallback is False and warning is None
    assert card["mode"] == "llm_grounded"
    assert card["narration"] == "Plain-language narration."
    assert card["caveat"] == CAVEAT                      # grounded fields untouched
    assert calls[1]["url"] == "http://llm.invalid/v1/chat/completions"
    assert calls[1]["headers"]["Authorization"] == "Bearer test-key"
    msgs = calls[1]["json"]["messages"]
    assert msgs[0]["role"] == "system" and "Use ONLY facts and numbers" in msgs[0]["content"]
    assert "radar_physics_evidence" in msgs[1]["content"]       # user turn = the grounded card JSON


def test_llm_narrator_timeout_is_bounded_and_non_blocking_setting(monkeypatch):
    calls: list = []
    resp = FakeResponse({"choices": [{"message": {"content": "x"}}]})
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient",
                        make_fake_async_client(response=resp, calls=calls))
    asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    timeout: httpx.Timeout = calls[0]["init"]["timeout"]
    assert timeout.read == _llm_settings().llm_timeout_seconds <= 20.0


@pytest.mark.parametrize("exc", [
    httpx.ReadTimeout("slow"), httpx.ConnectError("down"), KeyError("choices"),
])
def test_llm_narrator_failure_falls_back_to_deterministic(monkeypatch, exc):
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient", make_fake_async_client(exc=exc))
    card, mode, fallback, warning = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert card == deterministic_card(SRS_EXAMPLE)
    assert mode == "LOCAL_VERIFIED_CACHE" and fallback is True
    assert warning.startswith("LLM narrator unavailable")


def test_llm_narrator_http_error_falls_back(monkeypatch):
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient",
                        make_fake_async_client(response=FakeResponse(status_code=503)))
    card, mode, fallback, _ = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert card["mode"] == "deterministic" and fallback is True


def test_narrate_false_returns_instant_deterministic_card_without_calling_llm(monkeypatch):
    calls: list = []
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient", make_fake_async_client(
        response=FakeResponse({"choices": [{"message": {"content": "x"}}]}), calls=calls))
    card, mode, fallback, warning = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE, narrate=False))
    assert card["mode"] == "deterministic" and fallback is False and not calls


def test_llm_narrator_retries_once_on_503_then_succeeds(monkeypatch):
    seq = [FakeResponse(status_code=503), FakeResponse({"choices": [{"message": {"content": "Retried OK."}}]})]
    calls: list = []

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kw):
            calls.append(url)
            return seq.pop(0)

    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient", Client)
    card, mode, fallback, _ = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert card["narration"] == "Retried OK." and len(calls) == 2


def test_llm_narration_with_invented_numbers_is_rejected(monkeypatch):
    resp = FakeResponse({"choices": [{"message": {"content": "Water was 4.7 metres deep here."}}]})
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient", make_fake_async_client(response=resp))
    card, mode, fallback, warning = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert card == deterministic_card(SRS_EXAMPLE) and fallback is True and "unavailable" in warning


def test_same_card_is_narrated_once_then_served_from_cache(monkeypatch):
    calls: list = []
    resp = FakeResponse({"choices": [{"message": {"content": "Cached narration."}}]})
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient", make_fake_async_client(response=resp, calls=calls))
    a = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    b = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert a[0]["narration"] == b[0]["narration"] == "Cached narration."
    assert len([c for c in calls if "url" in c]) == 1            # second click spent no quota


def test_quota_429_pauses_the_llm_instead_of_slowing_every_click(monkeypatch):
    calls: list = []
    monkeypatch.setattr(evidence_narrator, "get_settings", _llm_settings)
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient",
                        make_fake_async_client(response=FakeResponse(status_code=429), calls=calls))
    first = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    n_after_first = len([c for c in calls if "url" in c])
    second = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert first[3].startswith("LLM narrator unavailable") and second[3].startswith("LLM narrator paused")
    assert n_after_first == 1 and len([c for c in calls if "url" in c]) == 1   # no retry, no 2nd call
    assert second[0] == deterministic_card(SRS_EXAMPLE)

def test_fallback_model_narrates_when_primary_is_out_of_quota(monkeypatch):
    seq = {"primary-m": FakeResponse(status_code=429),
           "backup-m": FakeResponse({"choices": [{"message": {"content": "Backup model narration."}}]})}
    used: list = []

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kw):
            used.append(kw["json"]["model"])
            return seq[kw["json"]["model"]]

    monkeypatch.setattr(evidence_narrator, "get_settings", lambda: Settings(
        llm_api_key="k", llm_api_base="http://llm.invalid/v1", llm_model="primary-m",
        llm_fallback_models="backup-m", _env_file=None))
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient", Client)
    card, mode, fallback, warning = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert used == ["primary-m", "backup-m"]
    assert card["narration"] == "Backup model narration." and card["narration_model"] == "backup-m"
    assert fallback is False and "fallback backup-m" in warning
    # primary is now paused: the next (different) card goes straight to the backup model
    used.clear()
    other = dict(SRS_EXAMPLE, lat=1.0)
    asyncio.run(evidence_narrator.build_evidence_card(other))
    assert used == ["backup-m"]


def test_all_models_failing_ends_on_the_built_in_template(monkeypatch):
    monkeypatch.setattr(evidence_narrator, "get_settings", lambda: Settings(
        llm_api_key="k", llm_api_base="http://llm.invalid/v1", llm_model="a",
        llm_fallback_models="b", _env_file=None))
    monkeypatch.setattr(evidence_narrator.httpx, "AsyncClient",
                        make_fake_async_client(response=FakeResponse(status_code=429)))
    card, mode, fallback, warning = asyncio.run(evidence_narrator.build_evidence_card(SRS_EXAMPLE))
    assert card == deterministic_card(SRS_EXAMPLE) and fallback is True and "narrator unavailable" in warning
