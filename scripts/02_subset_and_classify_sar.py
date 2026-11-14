"""02 — Subset, speckle-filter, classify, hydroperiod (SRS §2, §5.1-5.3, §9 Phase 2).

For each locked granule: stream+subset gamma0 HH/HV to the AOI box, mask
(validity + layover/shadow + DEM slope >5deg), 3x3 median/Lee speckle filter on
LINEAR power, floor-clip 1e-5, convert to dB, run the 3-class physics classifier,
and accumulate the M-of-N hydroperiod. Emits RGBA PNG overlays + time_series_cube.npz.

Owner: Kaushik (@kaushik7) + Himanshu (@lunar_node)

CRITICAL dB rule (SRS §2): Ratio_dB = HH_dB - HV_dB  (never divide negative dB).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

DATA_STORE = Path(__file__).resolve().parent.parent / "services" / "api" / "data_store"

MIN_DELTA_HH_DB = 3.0      # double-bounce surge threshold
MIN_DELTA_RATIO_DB = 1.5
OTSU_HH_RANGE_DB = (-22.0, -13.0)
LINEAR_FLOOR = 1e-5


def to_db(linear: np.ndarray) -> np.ndarray:
    return 10.0 * np.log10(np.clip(linear, LINEAR_FLOOR, None))


def ratio_db(hh_db: np.ndarray, hv_db: np.ndarray) -> np.ndarray:
    # Subtraction in dB space — correct form of the HH/HV linear ratio.
    return hh_db - hv_db


def classify_scene(hh_db, hv_db, hh_ref_db, veg_mask, otsu_hh, hv_thresh):
    """3-class per-date classifier (SRS §5.2). Returns int array: 0=dry,1=open,2=fveg."""
    out = np.zeros(hh_db.shape, dtype=np.uint8)
    open_water = (hh_db < otsu_hh) & (hv_db < hv_thresh)
    delta_hh = hh_db - hh_ref_db
    delta_ratio = ratio_db(hh_db, hv_db) - ratio_db(hh_ref_db, hv_db)
    fveg = (~open_water) & veg_mask & (delta_hh >= MIN_DELTA_HH_DB) & (delta_ratio >= MIN_DELTA_RATIO_DB)
    out[open_water] = 1
    out[fveg] = 2
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", required=True)
    parser.parse_args()
    # TODO(Phase 2): iterate locked granules, read HH/HV via rasterio/h5py windowed
    #   reads, apply masks + speckle filter, dynamic Otsu in OTSU_HH_RANGE_DB,
    #   classify each date, stack M_open/M_fveg/N_valid, write overlays + npz.
    print("[02] SCAFFOLD: implement subset/classify/hydroperiod in Phase 2.")
    print(f"      Thresholds -> dHH>={MIN_DELTA_HH_DB}dB, dRatio>={MIN_DELTA_RATIO_DB}dB, Otsu range={OTSU_HH_RANGE_DB}")


if __name__ == "__main__":
    main()
