"""02 — Subset, speckle-filter, classify, hydroperiod (SRS §2, §5.1-5.3, §9 Phase 2).

For each same-track granule: read only the AOI window of γ0 HH/HV from the GCOV
HDF5, multilook onto a ~100 m AOI lat/lon grid, 3x3 median speckle filter on
LINEAR power, floor-clip 1e-5, convert to dB, dynamic Otsu per scene, run the
3-class physics classifier against the post-monsoon dry reference, accumulate
the M-of-N hydroperiod, and emit:
    data_store/<aoi>/time_series_cube.npz
    data_store/<aoi>/overlays/{open_water,flooded_veg}_<date>.png, hydroperiod.png
    data_store/<aoi>/manifest.json   (timeline + per-date metrics + provenance)

Owner: Kaushik (@kaushik7) + Himanshu (@lunar_node)

CRITICAL dB rule (SRS §2): Ratio_dB = HH_dB - HV_dB  (never divide negative dB).

Example:
    python scripts/02_subset_and_classify_sar.py --aoi aoi_assam_majuli --h5-dir D:/nisar \
        [--track-frame 063/076] [--ref-date 2026-11-02] [--worldcover wc.tif] [--dem dem.tif]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline.common import (AOI_BOUNDS, LINEAR_FLOOR, MIN_DELTA_HH_DB,  # noqa: E402,F401
                                    MIN_DELTA_RATIO_DB, OTSU_HH_RANGE_DB, data_store)
from geosar_pipeline.physics import classify_scene, ratio_db, to_db  # noqa: E402,F401
from geosar_pipeline import process  # noqa: E402

DATA_STORE = data_store()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi", required=True, choices=list(AOI_BOUNDS))
    p.add_argument("--h5-dir", required=True, help="folder holding the GCOV .h5 granules")
    p.add_argument("--track-frame", help="force a track/frame (default: longest same-track stack)")
    p.add_argument("--ref-date", help="dry reference date (default: latest acquisition)")
    p.add_argument("--res-m", type=float, default=100.0, help="output grid resolution in metres")
    p.add_argument("--worldcover", help="ESA WorldCover GeoTIFF (vegetation mask + paddy sub-label)")
    p.add_argument("--dem", help="Copernicus DEM GeoTIFF (slope > 5° mask)")
    p.add_argument("--data-store", help="override data_store dir")
    args = p.parse_args()

    m = process.run(args.aoi, args.h5_dir, data_store(args.data_store), track_frame=args.track_frame,
                    ref_date=args.ref_date, res_m=args.res_m, worldcover=args.worldcover, dem=args.dem)
    for t in m["timeline"]:
        mt = t["metrics"]
        print(f"   {t['date']} {t['maturity']:<11} open={mt['open_water_km2']:>7} km²  "
              f"fveg={mt['flooded_veg_km2']:>7} km²  valid={mt['valid_pixel_pct']}%")


if __name__ == "__main__":
    main()
