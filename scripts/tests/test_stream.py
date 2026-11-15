"""Window maths + mini-granule compatibility for NASA window streaming (no network)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geosar_pipeline import gcov, stream  # noqa: E402


def _grid(epsg=32646, x0=400000.0, y0=3000000.0, n=3000, d=10.0):
    return x0 + d * np.arange(n), y0 - d * np.arange(n), epsg


def test_window_covers_the_bbox_with_padding():
    from pyproj import Transformer
    x, y, epsg = _grid()
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(x[1500], y[1500])
    bbox = [lon - 0.02, lat - 0.02, lon + 0.02, lat + 0.02]
    r0, r1, c0, c1 = stream.window_for_bbox(x, y, epsg, bbox, pad=40)
    assert 0 <= r0 < 1500 < r1 <= 3000 and 0 <= c0 < 1500 < c1 <= 3000
    assert (r1 - r0) > 300 and (c1 - c0) > 300                       # ~4 km box at 10 m + padding


def test_window_is_clipped_to_the_granule():
    x, y, epsg = _grid(n=200)
    r0, r1, c0, c1 = stream.window_for_bbox(x, y, epsg, [90.0, 27.0, 90.5, 27.5], pad=500)
    assert 0 <= r0 <= r1 <= 200 and 0 <= c0 <= c1 <= 200


def test_mini_granule_is_read_by_the_normal_pipeline_reader(tmp_path):
    """A mini file written the way stream.subset_one writes it must work with gcov.read_subset unchanged."""
    h5py = pytest.importorskip("h5py")
    from pyproj import Transformer
    x, y, epsg = _grid(n=400)
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(x[200], y[200])
    p = tmp_path / "mini.h5"
    with h5py.File(p, "w") as o:
        g = o.create_group(gcov.GRID)
        g.create_dataset("xCoordinates", data=x)
        g.create_dataset("yCoordinates", data=y)
        pd = g.create_dataset("projection", data=np.int32(epsg))
        pd.attrs["epsg_code"] = np.int32(epsg)
        g.create_dataset("listOfPolarizations", data=np.array([b"HH", b"HV"]))
        g.create_dataset("HHHH", data=np.full((400, 400), 0.05, dtype="float32"))
        g.create_dataset("HVHV", data=np.full((400, 400), 0.01, dtype="float32"))
        g.create_dataset("mask", data=np.ones((400, 400), dtype="uint8"))
        i = o.create_group(gcov.IDENT)
        i.create_dataset("boundingPolygon", data=np.bytes_(
            f"POLYGON (({lon-.1} {lat-.1} 0, {lon+.1} {lat-.1} 0, {lon+.1} {lat+.1} 0, {lon-.1} {lat+.1} 0, {lon-.1} {lat-.1} 0))"))
    assert gcov.granule_footprint(p) is not None
    lats = np.linspace(lat - 0.005, lat + 0.005, 8)
    lons = np.linspace(lon - 0.005, lon + 0.005, 8)
    sub = gcov.read_subset(p, lats, lons, 100.0)
    assert sub["coverage_pct"] == 100.0 and np.isfinite(sub["hh"]).all() and sub["polarizations"] == ["HH", "HV"]


def test_fetch_stack_needs_two_dates_and_tolerates_one_failure(tmp_path, monkeypatch):
    calls = {}

    def fake_retry(url, out, bbox, name, attempts=4):
        if "bad" in url:
            raise RuntimeError("boom")
        calls[name] = out
        return {"name": name, "cached": True, "mb": 1.0, "seconds": 0.0}

    class Inline:                                   # run "processes" inline so monkeypatching works
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def submit(self, fn, *a):
            from concurrent.futures import Future
            f = Future()
            try:
                f.set_result(fn(*a))
            except Exception as e:  # noqa: BLE001
                f.set_exception(e)
            return f

    monkeypatch.setattr(stream, "subset_with_retry", fake_retry)
    monkeypatch.setattr(stream, "ProcessPoolExecutor", Inline)
    mk = lambda i, bad=False: {"granule_id": f"G{i}", "date": f"2026-07-{10+i}", "track_frame": "040/015",
                               "url": ("bad" if bad else "ok") + str(i)}
    paths = stream.fetch_stack([mk(1), mk(2), mk(3, bad=True)], [1, 2, 3, 4], tmp_path, log=lambda *_: None)
    assert [p.name for p in paths] == ["G1.h5", "G2.h5"]
    with pytest.raises(RuntimeError, match="only 1 date"):
        stream.fetch_stack([mk(1), mk(2, bad=True), mk(3, bad=True)], [1, 2, 3, 4], tmp_path, log=lambda *_: None)


def test_same_day_multi_mode_granules_collapse_to_one_per_date():
    """NISAR images a frame on one day in several modes; only the dual-pol, widest-bandwidth one is kept."""
    from geosar_pipeline import common

    def g(name):
        return common.parse_granule_name(name)

    stack = [
        g("NISAR_L2_PR_GCOV_024_084_D_070_2005_QPDH_A_20260702T005150_20260702T005155_P05023_N_P_J_001"),
        g("NISAR_L2_PR_GCOV_024_084_D_070_2005_DHDH_M_20260702T005150_20260702T005225_P05023_N_F_J_001"),
        g("NISAR_L2_PR_GCOV_024_084_D_070_4005_DHDH_A_20260702T005158_20260702T005225_P05023_N_F_J_001"),
        g("NISAR_L2_PR_GCOV_025_084_D_070_2005_DHDH_M_20260714T005149_20260714T005224_P05023_F_F_J_001"),
        g("NISAR_L2_PR_GCOV_025_084_D_070_4005_DHDH_A_20260714T005157_20260714T005224_P05023_F_F_J_001"),
    ]
    tf, picked = common.select_best_track(stack, "084/070")
    assert tf == "084/070" and [p["date"] for p in picked] == ["2026-07-02", "2026-07-14"]
    assert all(p["mode"] == "4005" and p["pol_code"] == "DHDH" for p in picked)
    _, auto = common.select_best_track(stack)                     # without a forced track/frame too
    assert [p["date"] for p in auto] == ["2026-07-02", "2026-07-14"]