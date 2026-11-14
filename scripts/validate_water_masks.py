"""Independent check of our radar water masks against ESA WorldCover (class 80, 2021) and EC-JRC Global Surface Water occurrence, read live from the internet. Run from repo root: python scripts/validate_water_masks.py"""
import json
import sys

import numpy as np
import rasterio

sys.path.insert(0, "scripts")
from geosar_pipeline.common import sample_geotiff

WC = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
JRC = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{}v1_4_2021.tif"
CFG = {
    "aoi_assam_majuli": (["N24E093", "N27E093"], "90E_30N"),
    "aoi_nagpur_kanhan": (["N21E078"], "70E_30N"),
}
root = "services/api/data_store/"
env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="4",
           GDAL_HTTP_RETRY_DELAY="2", GDAL_HTTP_TIMEOUT="60")
with rasterio.Env(**env):
    for aoi, (wc_tiles, jrc_tile) in CFG.items():
        z = np.load(root + aoi + "/time_series_cube.npz")
        m = json.load(open(root + aoi + "/manifest.json", encoding="utf-8"))
        w, s, e, n = m["bounds"]
        cls = z["cls"]
        T, rows, cols = cls.shape
        lats = n - (np.arange(rows) + 0.5) * (n - s) / rows
        lons = w + (np.arange(cols) + 0.5) * (e - w) / cols
        dates = [str(d) for d in z["dates"]]
        print(f"\n===== {aoi}  dates {dates}")
        wc = np.full((rows, cols), np.nan, dtype="float32")
        for t in wc_tiles:
            a = sample_geotiff(WC.format(t), lats, lons)
            wc = np.where(np.isnan(wc), a, wc)
        jrc = sample_geotiff(JRC.format(jrc_tile), lats, lons)
        wc_water = wc == 80
        print(f"  ESA WorldCover permanent-water (2021) in AOI: {wc_water.sum()*0.01:.1f} km2 | coverage of tiles: {np.isfinite(wc).mean():.0%}")
        jrc_ok = np.isfinite(jrc)
        print(f"  JRC occurrence coverage: {jrc_ok.mean():.0%} | JRC occurrence >=75%: {(jrc >= 75).sum()*0.01:.1f} km2 | >=50%: {(jrc >= 50).sum()*0.01:.1f} km2")
        dry_i = len(dates) - 1                                         # the VALIDATED dry-reference scene
        open_all = cls == 1
        for label, mask in ((f"open water {dates[dry_i]} (dry reference)", open_all[dry_i]),
                            (f"open water {dates[1]} (peak)", open_all[1]),
                            ("open on ALL dates (permanent)", open_all.all(0))):
            if mask.sum() == 0:
                print(f"  {label}: 0 px")
                continue
            in_wc = (wc_water & mask).sum() / mask.sum()
            jv = jrc[mask & jrc_ok]
            print(f"  {label}: {mask.sum()*0.01:6.1f} km2 | {in_wc:5.0%} also WorldCover water | JRC occurrence median {np.median(jv):.0f}% , "
                  f"{(jv >= 50).mean():.0%} of them have JRC occurrence >= 50%, {(jv >= 25).mean():.0%} >= 25%")
        hi = (jrc >= 75)
        if hi.sum():
            rec = (open_all.any(0) & hi).sum() / hi.sum()
            rec_d = (open_all[dry_i] & hi).sum() / hi.sum()
            print(f"  JRC high-occurrence water (>=75%): {rec:.0%} is open on at least one of our dates, {rec_d:.0%} on {dates[dry_i]}")
        # land check: how much of our 'dry upland' regime is WorldCover water? (false-negative sanity)
        never = ~open_all.any(0)
        print(f"  pixels never open in our stack that WorldCover calls water: {(wc_water & never).sum()*0.01:.1f} km2 "
              f"({(wc_water & never).sum() / max(wc_water.sum(),1):.0%} of WorldCover water)")
