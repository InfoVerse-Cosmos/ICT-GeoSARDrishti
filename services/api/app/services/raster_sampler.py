"""Fast coordinate -> pixel time-series lookup (SRS §6, §7.1, §7.3).

Reads the committed `time_series_cube.npz` for an AOI and returns the full
monsoon HH/HV dB trajectory, per-date class, hydroperiod M/N, GMM regime, JRC %,
WorldCover class AND the radar evidence the Evidence Card needs (ΔHH surge vs
the dry reference, peak date + maturity, ΔRatio, darkest open-water date).
Falls back to a structured 'nodata' card when the pack is not present yet.
"""
from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Any

import numpy as np

from ..config import DATA_STORE
from ..data_store import store

logger = logging.getLogger("geosar.raster")

CLASS_NAMES = {0: "dry", 1: "open_water", 2: "flooded_veg", 255: "nodata"}
WC_CROPLAND = 40

_REGIME_NAMES = [
    "Permanent River / Deep Channel",
    "Seasonal Open Floodplain / Beel",
    "Seasonally Flooded Canopy / Tall Grassland",
    "Seasonal Paddy-Like Inundation Cycle",
    "Stable Dry Upland / Levee",
]


@lru_cache(maxsize=4)
def _load_cube(aoi_id: str):
    """Loads a cached npz cube fully into memory. Returns None if missing/corrupt."""
    path = DATA_STORE / aoi_id / "time_series_cube.npz"
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load cube for %s: %s", aoi_id, exc)
        return None


def _latlon_to_rc(lat: float, lon: float, bounds: list[float], shape: tuple[int, int]) -> tuple[int, int]:
    """Pixel containing (lat, lon) on the regular AOI grid (row 0 = north edge)."""
    west, south, east, north = bounds
    rows, cols = shape
    col = math.floor((lon - west) / (east - west) * cols)
    row = math.floor((north - lat) / (north - south) * rows)
    return max(0, min(rows - 1, row)), max(0, min(cols - 1, col))


def _f(v) -> float | None:
    """JSON-safe float (NaN/inf -> None)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, 2) if math.isfinite(v) else None


def _manifest_dates(manifest: dict) -> list[str]:
    return [str(t.get("date")) for t in manifest.get("timeline", []) if t.get("date")]


def trajectory_evidence(dates: list[str], hh: list, hv: list, ref_idx: int,
                        maturity: dict[str, str], thresholds: dict) -> dict[str, Any]:
    """Derives the physical evidence quoted by the Radar Evidence Card (SRS §7.3)."""
    out: dict[str, Any] = {"reference_date": None, "hh_baseline_db": None, "delta_hh_db": None,
                           "peak_date": None, "peak_maturity": None, "hh_peak_db": None,
                           "delta_ratio_db": None, "min_hh_db": None, "min_hh_date": None,
                           "open_water_threshold_db": None}
    if not dates or ref_idx >= len(hh) or hh[ref_idx] is None:
        return out
    base = hh[ref_idx]
    out["reference_date"] = dates[ref_idx]
    out["hh_baseline_db"] = base
    deltas = [(h - base, i) for i, h in enumerate(hh) if h is not None and i != ref_idx]
    if deltas:
        d, i = max(deltas)
        out.update(delta_hh_db=round(d, 1), peak_date=dates[i], peak_maturity=maturity.get(dates[i]),
                   hh_peak_db=hh[i])
        if hv and hv[i] is not None and hv[ref_idx] is not None:
            out["delta_ratio_db"] = round((hh[i] - hv[i]) - (base - hv[ref_idx]), 1)
    finite = [(h, i) for i, h in enumerate(hh) if h is not None]
    if finite:
        h, i = min(finite)
        out["min_hh_db"], out["min_hh_date"] = h, dates[i]
        out["open_water_threshold_db"] = (thresholds.get(dates[i]) or {}).get("hh_db")
    return out


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
                "lat": lat, "lon": lon,
                "dates": _manifest_dates(manifest),
                "hh_db": [], "hv_db": [], "classes": [],
                "hydroperiod": {"m": None, "n": None, "pct": None},
                "gmm_regime": None, "jrc_occurrence_pct": None, "worldcover_class": None,
            },
        }

    bounds = manifest.get("bounds", [0, 0, 1, 1])
    hh_cube = cube["hh_db"]  # (T, rows, cols)
    T = hh_cube.shape[0]
    dates = [str(d) for d in cube["dates"]] if "dates" in cube else _manifest_dates(manifest)[:T]
    if len(dates) != T:  # cube/manifest mismatch: never crash a live demo, label the unknown steps
        dates = [dates[i] if i < len(dates) else f"t{i + 1}" for i in range(T)]
    row, col = _latlon_to_rc(lat, lon, bounds, hh_cube.shape[1:])

    hh = [_f(v) for v in hh_cube[:, row, col]]
    hv = [_f(v) for v in cube["hv_db"][:, row, col]] if "hv_db" in cube else []
    classes = [CLASS_NAMES.get(int(c), "nodata") for c in cube["cls"][:, row, col]] if "cls" in cube else []

    m_open = int(cube["m_open"][row, col]) if "m_open" in cube else None
    m_fveg = int(cube["m_fveg"][row, col]) if "m_fveg" in cube else None
    n_valid = int(cube["n_valid"][row, col]) if "n_valid" in cube else len(dates)
    m_total = (m_open or 0) + (m_fveg or 0)
    ref_idx = int(cube["ref_index"]) if "ref_index" in cube else len(dates) - 1

    maturity = {str(t.get("date")): t.get("maturity") for t in manifest.get("timeline", [])}
    thresholds = manifest.get("provenance", {}).get("otsu_thresholds", {}) or {}
    wc = int(cube["worldcover"][row, col]) if "worldcover" in cube else None
    evidence = trajectory_evidence(dates, hh, hv, ref_idx, maturity, thresholds)

    if n_valid == 0:
        status, warning = "nodata", "No valid NISAR observation at this pixel (outside swath or masked)."
    else:
        status, warning = "ok", None

    return {
        "status": status,
        "fallback_active": False,
        "warning": warning,
        "data": {
            "lat": lat, "lon": lon, "row": row, "col": col,
            "dates": dates,
            "maturity": [maturity.get(d) for d in dates],
            "hh_db": hh,
            "hv_db": hv,
            "classes": classes,
            "wet_dates": [d for d, c in zip(dates, classes) if c in ("open_water", "flooded_veg")],
            "hydroperiod": {
                "m": m_total,
                "n": n_valid,
                "pct": round(100.0 * m_total / n_valid, 1) if n_valid else None,
                "m_open": m_open,
                "m_flooded_veg": m_fveg,
            },
            "gmm_regime": _regime_label(cube, row, col),
            "jrc_occurrence_pct": _f(cube["jrc"][row, col]) if "jrc" in cube else None,
            "worldcover_class": wc,
            "flooded_veg_sublabel": (("Paddy-Like Agricultural Inundation" if wc == WC_CROPLAND
                                      else "Natural Flooded Vegetation") if (m_fveg and wc is not None) else None),
            # (no land-cover sub-label unless the ESA WorldCover layer was supplied to the pipeline)
            "single_pol_mode": "hv_db" not in cube,
            "synthetic_test_data": bool(manifest.get("synthetic_test_data")),
            **evidence,
        },
    }


def _regime_label(cube, row: int, col: int) -> str | None:
    if "gmm" not in cube:
        return None
    idx = int(cube["gmm"][row, col])
    if 0 <= idx < len(_REGIME_NAMES):
        return _REGIME_NAMES[idx]
    return None
