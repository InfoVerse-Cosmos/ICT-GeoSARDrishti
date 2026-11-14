"""One-click analysis report aggregation (SRS §4.2, §7.1, §7.3).

Composes a plain-language AOI summary strictly from numbers ALREADY computed by
the offline pipeline and committed to the data pack: the per-pixel hydroperiod
cube (m_open / m_fveg / n_valid), the GMM regime plane, per-scene Otsu thresholds,
the OSM exposure candidates and the manifest provenance. No number is invented.

Per-date open-water extent is taken from the manifest timeline metrics when the
pack carries them; for packs that only ship the hydroperiod cube (e.g. the
dual-track Gujarat pack) it is recomputed from the committed γ⁰ cube using each
scene's own dynamic Otsu HH threshold (and HV threshold in dual-pol) — the exact
open-water rule the classifier used — so the report mirrors the map overlays.

NISAR images an AOI from more than one track; consecutive acquisitions can cover
different parts of the footprint, so the before/after change is computed WITHIN a
single track/frame and flagged when more than one track is present.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np

from ..data_store import store
from .raster_sampler import _load_cube

REGIME_NAMES = [
    "Permanent River / Deep Channel",
    "Seasonal Open Floodplain / Beel",
    "Seasonally Flooded Canopy / Tall Grassland",
    "Seasonal Paddy-Like Inundation Cycle",
    "Stable Dry Upland / Levee",
]

# Mirrors scripts/geosar_pipeline MIN_WET_OBSERVATIONS (SRS §5.5).
MIN_WET_OBSERVATIONS = 3

HONEST_CAVEAT = (
    "This is a radar-derived surface/canopy-water indication for field inspection, "
    "not a confirmed flood, water-depth, or damage claim. Persistence is reported as "
    "M of N valid NISAR observations, never as days flooded. Any OPERA agreement is "
    "inter-sensor agreement, not ground-truth accuracy."
)

DEFAULT_LIMITATIONS = [
    "Radar-derived surface/canopy-water indication for inspection, not confirmed flood depth.",
    "OPERA agreement is inter-sensor agreement, not ground-truth accuracy.",
    "Hydroperiod expressed as M of N valid NISAR observations, not days flooded.",
]


def _r(value, nd: int = 1):
    """JSON-safe rounded float (NaN/inf/None -> None)."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if math.isfinite(f) else None


def _pixel_area_km2(bounds, rows: int, cols: int) -> float:
    west, south, east, north = bounds
    h = (north - south) * 111.32 / rows
    w = (east - west) * 111.32 * math.cos(math.radians((south + north) / 2)) / cols
    return h * w


def _granule_ids(prov: dict) -> list[str]:
    out = []
    for g in prov.get("granules", []) or []:
        if isinstance(g, dict):
            gid = g.get("granule_id")
            if gid:
                out.append(gid)
        elif isinstance(g, str):
            out.append(g)
    return out


def _otsu(prov: dict, date: str) -> tuple[float | None, float | None]:
    """Per-scene open-water thresholds, tolerant of both manifest key spellings."""
    t = (prov.get("otsu_thresholds", {}) or {}).get(date, {}) or {}
    thh = t.get("otsu_hh_db", t.get("hh_db"))
    thv = t.get("hv_thresh_db", t.get("hv_db"))
    return thh, thv


def _exposure_summary(aoi_id: str) -> dict:
    path = store.aoi_dir(aoi_id) / "osm_exposure.geojson"
    note = "Ground-inspection candidates only — never a damage claim."
    if not path.is_file():
        return {"count": 0, "threshold": None, "source": None, "top": [], "note": note,
                "available": False}
    try:
        fc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"count": 0, "threshold": None, "source": None, "top": [], "note": note,
                "available": False}
    feats = fc.get("features", []) or []
    meta = fc.get("_meta", {}) or {}
    ranked = sorted(
        (
            {
                "name": f["properties"].get("name", "unnamed"),
                "kind": f["properties"].get("kind"),
                "wet_observations": f["properties"].get("wet_observations"),
                "total_observations": f["properties"].get("total_observations"),
            }
            for f in feats
        ),
        key=lambda r: (r["wet_observations"] or 0),
        reverse=True,
    )
    return {
        "count": len(feats),
        "threshold": meta.get("threshold"),
        "source": meta.get("source"),
        "top": ranked[:5],
        "note": meta.get("note") or note,
        "available": True,
    }


