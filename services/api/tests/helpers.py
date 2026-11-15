"""Test helpers: fake httpx client + synthetic NISAR data-pack builder.

The backend only lists AOIs that have a real pack on disk (a manifest.json AND a
time_series_cube.npz, see app/data_store.py). The repo ships no packs, so the
tests build their own synthetic packs in a temp data store: a manifest written by
``write_manifest`` next to the cube written by ``write_cube`` (``write_pack`` does
both). ``conftest`` seeds the two standard AOIs this way before every test.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import numpy as np

DATES = [
    "2026-06-14", "2026-06-26", "2026-07-10", "2026-07-22", "2026-08-15",
    "2026-09-08", "2026-10-02", "2026-10-26", "2026-11-07",
]

# Honest-framing limitations (SRS §10): "M of N", "inter-sensor agreement", and the
# only permitted (negated) use of the word "accuracy". Mirrors the backend defaults.
STANDARD_LIMITATIONS = [
    "Radar-derived surface/canopy-water indication for inspection, not confirmed flood depth.",
    "OPERA agreement is inter-sensor agreement, not ground-truth accuracy.",
    "Hydroperiod expressed as M of N valid NISAR observations, not days flooded.",
]

# The two standard preset AOIs the tests assume exist (SRS §3.1). Both carry WGS84
# bounds describing a ~30 km window, a timeline whose dates straddle the 21-23 Oct 2026
# PROVISIONAL->VALIDATED calibration transition with no acquisition inside the
# 27 Jul-10 Aug 2026 sensor gap, and the pipeline thematic layers.
AOI_SPECS = {
    "aoi_assam_majuli": {
        "name": "Majuli Island, Assam",
        "role": "primary",
        "bounds": [93.90, 26.75, 94.30, 27.05],
        "default_zoom": 10,
        "track_frame": "040/015",
        "granule_prefix": "NISAR_L2_PR_GCOV_040_015_A",
        # Three same-track scenes -> a complete before/after report (SRS §4.2).
        "timeline": [
            {"date": "2026-07-10", "maturity": "PROVISIONAL", "open_water_km2": 256.1},
            {"date": "2026-07-22", "maturity": "PROVISIONAL", "open_water_km2": 320.7},
            {"date": "2026-11-07", "maturity": "VALIDATED", "open_water_km2": 103.3},
        ],
        "wet_every_observation_km2": 99.3,
    },
    "aoi_nagpur_kanhan": {
        "name": "Kanhan River, Nagpur",
        "role": "secondary",
        "bounds": [78.95, 21.15, 79.35, 21.45],
        "default_zoom": 10,
        "track_frame": "055/021",
        "granule_prefix": "NISAR_L2_PR_GCOV_055_021_A",
        "timeline": [
            {"date": "2026-08-15", "maturity": "PROVISIONAL", "open_water_km2": 41.0},
            {"date": "2026-10-02", "maturity": "PROVISIONAL", "open_water_km2": 58.6},
            {"date": "2026-11-07", "maturity": "VALIDATED", "open_water_km2": 22.4},
        ],
        "wet_every_observation_km2": 18.2,
    },
}

PIPELINE_LAYERS = ["open_water", "flooded_veg", "hydroperiod", "gmm_regimes"]


def standard_manifest(aoi_id: str) -> dict:
    """Builds a synthetic-but-realistic manifest matching the backend's expectations.

    Grounded so the EXISTING assertions pass unchanged: WGS84 ~30 km bounds, a maturity
    badge per date, the 27 Jul-10 Aug 2026 acquisition gap, HH+HV polarization,
    fallback plan A, the delta-HH thresholds and the honest-language limitations.
    """
    spec = AOI_SPECS[aoi_id]
    prefix = spec["granule_prefix"]
    timeline = []
    granules = []
    for t in spec["timeline"]:
        compact = t["date"].replace("-", "")
        granule_id = f"{prefix}_{compact}T000000"
        granules.append(granule_id)
        timeline.append({
            "date": t["date"],
            "maturity": t["maturity"],
            "track_frame": spec["track_frame"],
            "granule_id": granule_id,
            "metrics": {"open_water_km2": t["open_water_km2"]},
        })
    reference_date = spec["timeline"][-1]["date"]
    return {
        "aoi_id": aoi_id,
        "name": spec["name"],
        "role": spec["role"],
        "bounds": list(spec["bounds"]),
        "default_zoom": spec["default_zoom"],
        "layers": list(PIPELINE_LAYERS),
        "polarization": "HH+HV",
        "single_pol_mode": False,
        "track_frame": spec["track_frame"],
        "fallback_plan": "A",
        "reference_date": reference_date,
        "acquisition_gaps": ["2026-07-27/2026-08-10"],
        "synthetic_test_data": False,
        "season_summary": {"wet_every_observation_km2": spec["wet_every_observation_km2"]},
        "timeline": timeline,
        "provenance": {
            "reference_date": reference_date,
            "granules": granules,
            "delta_hh_params": {"min_delta_hh_db": 3.0, "min_delta_ratio_db": 1.5},
            "limitations": list(STANDARD_LIMITATIONS),
        },
    }


def standard_exposure() -> dict:
    """OSM ground-inspection candidates (SRS §5.5) ranked by wet observations."""
    return {
        "type": "FeatureCollection",
        "_meta": {"threshold": 3, "source": "OpenStreetMap",
                  "note": "Ground-inspection candidates only, never a damage claim."},
        "features": [
            {"type": "Feature", "id": "village/1", "geometry": None,
             "properties": {"kind": "village", "name": "Kamalabari",
                            "wet_observations": 7, "total_observations": 9}},
            {"type": "Feature", "id": "road/2", "geometry": None,
             "properties": {"kind": "road", "name": "NH715K",
                            "wet_observations": 4, "total_observations": 9}},
        ],
    }


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://fake")
            raise httpx.HTTPStatusError(
                "fake error", request=req, response=httpx.Response(self.status_code, request=req)
            )

    def json(self) -> dict:
        return self._payload


def make_fake_async_client(*, response: FakeResponse | None = None, exc: Exception | None = None,
                           calls: list | None = None):
    """Returns a drop-in replacement for httpx.AsyncClient that records calls."""

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            if calls is not None:
                calls.append({"init": kwargs})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def _do(self, url, **kwargs):
            if calls is not None:
                calls.append({"url": url, **kwargs})
            if exc is not None:
                raise exc
            return response

        get = _do
        post = _do

    return FakeAsyncClient


def write_cube(root: Path, aoi_id: str, rows: int = 10, cols: int = 10, *, full: bool = True) -> Path:
    """Writes a synthetic time_series_cube.npz with known values at the corners.

    Pixel (0,0)   = NW corner: flooded-vegetation-like trajectory, 6/9 wet, regime idx 2.
    Pixel (-1,-1) = SE corner: dry upland, 0/9 wet, regime idx 4.
    """
    t = len(DATES)
    hh = np.full((t, rows, cols), -12.0, dtype=np.float32)
    hv = np.full((t, rows, cols), -18.0, dtype=np.float32)
    # NW pixel: dry baseline -11.8 dB, surge to -7.2 dB on 2026-07-22 (SRS §7.3 example).
    hh[:, 0, 0] = [-11.5, -10.0, -8.0, -7.2, -9.0, -9.5, -10.5, -11.6, -11.8]
    hv[:, 0, 0] = [-18.0, -18.2, -18.5, -18.4, -18.1, -18.0, -18.0, -18.1, -18.0]

    arrays = {"hh_db": hh}
    if full:
        m_open = np.zeros((rows, cols), dtype=np.int16)
        m_fveg = np.zeros((rows, cols), dtype=np.int16)
        n_valid = np.full((rows, cols), t, dtype=np.int16)
        m_open[0, 0], m_fveg[0, 0] = 2, 4
        gmm = np.full((rows, cols), 4, dtype=np.int8)
        gmm[0, 0] = 2
        jrc = np.full((rows, cols), 0.0, dtype=np.float32)
        jrc[0, 0] = 14.0
        worldcover = np.full((rows, cols), 40, dtype=np.int16)
        worldcover[0, 0] = 90
        arrays.update(
            hv_db=hv, m_open=m_open, m_fveg=m_fveg, n_valid=n_valid,
            gmm=gmm, jrc=jrc, worldcover=worldcover, dates=np.array(DATES),
        )

    out_dir = root / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "time_series_cube.npz"
    np.savez_compressed(path, **arrays)
    return path


def write_manifest(root: Path, aoi_id: str, manifest: dict | None = None) -> Path:
    """Writes a manifest.json next to the cube so the data store lists the pack."""
    out_dir = root / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest or standard_manifest(aoi_id)), encoding="utf-8")
    return path


def write_exposure(root: Path, aoi_id: str, feature_collection: dict | None = None) -> Path:
    out_dir = root / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "osm_exposure.geojson"
    path.write_text(json.dumps(feature_collection or standard_exposure()), encoding="utf-8")
    return path


def write_pack(root: Path, aoi_id: str, *, cube: bool = True, full: bool = True,
               exposure: bool = False, manifest: dict | None = None) -> Path:
    """Writes a complete synthetic AOI pack (manifest + cube, optional exposure).

    A pack is only listed by the data store when BOTH manifest.json and
    time_series_cube.npz are present (app/data_store.py:_pack_ready).
    """
    write_manifest(root, aoi_id, manifest)
    if cube:
        write_cube(root, aoi_id, full=full)
    if exposure:
        write_exposure(root, aoi_id)
    return root / aoi_id
