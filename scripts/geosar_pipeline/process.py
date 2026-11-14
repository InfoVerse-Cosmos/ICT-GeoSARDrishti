"""Stage 02 — subset, speckle filter, dB, Otsu, 3-class classifier, hydroperiod, overlays (SRS §5.1-5.3)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .common import (AOI_BOUNDS, MAX_SLOPE_DEG, MIN_DELTA_HH_DB, MIN_DELTA_RATIO_DB, OTSU_HH_RANGE_DB,
                     OTSU_HV_RANGE_DB, WC_CROPLAND, WC_VEGETATION, aoi_grid, fallback_plan, load_manifest,
                     mask_to_rgba, now_iso, pixel_area_km2, sample_geotiff, save_manifest, select_best_track,
                     write_png)
from .data_gate import granules_from_dir
from .physics import (DRY, FLOODED_VEG, NODATA_CLASS, OPEN_WATER, classify_scene, dynamic_threshold,
                      hydroperiod, median3, slope_deg, to_db)

COLOURS = {"open": "#0284C7", "fveg": "#10B981", "paddy": "#F59E0B"}


def hydroperiod_rgba(m_total: np.ndarray, n_valid: np.ndarray) -> np.ndarray:
    """Amber→deep-orange ramp by wet fraction; transparent where never wet."""
    with np.errstate(invalid="ignore", divide="ignore"):
        f = np.where(n_valid > 0, m_total / np.maximum(n_valid, 1), 0.0)
    out = np.zeros((*f.shape, 4), dtype=np.uint8)
    wet = f > 0
    lo, hi = np.array([253, 230, 138]), np.array([194, 65, 12])
    rgb = lo + (hi - lo) * f[..., None]
    out[..., :3] = rgb.astype(np.uint8)
    out[..., 3] = np.where(wet, (90 + 150 * f).astype(np.uint8), 0)
    return out


def run(aoi_id: str, h5_dir: str | Path, store: Path, *, track_frame: str | None = None,
        ref_date: str | None = None, res_m: float = 100.0, worldcover: str | None = None,
        dem: str | None = None, log=print) -> dict:
    manifest = load_manifest(aoi_id, store)
    bounds = manifest.get("bounds") or AOI_BOUNDS[aoi_id]
    rows, cols, lats, lons = aoi_grid(bounds, res_m)
    log(f"[02] AOI {aoi_id} grid {rows}x{cols} @ {res_m:.0f} m")

    granules = [g for g in granules_from_dir(h5_dir, aoi_id) if not g.get("skipped")]
    tf, stack = select_best_track(granules, track_frame)
    log(f"[02] track/frame {tf}: {[g['date'] for g in stack]}")

    # ---- read + multilook + speckle filter + dB --------------------------------------
    from .gcov import read_subset  # h5py/pyproj imported lazily

    hh_list, hv_list, used, coverage, synthetic, epsgs = [], [], [], {}, False, set()
    for g in stack:
        sub = read_subset(g["path"], lats, lons, res_m)
        coverage[g["date"]] = sub["coverage_pct"]
        synthetic |= sub["synthetic"]
        if sub["hh"] is None or sub["coverage_pct"] < 5:
            log(f"[02]   {g['date']}: skipped (AOI coverage {sub['coverage_pct']}%)")
            continue
        epsgs.add(sub["epsg"])
        hh_list.append(to_db(median3(sub["hh"])))
        hv_list.append(to_db(median3(sub["hv"])) if sub["hv"] is not None else None)
        used.append(g)
        log(f"[02]   {g['date']}: coverage {sub['coverage_pct']}%  pols={sub['polarizations']}")

    if len(used) < 1:
        raise RuntimeError("no granule covers the AOI — check footprint / choose another track (Plan D)")

    dual_pol = all(h is not None for h in hv_list)
    dates = [g["date"] for g in used]
    hh = np.stack(hh_list)
    hv = np.stack(hv_list) if dual_pol else None
    T = len(dates)

    # ---- masks -------------------------------------------------------------------------
    valid_static = np.ones((rows, cols), bool)
    wc = None
    if worldcover:
        wc = sample_geotiff(worldcover, lats, lons)
        veg_mask = np.isin(np.nan_to_num(wc, nan=-1).astype(int), list(WC_VEGETATION))
        veg_source = "ESA WorldCover 10 m (classes 10,20,30,40,90,95)"
    else:
        veg_mask = np.ones((rows, cols), bool)
        veg_source = "none supplied — double-bounce test applied to all non-water pixels"
    slope_source = "not applied (no DEM supplied)"
    if dem:
        dem_arr = sample_geotiff(dem, lats, lons)
        cell_h = (bounds[3] - bounds[1]) * 111_320 / rows
        cell_w = (bounds[2] - bounds[0]) * 111_320 * np.cos(np.radians(np.mean(bounds[1::2]))) / cols
        steep = slope_deg(np.nan_to_num(dem_arr, nan=np.nanmean(dem_arr)), cell_h, cell_w) > MAX_SLOPE_DEG
        valid_static &= ~steep
        slope_source = f"Copernicus DEM slope > {MAX_SLOPE_DEG}° excluded ({int(steep.sum())} px)"

    # ---- reference (post-monsoon dry) scene ---------------------------------------------
    ref_idx = dates.index(ref_date) if ref_date in dates else T - 1
    hh_ref = hh[ref_idx]
    hv_ref = hv[ref_idx] if dual_pol else None

    # ---- classify per date ---------------------------------------------------------------
    cls = np.full((T, rows, cols), NODATA_CLASS, dtype=np.uint8)
    thresholds = {}
    for t in range(T):
        t_hh = dynamic_threshold(hh[t][valid_static], OTSU_HH_RANGE_DB)
        t_hv = dynamic_threshold(hv[t][valid_static], OTSU_HV_RANGE_DB) if dual_pol else None
        thresholds[dates[t]] = {"hh_db": round(t_hh, 2), "hv_db": None if t_hv is None else round(t_hv, 2)}
        valid = np.isfinite(hh[t]) & np.isfinite(hh_ref) & valid_static
        if dual_pol:
            valid &= np.isfinite(hv[t]) & np.isfinite(hv_ref)
        cls[t] = classify_scene(hh[t], hv[t] if dual_pol else None, hh_ref, hv_ref, veg_mask,
                                t_hh, t_hv if t_hv is not None else 0.0, valid=valid)

    m_open, m_fveg, n_valid = hydroperiod(cls)
    m_total = m_open + m_fveg

    # ---- PROVISIONAL -> VALIDATED radiometric offset check (SRS §3.2) ----------------------
    calibration = None
    mats = [g["maturity"] for g in used]
    if "PROVISIONAL" in mats and "VALIDATED" in mats:
        a = max(i for i, m in enumerate(mats) if m == "PROVISIONAL")
        b = min(i for i, m in enumerate(mats) if m == "VALIDATED")
        stable = (cls[a] == DRY) & (cls[b] == DRY)
        ref_stack = hv if dual_pol else hh
        diff = ref_stack[b][stable] - ref_stack[a][stable]
        diff = diff[np.isfinite(diff)]
        if diff.size:
            off = float(np.median(diff))
            calibration = {"provisional_date": dates[a], "validated_date": dates[b],
                           "channel": "HV" if dual_pol else "HH", "median_offset_db": round(off, 2),
                           "stable_pixels": int(diff.size), "within_1db": abs(off) < 1.0}
            log(f"[02] calibration offset {dates[a]}→{dates[b]}: {off:+.2f} dB")

    # ---- metrics + overlays ----------------------------------------------------------------
    px_km2 = pixel_area_km2(bounds, rows, cols)
    aoi_dir = store / aoi_id
    ov_dir = aoi_dir / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    for old in ov_dir.glob("*.png"):
        old.unlink()
    paddy_px = (wc == WC_CROPLAND) if wc is not None else np.zeros((rows, cols), bool)

    timeline = []
    for t, g in enumerate(used):
        c = cls[t]
        open_m, fveg_m = c == OPEN_WATER, c == FLOODED_VEG
        paddy_m, natural_m = fveg_m & paddy_px, fveg_m & ~paddy_px
        valid_px = int((c != NODATA_CLASS).sum())
        metrics = {
            "open_water_km2": round(open_m.sum() * px_km2, 2),
            "flooded_veg_km2": round(fveg_m.sum() * px_km2, 2),
            "paddy_like_km2": round(paddy_m.sum() * px_km2, 2),
            "natural_flooded_veg_km2": round(natural_m.sum() * px_km2, 2),
            "dry_km2": round((c == DRY).sum() * px_km2, 2),
            "valid_pixel_pct": round(100.0 * valid_px / c.size, 1),
            "aoi_coverage_pct": coverage[g["date"]],
            "otsu_hh_db": thresholds[g["date"]]["hh_db"],
            "otsu_hv_db": thresholds[g["date"]]["hv_db"],
            "is_reference": t == ref_idx,
        }
        timeline.append({"date": g["date"], "granule_id": g["granule_id"], "track_frame": tf,
                         "polarization": "HH+HV" if dual_pol else "HH", "maturity": g["maturity"],
                         "crid": g["crid"], "metrics": metrics})
        write_png(ov_dir / f"open_water_{g['date']}.png",
                  mask_to_rgba([(open_m, COLOURS["open"], 210)], c.shape))
        write_png(ov_dir / f"flooded_veg_{g['date']}.png",
                  mask_to_rgba([(natural_m, COLOURS["fveg"], 210), (paddy_m, COLOURS["paddy"], 210)], c.shape))

    latest = timeline[-1]["date"]
    (ov_dir / "open_water.png").write_bytes((ov_dir / f"open_water_{latest}.png").read_bytes())
    (ov_dir / "flooded_veg.png").write_bytes((ov_dir / f"flooded_veg_{latest}.png").read_bytes())
    write_png(ov_dir / "hydroperiod.png", hydroperiod_rgba(m_total, n_valid))

    # ---- cube for instant pixel lookup -------------------------------------------------------
    cube = {
        "dates": np.array(dates), "hh_db": hh.astype(np.float16), "cls": cls,
        "m_open": m_open, "m_fveg": m_fveg, "n_valid": n_valid, "ref_index": np.int16(ref_idx),
        "bounds": np.array(bounds, dtype="float64"),
    }
    if dual_pol:
        cube["hv_db"] = hv.astype(np.float16)
    if wc is not None:
        cube["worldcover"] = np.nan_to_num(wc, nan=0).astype(np.int16)
    np.savez_compressed(aoi_dir / "time_series_cube.npz", **cube)

    # ---- manifest ---------------------------------------------------------------------------
    # gmm_regimes / jrc_anomaly are re-added by stage 03 once their overlays exist.
    layers = ["open_water", "flooded_veg", "hydroperiod"]
    if "context_layers" in manifest.get("layers", []):
        layers.append("context_layers")
    manifest.update({
        "track_frame": tf,
        "polarization": "HH+HV" if dual_pol else "HH",
        "single_pol_mode": not dual_pol,
        "fallback_plan": fallback_plan(T, dual_pol),
        "reference_date": dates[ref_idx],
        "layers": layers,
        "timeline": timeline,
        "synthetic_test_data": synthetic,
        "grid": {"rows": rows, "cols": cols, "res_m": res_m, "pixel_area_km2": round(px_km2, 5)},
        "season_summary": {
            "n_dates": T,
            "ever_wet_km2": round(float((m_total > 0).sum() * px_km2), 2),
            "wet_every_observation_km2": round(float(((m_total == n_valid) & (n_valid > 0)).sum() * px_km2), 2),
            "max_wet_observations": int(m_total.max()),
        },
    })
    manifest.pop("_note", None)
    prov = manifest.setdefault("provenance", {})
    prov.update({
        "granules": [g["granule_id"] for g in used],
        "otsu_thresholds": thresholds,
        "delta_hh_params": {"min_delta_hh_db": MIN_DELTA_HH_DB, "min_delta_ratio_db": MIN_DELTA_RATIO_DB},
        "reference_date": dates[ref_idx],
        "calibration_check": calibration,
        "masks": {"vegetation": veg_source, "slope": slope_source,
                  "validity": "GCOV fill (mask==255), non-finite and γ0<=0 excluded"},
        "processing": {"generated_at": now_iso(), "grid_res_m": res_m, "speckle": "multilook + 3x3 median (linear)",
                       "crs_native": sorted(epsgs), "single_pol_mode": not dual_pol,
                       "pipeline": "scripts/02_subset_and_classify_sar.py"},
    })
    lims = prov.setdefault("limitations", [])
    if synthetic:
        msg = "SYNTHETIC TEST DATA — generated for pipeline testing, not a NISAR observation."
        if msg not in lims:
            lims.insert(0, msg)
    if T < 6:
        msg = f"Only {T} same-track dates available — Plan C change comparison, not a full-season hydroperiod."
        if not any(l.startswith("Only ") for l in lims):
            lims.append(msg)
    save_manifest(aoi_id, store, manifest)
    log(f"[02] wrote cube + {len(list(ov_dir.glob('*.png')))} overlays; plan {manifest['fallback_plan']}")
    return manifest