def _regime_areas(cube: dict, prov: dict, px_km2: float) -> dict[str, float | None]:
    recorded = (prov.get("gmm") or {}).get("regime_area_km2")
    if recorded:
        return {name: _r(recorded.get(name, 0)) for name in REGIME_NAMES}
    if "gmm" in cube:
        gmm = cube["gmm"]
        return {name: _r(float((gmm == i).sum() * px_km2)) for i, name in enumerate(REGIME_NAMES)}
    return {}


def _per_date_open_water(manifest: dict, cube: dict, dates: list[str], px_km2: float) -> list[dict]:
    """Per observation: open-water (and flooded-veg where known) extent in km²."""
    timeline = manifest.get("timeline", [])
    prov = manifest.get("provenance", {})
    by_date = {t.get("date"): t for t in timeline}

    hh = cube.get("hh_db")
    hv = cube.get("hv_db")
    hh = hh.astype("float32") if hh is not None else None
    hv = hv.astype("float32") if hv is not None else None
    n_scenes = hh.shape[0] if hh is not None else len(dates)

    out = []
    for i, date in enumerate(dates[:n_scenes]):
        entry = by_date.get(date, {})
        metrics = entry.get("metrics") or {}
        ow = metrics.get("open_water_km2")
        fveg = metrics.get("flooded_veg_km2")
        method = "manifest timeline metrics"
        if ow is None and hh is not None:
            thh, thv = _otsu(prov, date)
            if thh is not None:
                mask = np.isfinite(hh[i]) & (hh[i] < thh)
                if hv is not None and thv is not None:
                    mask &= np.isfinite(hv[i]) & (hv[i] < thv)
                ow = float(mask.sum() * px_km2)
                method = "recomputed from γ⁰ cube with the scene's dynamic Otsu threshold"
        out.append({
            "date": date,
            "track_frame": entry.get("track_frame") or manifest.get("track_frame"),
            "maturity": entry.get("maturity"),
            "open_water_km2": _r(ow),
            "flooded_veg_km2": _r(fveg),
            "method": method,
        })
    return out


