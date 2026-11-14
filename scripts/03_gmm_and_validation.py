"""03 — GMM regimes + OPERA DSWx / JRC validation (SRS §5.4-5.5, §9 Phase 2).

Runs an unsupervised 5-cluster Gaussian Mixture Model on each pixel's temporal
SAR feature vector, maps clusters to the 5 named hydrological regimes, computes
OPERA DSWx-S1/NI inter-sensor agreement %, and JRC occurrence context.

Owner: Sakshi (@sakshitayade)

Feature vector per pixel (SRS §5.4):
    x = [mean(HH), min(HH), max(dHH), mean(HH-HV), M_open/N, M_fveg/N]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from sklearn.mixture import GaussianMixture

DATA_STORE = Path(__file__).resolve().parent.parent / "services" / "api" / "data_store"

REGIME_NAMES = [
    "Permanent River / Deep Channel",
    "Seasonal Open Floodplain / Beel",
    "Seasonally Flooded Canopy / Tall Grassland",
    "Seasonal Paddy-Like Inundation Cycle",
    "Stable Dry Upland / Levee",
]


def fit_gmm(features: np.ndarray, k: int = 5) -> np.ndarray:
    """features: (n_pixels, 6) -> cluster index per pixel."""
    gmm = GaussianMixture(n_components=k, covariance_type="full", random_state=42)
    return gmm.fit_predict(features)


def dswx_agreement(nisar_open: np.ndarray, dswx_open: np.ndarray) -> float:
    """Spatial agreement % on open-water class (inter-sensor agreement, NOT accuracy)."""
    valid = ~np.isnan(nisar_open) & ~np.isnan(dswx_open)
    if valid.sum() == 0:
        return float("nan")
    agree = (nisar_open[valid] == dswx_open[valid]).sum()
    return round(100.0 * agree / valid.sum(), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", required=True)
    parser.parse_args()
    # TODO(Phase 2): load time_series_cube.npz, build feature matrix, fit_gmm,
    #   order clusters into REGIME_NAMES by hydrology, load temporally-nearest
    #   OPERA DSWx granule for agreement %, intersect JRC occurrence (<20% = unusual),
    #   and write results back into cube + manifest provenance.
    print("[03] SCAFFOLD: implement GMM + DSWx/JRC validation in Phase 2.")
    print(f"      Regimes -> {REGIME_NAMES}")


if __name__ == "__main__":
    main()
