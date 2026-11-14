"""Deterministic SAR physics (SRS §2, §5.1-5.3). NumPy only."""
from __future__ import annotations

import warnings

import numpy as np

from .common import (LINEAR_FLOOR, MIN_DELTA_HH_DB, MIN_DELTA_RATIO_DB)

NODATA_CLASS = 255
DRY, OPEN_WATER, FLOODED_VEG = 0, 1, 2


def to_db(linear: np.ndarray) -> np.ndarray:
    """γ0 linear -> dB with floor clip at 1e-5 (NaN stays NaN)."""
    linear = np.asarray(linear, dtype="float64")
    out = 10.0 * np.log10(np.clip(linear, LINEAR_FLOOR, None))
    return np.where(np.isnan(linear), np.nan, out)


def ratio_db(hh_db: np.ndarray, hv_db: np.ndarray) -> np.ndarray:
    """dB of the linear HH/HV ratio == HH_dB - HV_dB. Never divide dB values (SRS §2)."""
    return hh_db - hv_db


def median3(a: np.ndarray) -> np.ndarray:
    """NaN-aware 3x3 median speckle filter on LINEAR power (SRS §5.1)."""
    p = np.pad(a, 1, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(p, (3, 3))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = np.nanmedian(win, axis=(-2, -1))
    return np.where(np.isnan(a), np.nan, out)


def box_nanmean(a: np.ndarray, k: int) -> np.ndarray:
    """k x k NaN-aware moving mean (multilooking before resampling to the AOI grid)."""
    if k <= 1:
        return a
    finite = np.isfinite(a)
    v = np.where(finite, a, 0.0).astype("float64")
    n = finite.astype("float64")
    p = k // 2

    def box_sum(x):
        x = np.pad(x, ((p + 1, k - p - 1), (p + 1, k - p - 1)))
        c = x.cumsum(0).cumsum(1)
        return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]

    s, cnt = box_sum(v), box_sum(n)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = s / cnt
    return np.where(cnt > 0, out, np.nan)


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float | None:
    v = np.asarray(values, dtype="float64")
    v = v[np.isfinite(v)]
    if v.size < 50 or v.min() == v.max():
        return None
    hist, edges = np.histogram(v, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m = np.cumsum(hist * centres)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu0 = m / w0
        mu1 = (m[-1] - m) / w1
        between = w0 * w1 * (mu0 - mu1) ** 2
    between = np.nan_to_num(between)
    return float(centres[int(np.argmax(between))])


def dynamic_threshold(db: np.ndarray, rng: tuple[float, float]) -> float:
    """Per-scene Otsu clipped into the SRS physical range."""
    t = otsu_threshold(db)
    if t is None:
        t = (rng[0] + rng[1]) / 2
    return float(min(max(t, rng[0]), rng[1]))


def classify_scene(hh_db, hv_db, hh_ref_db, hv_ref_db, veg_mask, otsu_hh, hv_thresh, valid=None):
    """3-class per-date physics classifier (SRS §5.2).

    Returns uint8: 0 dry/other, 1 open water, 2 possible flooded vegetation, 255 no data.
    hv_db / hv_ref_db may be None -> Single-Pol HH mode (ΔHH surge only, no ratio test).
    ΔRatio(t) = [HH(t) - HV(t)] - [HH(ref) - HV(ref)].
    """
    hh_db = np.asarray(hh_db, dtype="float64")
    single_pol = hv_db is None or hv_ref_db is None
    if valid is None:
        valid = np.isfinite(hh_db) & np.isfinite(hh_ref_db)
        if not single_pol:
            valid &= np.isfinite(hv_db) & np.isfinite(hv_ref_db)

    with np.errstate(invalid="ignore"):
        if single_pol:
            open_water = hh_db < otsu_hh
        else:
            open_water = (hh_db < otsu_hh) & (np.asarray(hv_db) < hv_thresh)
        delta_hh = hh_db - hh_ref_db
        fveg = (~open_water) & veg_mask & (delta_hh >= MIN_DELTA_HH_DB)
        if not single_pol:
            delta_ratio = ratio_db(hh_db, hv_db) - ratio_db(hh_ref_db, hv_ref_db)
            fveg &= delta_ratio >= MIN_DELTA_RATIO_DB

    out = np.full(hh_db.shape, DRY, dtype=np.uint8)
    out[open_water] = OPEN_WATER
    out[fveg] = FLOODED_VEG
    out[~valid] = NODATA_CLASS
    return out


def hydroperiod(cls_stack: np.ndarray):
    """M_open, M_fveg, N_valid per pixel from a (T,R,C) class stack (SRS §5.3)."""
    m_open = (cls_stack == OPEN_WATER).sum(0).astype(np.int16)
    m_fveg = (cls_stack == FLOODED_VEG).sum(0).astype(np.int16)
    n_valid = (cls_stack != NODATA_CLASS).sum(0).astype(np.int16)
    return m_open, m_fveg, n_valid


def slope_deg(dem: np.ndarray, cell_h_m: float, cell_w_m: float) -> np.ndarray:
    gy, gx = np.gradient(dem.astype("float64"), cell_h_m, cell_w_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))
