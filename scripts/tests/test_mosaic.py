"""Multi-frame mosaic path tests (FEAT-001): gcov.mosaic_subsets + process.run(mosaic=True).

(a) Unit-tests mosaic_subsets on small numpy arrays (union coverage, linear-power overlap mean,
    single-frame passthrough).
(b) Integration: writes synthetic track-149 granules — north frames 074/076 + south frame 075 for
    date A and frame 075 only for date B — and asserts the mosaic run unions the frames (a northern
    and a southern pixel both finite with n_valid>0 for date A, date B still processes) while a
    mosaic=False run over the same data keeps the single track/frame behaviour.

Uses only numpy/h5py/pyproj (no rasterio/fastapi), so it runs in the repo venv.
Run:  python -m pytest scripts/tests/test_mosaic.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("h5py")
pytest.importorskip("pyproj")

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from geosar_pipeline import common, gcov, process  # noqa: E402
import make_synthetic_gcov as synth  # noqa: E402

# Gandak-like union bounds [west, south, east, north]; the frames split it N/S.
UNION = [84.00, 26.90, 84.40, 27.60]


def _sub(hh, hv=None, epsg=32645, cov=50.0, spacing=200.0, pols=("HH", "HV")):
    return {"hh": np.asarray(hh, dtype="float64") if hh is not None else None,
            "hv": np.asarray(hv, dtype="float64") if hv is not None else None,
            "epsg": epsg, "native_spacing_m": spacing, "identification": {"trackNumber": 149},
            "polarizations": list(pols), "synthetic": True, "coverage_pct": cov}


# ------------------------------------------------------------------ (a) unit
def test_mosaic_subsets_unions_disjoint_frames():
    north = [[0.01, 0.01], [np.nan, np.nan]]
    south = [[np.nan, np.nan], [0.02, 0.02]]
    m = gcov.mosaic_subsets([_sub(north), _sub(south)])
    assert np.isfinite(m["hh"]).all()                      # union covers every pixel
    assert m["hh"][0, 0] == pytest.approx(0.01)
    assert m["hh"][1, 0] == pytest.approx(0.02)
    assert m["epsg"] == [32645]
    assert m["coverage_pct"] == 100.0
    assert len(m["frames"]) == 2


def test_mosaic_subsets_averages_overlap_in_linear_power():
    a = [[0.01, np.nan]]
    b = [[0.03, np.nan]]
    m = gcov.mosaic_subsets([_sub(a), _sub(b)])
    assert m["hh"][0, 0] == pytest.approx(0.02)            # (0.01 + 0.03) / 2 in LINEAR power
    assert not np.isfinite(m["hh"][0, 1])


def test_mosaic_subsets_single_frame_preserved():
    only = [[0.05, np.nan], [0.07, 0.09]]
    m = gcov.mosaic_subsets([_sub(only)])
    np.testing.assert_array_equal(np.nan_to_num(m["hh"], nan=-1.0),
                                  np.nan_to_num(np.asarray(only), nan=-1.0))
    assert m["hv"] is None


# ------------------------------------------------------------------ (b) integration
def _name(cycle: int, frame: int, date: str) -> str:
    stamp = date.replace("-", "")
    return (f"NISAR_L2_PR_GCOV_{cycle:03d}_149_D_{frame:03d}_2005_DHDH_M_"
            f"{stamp}T135735_{stamp}T135809_P05023_N_F_J_001.h5")


@pytest.fixture
def mosaic_dir(tmp_path):
    midlat = (UNION[1] + UNION[3]) / 2
    north = [UNION[0], midlat, UNION[2], UNION[3]]
    south = [UNION[0], UNION[1], UNION[2], midlat]
    d = tmp_path / "h5"
    d.mkdir()
    # date A (2026-09-04): frames 074 + 076 cover the NORTH sub-band, frame 075 the SOUTH sub-band
    for frame, seed in ((74, 1), (76, 2)):
        synth.write_granule(d / _name(32, frame, "2026-09-04"), _name(32, frame, "2026-09-04"),
                            north, spacing_m=200.0, seed=seed)
    synth.write_granule(d / _name(32, 75, "2026-09-04"), _name(32, 75, "2026-09-04"),
                        south, spacing_m=200.0, seed=3)
    # date B (2026-09-28): frame 075 only (SOUTH)
    synth.write_granule(d / _name(34, 75, "2026-09-28"), _name(34, 75, "2026-09-28"),
                        south, spacing_m=200.0, seed=4)
    return d


def test_mosaic_run_unions_frames(mosaic_dir, tmp_path):
    aoi = "aoi_mosaic_test"
    common.AOI_BOUNDS[aoi] = UNION
    store = tmp_path / "store"
    m = process.run(aoi, mosaic_dir, store, mosaic=True, res_m=2000.0, log=lambda *_: None)

    dates = [t["date"] for t in m["timeline"]]
    assert dates == ["2026-09-04", "2026-09-28"]           # date B (single frame) still processes
    assert m["track_frame"] == "track-149 mosaic"
    assert {t["track_frame"] for t in m["timeline"]} == {"track-149 mosaic"}

    with np.load(store / aoi / "time_series_cube.npz") as z:
        hh, cls, n_valid = z["hh_db"], z["cls"], z["n_valid"]
    rows, cols = cls.shape[1:]
    north_r, south_r, c = int(rows * 0.1), int(rows * 0.9), cols // 2
    a = dates.index("2026-09-04")
    assert np.isfinite(hh[a, north_r, c]), "northern pixel should be covered by frames 074/076"
    assert np.isfinite(hh[a, south_r, c]), "southern pixel should be covered by frame 075"
    assert cls[a, north_r, c] != 255 and cls[a, south_r, c] != 255
    assert n_valid[north_r, c] > 0 and n_valid[south_r, c] > 0

    prov = m["provenance"]["mosaic"]
    assert len(prov["dates"]["2026-09-04"]["frames"]) == 3
    assert len(prov["dates"]["2026-09-28"]["frames"]) == 1
    assert any(l.startswith("Multi-frame mosaic:") for l in m["provenance"]["limitations"])


def test_mosaic_false_keeps_single_frame_behaviour(mosaic_dir, tmp_path):
    aoi = "aoi_mosaic_test_single"
    common.AOI_BOUNDS[aoi] = UNION
    store = tmp_path / "store_single"
    m = process.run(aoi, mosaic_dir, store, mosaic=False, res_m=2000.0, log=lambda *_: None)

    # select_best_track groups by track_frame; frame 075 has the most dates, so it is chosen.
    assert m["track_frame"] == "149/075"
    assert {t["track_frame"] for t in m["timeline"]} == {"149/075"}
    assert [t["date"] for t in m["timeline"]] == ["2026-09-04", "2026-09-28"]
    assert "mosaic" not in m["provenance"]
