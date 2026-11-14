"""Fast coordinate -> pixel time-series lookup (SRS §6, §7.1).

Reads the committed `time_series_cube.npz` for an AOI and returns the full
monsoon HH/HV dB trajectory, hydroperiod M/N, GMM regime, JRC %, and WorldCover
class for the clicked pixel. Falls back to a structured 'nodata' card when the
pack is not present yet (Phase 1 before data generation).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np

from ..config import DATA_STORE
from ..data_store import store

logger = logging.getLogger("geosar.raster")


@lru_cache(maxsize=4)
def _load_cube(aoi_id: str):
    """Loads a cached npz cube. Returns None if missing/corrupt."""
    path = DATA_STORE / aoi_id / "time_series_cube.npz"
    if not path.exists():
        return None
    try:
        return np.load(path, allow_pickle=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load cube for %s: %s", aoi_id, exc)
        return None


def _latlon_to_rc(lat: float, lon: float, bounds: list[float], shape: tuple[int, int]) -> tuple[int, int]:
    west, south, east, north = bounds
    rows, cols = shape
    col = int((lon - west) / (east - west) * (cols - 1))
    row = int((north - lat) / (north - south) * (rows - 1))
    return max(0, min(rows - 1, row)), max(0, min(cols - 1, col))


def sample_pixel(aoi_id: str, lat: float, lon: float) -> dict[str, Any]:
    """Returns {status, data, fallback_active, warning}."""
    manifest = store.get(aoi_id) or {}
    cube = _load_cube(aoi_id)

    if cube is None:
        return {
            "status": "nodata",
            "fallback_active": True,
            "warning": "Pixel time-series cube not generated yet (produced in Phase 2 via scripts/02).",
            "data": {
                "lat": lat,
                "lon": lon,
                "dates": manifest.get("timeline", []),
                "hh_db": [],
                "hv_db": [],
                "hydroperiod": {"m": None, "n": None, "pct": None},
                "gmm_regime": None,
                "jrc_occurrence_pct": None,
                "worldcover_class": None,
            },
        }

    bounds = manifest.get("bounds", [0, 0, 1, 1])
    dates = list(cube["dates"]) if "dates" in cube else manifest.get("timeline", [])
    hh = cube["hh_db"]  # shape (T, rows, cols)
    row, col = _latlon_to_rc(lat, lon, bounds, hh.shape[1:])

    hv = cube["hv_db"] if "hv_db" in cube else None
    m_open = int(cube["m_open"][row, col]) if "m_open" in cube else None
    m_fveg = int(cube["m_fveg"][row, col]) if "m_fveg" in cube else None
    n_valid = int(cube["n_valid"][row, col]) if "n_valid" in cube else len(dates)
    m_total = (m_open or 0) + (m_fveg or 0)

    return {
        "status": "ok",
        "fallback_active": False,
        "warning": None,
        "data": {
            "lat": lat,
            "lon": lon,
            "dates": [str(d) for d in dates],
            "hh_db": [float(v) for v in hh[:, row, col]],
            "hv_db": [float(v) for v in hv[:, row, col]] if hv is not None else [],
            "hydroperiod": {
                "m": m_total,
                "n": n_valid,
                "pct": round(100.0 * m_total / n_valid, 1) if n_valid else None,
                "m_open": m_open,
                "m_flooded_veg": m_fveg,
            },
            "gmm_regime": _regime_label(cube, row, col),
            "jrc_occurrence_pct": float(cube["jrc"][row, col]) if "jrc" in cube else None,
            "worldcover_class": int(cube["worldcover"][row, col]) if "worldcover" in cube else None,
        },
    }


_REGIME_NAMES = [
    "Permanent River / Deep Channel",
    "Seasonal Open Floodplain / Beel",
    "Seasonally Flooded Canopy / Tall Grassland",
    "Seasonal Paddy-Like Inundation Cycle",
    "Stable Dry Upland / Levee",
]


def _regime_label(cube, row: int, col: int) -> str | None:
    if "gmm" not in cube:
        return None
    idx = int(cube["gmm"][row, col])
    if 0 <= idx < len(_REGIME_NAMES):
        return _REGIME_NAMES[idx]
    return None