def _change(per_date: list[dict]) -> dict:
    """Before/after open-water change WITHIN one track/frame (honest about geometry)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in per_date:
        if d["open_water_km2"] is not None:
            groups[d["track_frame"] or "—"].append(d)

    candidates = []
    for tf, rows in groups.items():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda r: r["date"])
        before, after = rows[0], rows[-1]
        candidates.append({
            "track_frame": tf,
            "before_date": before["date"],
            "after_date": after["date"],
            "before_open_water_km2": before["open_water_km2"],
            "after_open_water_km2": after["open_water_km2"],
            "delta_open_water_km2": _r(after["open_water_km2"] - before["open_water_km2"]),
        })

    multi_track = len(groups) > 1
    candidates.sort(key=lambda c: abs(c["delta_open_water_km2"] or 0), reverse=True)
    primary = candidates[0] if candidates else None
    if primary is None:
        note = ("Only one NISAR observation per track is available, so a before/after open-water "
                "change cannot be computed; the persistence summary below spans the whole stack.")
    elif multi_track:
        note = (f"Compared within track {primary['track_frame']} only: NISAR images this AOI from "
                f"more than one track, and different passes cover different parts of the footprint, "
                f"so observations are not compared across tracks.")
    else:
        note = f"Earliest vs latest NISAR observation on track {primary['track_frame']}."
    return {"multi_track": multi_track, "primary": primary, "per_track": candidates, "note": note}


def build_report(aoi_id: str) -> dict | None:
    """Returns the report payload, or None if the AOI is unknown."""
    manifest = store.get(aoi_id)
    if manifest is None:
        return None

    prov = manifest.get("provenance", {}) or {}
    timeline = manifest.get("timeline", [])
    dates = [t["date"] for t in timeline if t.get("date")]
    limitations = prov.get("limitations") or DEFAULT_LIMITATIONS
    exposure = _exposure_summary(aoi_id)

    base = {
        "aoi_id": aoi_id,
        "name": manifest.get("name"),
        "role": manifest.get("role"),
        "bounds": manifest.get("bounds"),
        "track_frame": manifest.get("track_frame"),
        "polarization": manifest.get("polarization", "HH+HV"),
        "single_pol_mode": bool(manifest.get("single_pol_mode", False)),
        "reference_date": manifest.get("reference_date"),
        "dates": dates,
        "date_range": {"first": dates[0], "last": dates[-1]} if dates else {"first": None, "last": None},
        "synthetic_test_data": bool(manifest.get("synthetic_test_data", False)),
        "exposure": exposure,
        "caveat": HONEST_CAVEAT,
        "limitations": limitations,
        "provenance": {
            "granules": _granule_ids(prov),
            "track_frame": manifest.get("track_frame"),
            "reference_date": prov.get("reference_date") or manifest.get("reference_date"),
            "delta_hh_params": prov.get("delta_hh_params", {"min_delta_hh_db": 3.0, "min_delta_ratio_db": 1.5}),
            "otsu_thresholds": prov.get("otsu_thresholds", {}),
            "opera_dswx_agreement_pct": prov.get("opera_dswx_agreement_pct"),
        },
    }

    cube = _load_cube(aoi_id)
    if cube is None or "m_open" not in cube or "n_valid" not in cube:
        base["data_pack_ready"] = False
        base["message"] = ("The full hydroperiod pack for this AOI has not been generated yet "
                           "(run the offline pipeline). Showing the acquisition timeline and caveats only.")
        base["hydroperiod"] = None
        base["classes"] = None
        base["change"] = None
        return base

    bounds = manifest.get("bounds")
    n_valid = cube["n_valid"].astype("int32")
    rows, cols = n_valid.shape
    px = _pixel_area_km2(bounds, rows, cols)

    m_open = cube["m_open"].astype("int32")
    m_fveg = cube.get("m_fveg")
    m_fveg = m_fveg.astype("int32") if m_fveg is not None else np.zeros_like(m_open)
    m_total = m_open + m_fveg
    valid = n_valid > 0
    max_n = int(n_valid.max()) if valid.any() else 0
    rep_thresh = min(MIN_WET_OBSERVATIONS, max_n) if max_n else MIN_WET_OBSERVATIONS

    season = manifest.get("season_summary") or {}
    hydroperiod = {
        "n_min": int(n_valid[valid].min()) if valid.any() else 0,
        "n_max": max_n,
        "max_wet_observations": int(m_total.max()) if m_total.size else 0,
        "ever_wet_km2": season.get("ever_wet_km2") or _r(float((m_total > 0).sum() * px)),
        "ever_open_water_km2": _r(float((m_open > 0).sum() * px)),
        "ever_flooded_veg_km2": _r(float((m_fveg > 0).sum() * px)),
        "wet_every_observation_km2": (season.get("wet_every_observation_km2")
                                      or _r(float(((m_total == n_valid) & valid).sum() * px))),
        "repeatedly_wet_threshold": rep_thresh,
        "repeatedly_wet_km2": _r(float(((m_total >= rep_thresh) & valid).sum() * px)),
    }

    per_date = _per_date_open_water(manifest, cube, dates, px)

    base["data_pack_ready"] = True
    base["grid"] = {"rows": rows, "cols": cols, "pixel_area_km2": _r(px, 5)}
    base["hydroperiod"] = hydroperiod
    base["classes"] = {
        "regimes_km2": _regime_areas(cube, prov, px),
        "per_date": per_date,
    }
    base["change"] = _change(per_date)
    return base
