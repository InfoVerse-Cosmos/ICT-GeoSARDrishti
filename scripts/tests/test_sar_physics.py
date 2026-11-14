"""Offline SAR physics pipeline (scripts/02, scripts/03).

SRS refs: §2 (dB math rule), §5.1 (floor clip, dB), §5.2 (3-class classifier),
§5.4 (GMM k=5), §5.5 (DSWx inter-sensor agreement).
Run from repo root:  python -m pytest scripts/tests -v
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), SCRIPTS / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s02 = _load("02_subset_and_classify_sar.py")


# ---------------------------------------------------------------- constants match SRS
def test_thresholds_match_srs():
    assert s02.MIN_DELTA_HH_DB == 3.0
    assert s02.MIN_DELTA_RATIO_DB == 1.5
    assert s02.OTSU_HH_RANGE_DB == (-22.0, -16.0)  # capped at SRS §2 typical open water, see common.py
    assert s02.LINEAR_FLOOR == 1e-5


# ---------------------------------------------------------------- dB conversion (§5.1)
@pytest.mark.parametrize("linear,expected_db", [(1.0, 0.0), (0.1, -10.0), (0.01, -20.0), (10.0, 10.0)])
def test_to_db(linear, expected_db):
    assert s02.to_db(np.array([linear]))[0] == pytest.approx(expected_db)


@pytest.mark.parametrize("bad", [0.0, -0.5, 1e-9])
def test_to_db_floor_clip_avoids_minus_inf_and_nan(bad):
    out = s02.to_db(np.array([bad]))
    assert np.isfinite(out).all()
    assert out[0] == pytest.approx(-50.0)


# ---------------------------------------------------------------- dB ratio rule (§2)
def test_ratio_is_subtraction_in_db_space():
    hh_lin, hv_lin = 0.05, 0.005
    hh_db, hv_db = s02.to_db(np.array([hh_lin])), s02.to_db(np.array([hv_lin]))
    # dB of linear ratio == HH_dB - HV_dB  (never divide dB values)
    assert s02.ratio_db(hh_db, hv_db)[0] == pytest.approx(10 * np.log10(hh_lin / hv_lin))
    assert s02.ratio_db(hh_db, hv_db)[0] != pytest.approx(hh_db[0] / hv_db[0])


# ---------------------------------------------------------------- 3-class classifier (§5.2)
OTSU, HV_T = -16.0, -22.0
VEG, NOVEG = np.array([True]), np.array([False])


def _px(v):
    return np.array([v], dtype=float)


def classify(hh, hv, hh_ref, hv_ref, veg=VEG):
    return s02.classify_scene(_px(hh), None if hv is None else _px(hv), _px(hh_ref),
                              None if hv_ref is None else _px(hv_ref), veg, OTSU, HV_T)[0]


def test_open_water_is_class_1():
    assert classify(-20.0, -26.0, -12.0, -18.0) == 1


def test_open_water_requires_both_hh_and_hv_dark():
    assert classify(-20.0, -15.0, -12.0, -18.0, NOVEG) == 0


def test_double_bounce_inside_veg_mask_is_class_2():
    # HH -11.8 -> -7.2 (+4.6 dB), HV steady -> ΔRatio +4.6 dB
    assert classify(-7.2, -18.0, -11.8, -18.0) == 2


def test_double_bounce_outside_veg_mask_is_dry():
    assert classify(-7.2, -18.0, -11.8, -18.0, NOVEG) == 0


def test_surge_below_3db_is_dry():
    assert classify(-9.5, -18.0, -11.8, -18.0) == 0


def test_surge_exactly_3db_is_inclusive():
    assert classify(-8.8, -18.0, -11.8, -18.0) == 2


def test_open_water_takes_precedence_over_flooded_veg():
    assert classify(-25.0, -30.0, -30.0, -30.0) == 1


def test_delta_ratio_uses_reference_hv():
    """HH and HV BOTH +4 dB (crop growth / volume scattering): ΔRatio = 0 -> NOT flooded veg."""
    assert classify(-7.8, -14.0, -11.8, -18.0) == 0


def test_delta_ratio_below_1_5db_is_dry():
    # ΔHH +4 dB but HV +3 dB -> ΔRatio +1 dB < 1.5
    assert classify(-7.8, -15.0, -11.8, -18.0) == 0


def test_single_pol_mode_uses_hh_only():
    assert classify(-20.0, None, -12.0, None) == 1          # HH below Otsu -> open water
    assert classify(-7.2, None, -11.8, None) == 2           # ΔHH surge only
    assert classify(-10.0, None, -11.8, None) == 0


def test_nan_pixels_are_nodata():
    assert classify(np.nan, -18.0, -11.8, -18.0) == 255


def test_classifier_output_shape_and_dtype():
    shape = (4, 5)
    out = s02.classify_scene(np.full(shape, -10.0), np.full(shape, -18.0), np.full(shape, -10.0),
                             np.full(shape, -18.0), np.ones(shape, bool), OTSU, HV_T)
    assert out.shape == shape and out.dtype == np.uint8
    assert set(np.unique(out)) <= {0, 1, 2}


# ---------------------------------------------------------------- scripts/03 (§5.4, §5.5)
@pytest.fixture(scope="module")
def s03():
    pytest.importorskip("sklearn")
    return _load("03_gmm_and_validation.py")


def test_regime_names_match_srs(s03):
    assert s03.REGIME_NAMES == [
        "Permanent River / Deep Channel",
        "Seasonal Open Floodplain / Beel",
        "Seasonally Flooded Canopy / Tall Grassland",
        "Seasonal Paddy-Like Inundation Cycle",
        "Stable Dry Upland / Levee",
    ]


def test_gmm_finds_five_regimes_deterministically(s03):
    rng = np.random.default_rng(0)
    centres = np.array([
        [-22, -25, 0.5, 6, 1.0, 0.0],   # permanent river
        [-14, -22, 1.0, 6, 0.6, 0.0],   # seasonal beel
        [-9, -12, 4.5, 9, 0.1, 0.6],    # flooded canopy
        [-11, -18, 3.5, 8, 0.3, 0.3],   # paddy cycle
        [-7, -9, 0.5, 5, 0.0, 0.0],     # dry upland
    ])
    X = np.vstack([c + rng.normal(0, 0.2, (200, 6)) for c in centres])
    a, b = s03.fit_gmm(X, k=5), s03.fit_gmm(X, k=5)
    assert len(np.unique(a)) == 5
    assert (a == b).all(), "random_state must make regimes reproducible"
    for i in range(5):  # each synthetic blob maps to one cluster
        assert len(np.unique(a[i * 200:(i + 1) * 200])) == 1


@pytest.mark.parametrize("nisar,dswx,expected", [
    ([1, 1, 0, 0], [1, 1, 0, 0], 100.0),
    ([1, 1, 0, 0], [1, 0, 1, 0], 50.0),
    ([1, np.nan, 0, 0], [1, 1, np.nan, 1], 50.0),   # NaNs excluded
])
def test_dswx_agreement(s03, nisar, dswx, expected):
    assert s03.dswx_agreement(np.array(nisar, float), np.array(dswx, float)) == expected


def test_dswx_agreement_all_invalid_is_nan(s03):
    assert np.isnan(s03.dswx_agreement(np.array([np.nan]), np.array([np.nan])))


def test_dswx_docstring_says_inter_sensor_not_accuracy(s03):
    doc = s03.dswx_agreement.__doc__.lower()
    assert "inter-sensor agreement" in doc and "not accuracy" in doc
