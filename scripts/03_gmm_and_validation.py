"""03 — GMM regimes + OPERA DSWx / JRC validation (SRS §5.4-5.5, §9 Phase 2).

Runs an unsupervised Gaussian Mixture Model (k=5) on each pixel's temporal SAR
feature vector, maps clusters to the 5 named hydrological regimes, and
(optionally) computes OPERA DSWx inter-sensor agreement and the JRC
"unusual open water" layer.

Owner: Sakshi (@sakshitayade)

Feature vector per pixel (SRS §5.4):
    x = [mean(HH), min(HH), max(dHH), mean(HH-HV), M_open/N, M_fveg/N]

Example:
    python scripts/03_gmm_and_validation.py --aoi aoi_assam_majuli \
        [--jrc occurrence_90E_30N.tif] [--dswx OPERA_L3_DSWx-S1_..._WTR.tif --dswx-date 2026-10-16]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline.common import AOI_BOUNDS, REGIME_NAMES, data_store  # noqa: E402,F401
from geosar_pipeline import regimes  # noqa: E402
from geosar_pipeline.regimes import fit_gmm  # noqa: E402,F401

DATA_STORE = data_store()


def dswx_agreement(nisar_open: np.ndarray, dswx_open: np.ndarray) -> float:
    """Spatial agreement % on open-water class (inter-sensor agreement, NOT accuracy)."""
    valid = ~np.isnan(nisar_open) & ~np.isnan(dswx_open)
    if valid.sum() == 0:
        return float("nan")
    agree = (nisar_open[valid] == dswx_open[valid]).sum()
    return round(100.0 * agree / valid.sum(), 1)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi", required=True, choices=list(AOI_BOUNDS))
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--jrc", help="JRC Global Surface Water occurrence GeoTIFF")
    p.add_argument("--dswx", help="OPERA DSWx-S1/NI WTR GeoTIFF")
    p.add_argument("--dswx-date", help="DSWx acquisition date (YYYY-MM-DD); nearest NISAR date is compared")
    p.add_argument("--data-store", help="override data_store dir")
    args = p.parse_args()
    regimes.run(args.aoi, data_store(args.data_store), k=args.k, jrc=args.jrc, dswx=args.dswx,
                dswx_date=args.dswx_date)


if __name__ == "__main__":
    main()
