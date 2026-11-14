"""Stage 03 — GMM hydrological regimes + OPERA DSWx agreement + JRC anomaly (SRS §5.4, §5.5)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .common import (JRC_UNUSUAL_PCT, REGIME_NAMES, WC_CROPLAND, load_manifest, mask_to_rgba, now_iso,
                     pixel_area_km2, sample_geotiff, save_manifest, write_png, aoi_grid)
from .physics import NODATA_CLASS, OPEN_WATER

REGIME_COLOURS = ["#1E3A8A", "#0284C7", "#10B981", "#F59E0B", "#94A3B8"]
REGIME_ALPHA = [220, 200, 200, 200, 70]


def load_cube(store: Path, aoi_id: str) -> dict:
    with np.load(store / aoi_id / "time_series_cube.npz", allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def save_cube(store: Path, aoi_id: str, cube: dict) -> None:
    np.savez_compressed(store / aoi_id / "time_series_cube.npz", **cube)


def build_features(cube: dict):
    """x = [mean HH, min HH, max ΔHH, mean(HH-HV), M_open/N, M_fveg/N] per valid pixel (SRS §5.4)."""
    hh = cube["hh_db"].astype("float64")
    ref = int(cube.get("ref_index", hh.shape[0] - 1))
    n = cube["n_valid"].astype("float64")
    valid = n > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_hh = np.nanmean(hh, 0)
            min_hh = np.nanmin(hh, 0)
            max_dhh = np.nanmax(hh - hh[ref], 0)
            if "hv_db" in cube:
                mean_ratio = np.nanmean(hh - cube["hv_db"].astype("float64"), 0)
            else:
                mean_ratio = np.zeros_like(mean_hh)
        f_open = cube["m_open"] / np.maximum(n, 1)
        f_fveg = cube["m_fveg"] / np.maximum(n, 1)
    X = np.stack([mean_hh, min_hh, max_dhh, mean_ratio, f_open, f_fveg], -1)
    valid &= np.isfinite(X).all(-1)
    return X, valid


def fit_gmm(features: np.ndarray, k: int = 5, seed: int = 42) -> np.ndarray:
    from sklearn.mixture import GaussianMixture
    gmm = GaussianMixture(n_components=k, covariance_type="full", random_state=seed, reg_covar=1e-3)
    return gmm.fit_predict(features)


DRY_WET_FRACTION = 0.15      # cluster wet in <15 % of observations on average -> dry
PERMANENT_OPEN_FRACTION = 0.9


def map_clusters_to_regimes(X: np.ndarray, labels: np.ndarray, cropland: np.ndarray | None) -> dict[int, int]:
    """Evidence-driven mapping cluster -> REGIME_NAMES index (deterministic, several clusters may share
    a regime because the GMM often splits a large class such as dry upland):

      wet fraction < 15 %                       -> Stable Dry Upland / Levee
      open-dominant, open in >= 90 % of obs     -> Permanent River / Deep Channel
      open-dominant otherwise                   -> Seasonal Open Floodplain / Beel
      flooded-veg-dominant, mostly cropland     -> Seasonal Paddy-Like Inundation Cycle
      flooded-veg-dominant otherwise            -> Seasonally Flooded Canopy / Tall Grassland
    """
    mapping: dict[int, int] = {}
    for c in np.unique(labels):
        sel = labels == c
        f_open, f_fveg = float(X[sel, 4].mean()), float(X[sel, 5].mean())
        crop = float(cropland[sel].mean()) if cropland is not None else 0.0
        if f_open + f_fveg < DRY_WET_FRACTION:
            mapping[int(c)] = 4
        elif f_open >= f_fveg:
            mapping[int(c)] = 0 if f_open >= PERMANENT_OPEN_FRACTION else 1
        else:
            mapping[int(c)] = 3 if crop >= 0.5 else 2
    return mapping


def run(aoi_id: str, store: Path, *, k: int = 5, jrc: str | None = None, dswx: str | None = None,
        dswx_date: str | None = None, log=print) -> dict:
    manifest = load_manifest(aoi_id, store)
    cube = load_cube(store, aoi_id)
    rows, cols = cube["n_valid"].shape
    bounds = manifest["bounds"]
    _, _, lats, lons = aoi_grid(bounds, manifest.get("grid", {}).get("res_m", 100))
    if len(lats) != rows or len(lons) != cols:  # recompute grid from cube shape
        lats = bounds[3] - (np.arange(rows) + 0.5) * (bounds[3] - bounds[1]) / rows
        lons = bounds[0] + (np.arange(cols) + 0.5) * (bounds[2] - bounds[0]) / cols
    px_km2 = pixel_area_km2(bounds, rows, cols)
    ov_dir = store / aoi_id / "overlays"
    prov = manifest.setdefault("provenance", {})
    layers = manifest.setdefault("layers", [])

    # ---- GMM regimes ---------------------------------------------------------------------
    X, valid = build_features(cube)
    # Two-stage regimes (so the GMM is not wasted on dry land, which dominates a few-date stack):
    #   1) pixels never wet in any valid observation are "Stable Dry Upland / Levee" by definition;
    #   2) a GMM (k = 4) clusters the ever-wet pixels into the four wet regimes.
    ever_wet = (cube["m_open"] + cube["m_fveg"]) > 0
    sel_wet = valid & ever_wet
    Xv = X[sel_wet]
    gmm_map = np.full((rows, cols), -1, dtype=np.int8)
    gmm_map[valid & ~ever_wet] = 4
    k_eff = 0
    if Xv.shape[0] >= 1:
        mu, sd = Xv.mean(0), Xv.std(0)
        sd[sd == 0] = 1
        Z = (Xv - mu) / sd
        k_eff = max(1, min(k - 1, Xv.shape[0] // 15))
        labels = fit_gmm(Z, k_eff) if k_eff > 1 else np.zeros(Xv.shape[0], dtype=int)
        crop = (cube["worldcover"][sel_wet] == WC_CROPLAND).astype(float) if "worldcover" in cube else None
        mapping = map_clusters_to_regimes(Xv, labels, crop)
        gmm_map[sel_wet] = np.vectorize(mapping.get)(labels)
        if "worldcover" in cube:  # SRS §5.2 per-pixel sub-label: flooded canopy on cropland -> paddy cycle
            gmm_map[(gmm_map == 2) & (cube["worldcover"] == WC_CROPLAND)] = 3
    if valid.any():
        cube["gmm"] = gmm_map
        write_png(ov_dir / "gmm_regimes.png", mask_to_rgba(
            [(gmm_map == i, REGIME_COLOURS[i], REGIME_ALPHA[i]) for i in range(5)], (rows, cols)))
        prov["gmm"] = {
            "k": int(k_eff) + 1, "k_wet_gmm": int(k_eff),
            "method": "never-wet pixels = Stable Dry Upland by definition; GMM clusters the ever-wet pixels",
            "features": ["mean_HH", "min_HH", "max_dHH", "mean_HH-HV", "M_open/N", "M_fveg/N"],
            "random_state": 42,
            "regime_area_km2": {REGIME_NAMES[i]: round(float((gmm_map == i).sum() * px_km2), 2) for i in range(5)},
            "mapping_rule": "wet<15%→Dry Upland; open-dominant & open≥90%→Permanent River; "
                            "open-dominant→Beel; flooded-veg-dominant & cropland≥50%→Paddy cycle; "
                            "else→Flooded Canopy",
        }
        if "gmm_regimes" not in layers:
            layers.append("gmm_regimes")
        log(f"[03] regimes (dry by definition + GMM k={k_eff} on wet pixels): {prov['gmm']['regime_area_km2']}")
    else:
        log("[03] too few valid pixels for GMM — skipped")

    cls = cube["cls"]
    ever_open = (cls == OPEN_WATER).any(0)

    # ---- JRC historical context (open water only, SRS §3.2) -----------------------------------
    if jrc:
        occ = sample_geotiff(jrc, lats, lons)
        cube["jrc"] = np.nan_to_num(occ, nan=0).astype(np.float32)
        unusual = ever_open & (np.nan_to_num(occ, nan=0) < JRC_UNUSUAL_PCT)
        write_png(ov_dir / "jrc_anomaly.png", mask_to_rgba(
            [(ever_open & ~unusual, "#0284C7", 90), (unusual, "#EF4444", 220)], (rows, cols)))
        prov["jrc"] = {
            "unusual_threshold_pct": JRC_UNUSUAL_PCT,
            "open_water_ever_km2": round(float(ever_open.sum() * px_km2), 2),
            "unusual_open_water_km2": round(float(unusual.sum() * px_km2), 2),
            "unusual_share_pct": round(100.0 * unusual.sum() / max(ever_open.sum(), 1), 1),
            "note": "Compared against Open-Water class only; optical JRC never sees water under canopy.",
        }
        if "jrc_anomaly" not in layers:
            layers.append("jrc_anomaly")
        log(f"[03] JRC: {prov['jrc']}")

    # ---- OPERA DSWx inter-sensor agreement --------------------------------------------------
    if dswx:
        dates = [str(d) for d in cube["dates"]]
        target = dswx_date or dates[-1]
        t = min(range(len(dates)), key=lambda i: abs(np.datetime64(dates[i]) - np.datetime64(target)))
        v = sample_geotiff(dswx, lats, lons)
        dswx_valid = np.isin(v, [0, 1, 2])          # 0 not water, 1 open water, 2 partial; >=250 masks
        nisar_valid = cls[t] != NODATA_CLASS
        both = dswx_valid & nisar_valid
        nisar_open = cls[t] == OPEN_WATER
        dswx_open = v == 1
        agree = float((nisar_open[both] == dswx_open[both]).mean() * 100) if both.any() else None
        inter = (nisar_open & dswx_open & both).sum()
        union = ((nisar_open | dswx_open) & both).sum()
        prov["opera_dswx_agreement_pct"] = None if agree is None else round(agree, 1)
        lims = prov.setdefault("limitations", [])
        if not any("inter-sensor" in l for l in lims):
            lims.append("OPERA agreement is inter-sensor agreement, not ground-truth accuracy.")
        prov["opera_dswx"] = {
            "file": Path(dswx).name, "dswx_date": target, "nisar_date": dates[t],
            "compared_pixels": int(both.sum()),
            "agreement_pct": prov["opera_dswx_agreement_pct"],
            "open_water_iou_pct": round(100.0 * inter / union, 1) if union else None,
            "note": "Inter-sensor agreement, not ground-truth accuracy.",
        }
        for entry in manifest.get("timeline", []):
            if entry["date"] == dates[t]:
                entry.setdefault("metrics", {})["dswx_agreement_pct"] = prov["opera_dswx_agreement_pct"]
        log(f"[03] DSWx agreement {prov['opera_dswx_agreement_pct']}% on {dates[t]}")

    prov.setdefault("processing", {})["stage03_at"] = now_iso()
    save_cube(store, aoi_id, cube)
    save_manifest(aoi_id, store, manifest)
    return manifest
