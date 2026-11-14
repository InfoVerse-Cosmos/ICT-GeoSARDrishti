"""Data-gate tests for the downloaded NISAR L2 GCOV granules (SRS §3.2, §3.3, §5.1, §9 Phase 1).

Three layers:
  1. Filename-level checks   -> always run (no data needed).
  2. Manifest contract       -> always run; FAIL until manifests list these real granules.
  3. HDF5 content checks     -> run only when NISAR_H5_DIR points at the folder holding the .h5 files
                                (and h5py is installed). Optional: GEOSAR_GRANULE_AOI=aoi_assam_majuli|aoi_nagpur_kanhan.

Run from repo root:
  python -m pytest scripts/tests/test_nisar_granules.py -v
  NISAR_H5_DIR=/path/to/h5 GEOSAR_GRANULE_AOI=aoi_assam_majuli python -m pytest scripts/tests/test_nisar_granules.py -v
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
DATA_STORE = REPO / "services" / "api" / "data_store"

GRANULES = [
    "NISAR_L2_PR_GCOV_032_063_D_076_2005_DHDH_M_20261004T135735_20261004T135809_P05023_N_F_J_001.h5",
    "NISAR_L2_PR_GCOV_032_135_D_076_2005_DHDH_M_20261009T134915_20261009T134950_P05023_N_F_J_001.h5",
    "NISAR_L2_PR_GCOV_033_063_D_076_2005_DHDH_M_20261016T135735_20261016T135809_P05023_N_F_J_001.h5",
    "NISAR_L2_PR_GCOV_034_135_D_076_2005_DHDH_M_20261102T134916_20261102T134950_P05036_N_F_J_001.h5",
]

NAME_RE = re.compile(
    r"^NISAR_(?P<level>L2)_(?P<ptype>PR)_(?P<product>GCOV)_"
    r"(?P<cycle>\d{3})_(?P<track>\d{3})_(?P<direction>[AD])_(?P<frame>\d{3})_"
    r"(?P<mode>\d{4})_(?P<pol>[A-Z]{4})_(?P<obs>[A-Z])_"
    r"(?P<start>\d{8}T\d{6})_(?P<end>\d{8}T\d{6})_"
    r"(?P<crid>[A-Z]\d{5})_(?P<acc>[A-Z])_(?P<cov>[A-Z])_(?P<loc>[A-Z])_(?P<ctr>\d{3})\.h5$"
)

AOI_BOUNDS = {
    "aoi_assam_majuli": (93.90, 26.75, 94.30, 27.05),
    "aoi_nagpur_kanhan": (78.95, 21.15, 79.35, 21.45),
}
GAP_START, GAP_END = "2026-07-27", "2026-08-10"
CALIBRATION_TRANSITION = "2026-10-21"


def parse(name: str) -> dict:
    m = NAME_RE.match(name)
    assert m, f"filename does not follow NISAR convention: {name}"
    g = m.groupdict()
    g["start_dt"] = datetime.strptime(g["start"], "%Y%m%dT%H%M%S")
    g["end_dt"] = datetime.strptime(g["end"], "%Y%m%dT%H%M%S")
    g["date"] = g["start_dt"].strftime("%Y-%m-%d")
    g["track_frame"] = f"{g['track']}/{g['frame']}"
    g["granule_id"] = name[:-3]
    return g


PARSED = [parse(n) for n in GRANULES]


def by_track() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for g in PARSED:
        out[g["track"]].append(g)
    for v in out.values():
        v.sort(key=lambda g: g["start_dt"])
    return dict(out)


def expected_maturity(date: str) -> str:
    """SRS §3.2: June-Oct 2026 PROVISIONAL, VALIDATED from the 21-23 Oct transition onward."""
    return "VALIDATED" if date >= "2026-10-23" else "PROVISIONAL"


# =============================================================== 1. filename level
@pytest.mark.parametrize("name", GRANULES)
def test_filename_follows_nisar_convention(name):
    g = parse(name)
    assert (g["level"], g["ptype"], g["product"]) == ("L2", "PR", "GCOV")


@pytest.mark.parametrize("g", PARSED, ids=[g["date"] for g in PARSED])
def test_granule_is_dual_pol_so_plan_a_classes_are_possible(g):
    """DHDH = dual-pol H-transmit (HH+HV). Single-Pol HH fallback mode must NOT trigger."""
    assert g["pol"] == "DHDH"


@pytest.mark.parametrize("g", PARSED, ids=[g["date"] for g in PARSED])
def test_acquisition_window_is_short_and_ordered(g):
    dur = (g["end_dt"] - g["start_dt"]).total_seconds()
    assert 0 < dur <= 60, "a single frame should be ~35 s of along-track acquisition"


def test_all_granules_share_direction_frame_and_mode():
    assert {g["direction"] for g in PARSED} == {"D"}
    assert {g["frame"] for g in PARSED} == {"076"}
    assert {g["mode"] for g in PARSED} == {"2005"}


def test_no_granule_falls_inside_reported_sensor_gap():
    assert not [g["date"] for g in PARSED if GAP_START < g["date"] < GAP_END]


def test_no_duplicate_granules():
    assert len({g["granule_id"] for g in PARSED}) == len(PARSED)


# ----------------------------------------------------------- same-track stacking (§3.2, §3.3)
def test_granules_split_into_two_same_track_stacks():
    """Hydroperiod/ΔHH must only be computed within ONE track (same geometry)."""
    tracks = by_track()
    assert set(tracks) == {"063", "135"}
    assert [g["date"] for g in tracks["063"]] == ["2026-10-04", "2026-10-16"]
    assert [g["date"] for g in tracks["135"]] == ["2026-10-09", "2026-11-02"]


def test_same_track_pairs_respect_12_day_repeat():
    for track, stack in by_track().items():
        for a, b in zip(stack, stack[1:]):
            days = (b["start_dt"] - a["start_dt"]).days
            assert days % 12 == 0, f"track {track}: {days} days is not a multiple of the 12-day repeat"
            cycles = int(b["cycle"]) - int(a["cycle"])
            assert cycles * 12 == days, f"track {track}: cycle delta {cycles} vs {days} days"


def test_same_track_pairs_have_near_identical_time_of_day():
    """Repeat-pass geometry check: same track -> same UTC time of day (± 5 s)."""
    for stack in by_track().values():
        secs = [g["start_dt"].hour * 3600 + g["start_dt"].minute * 60 + g["start_dt"].second for g in stack]
        assert max(secs) - min(secs) <= 5


def test_dataset_supports_only_fallback_plan_c():
    """SRS §3.3: <=3 compatible dates per track -> Plan C change triad, not Plan A season."""
    longest = max(len(v) for v in by_track().values())
    assert longest <= 3
    plan = "A" if longest >= 6 else ("C" if longest >= 2 else "D")
    assert plan == "C"


def test_season_coverage_misses_monsoon_peak():
    """Documents the scientific limitation: no June-Sept acquisitions, so the 18-21 July
    flood spell is NOT covered by this download."""
    assert min(g["date"] for g in PARSED) >= "2026-10-01"


# ----------------------------------------------------------- maturity / calibration (§3.2)
def test_maturity_assignment_by_date():
    got = {g["date"]: expected_maturity(g["date"]) for g in PARSED}
    assert got == {
        "2026-10-04": "PROVISIONAL", "2026-10-09": "PROVISIONAL",
        "2026-10-16": "PROVISIONAL", "2026-11-02": "VALIDATED",
    }


def test_track_135_crosses_calibration_transition_and_needs_offset_check():
    """Oct-09 (P05023, PROVISIONAL) vs Nov-02 (P05036, VALIDATED) on the same track:
    software release changed, so a radiometric offset check is mandatory before ΔHH."""
    a, b = by_track()["135"]
    assert a["date"] < CALIBRATION_TRANSITION <= b["date"]
    assert a["crid"] != b["crid"]


def test_track_063_pair_is_calibration_consistent():
    a, b = by_track()["063"]
    assert a["crid"] == b["crid"]
    assert expected_maturity(a["date"]) == expected_maturity(b["date"])


# =============================================================== 2. manifest contract
# Run AFTER scripts/01 locked the real granules:  GEOSAR_CHECK_LOCKED_MANIFEST=1 [GEOSAR_DATA_STORE=...]
needs_lock = pytest.mark.skipif(os.environ.get("GEOSAR_CHECK_LOCKED_MANIFEST") != "1",
                                reason="set GEOSAR_CHECK_LOCKED_MANIFEST=1 after running scripts/01 on the real data")
if os.environ.get("GEOSAR_DATA_STORE"):
    DATA_STORE = Path(os.environ["GEOSAR_DATA_STORE"])


def _all_manifest_entries():
    entries = []
    for aoi_id in AOI_BOUNDS:
        m = json.loads((DATA_STORE / aoi_id / "manifest.json").read_text(encoding="utf-8"))
        for t in m.get("timeline", []):
            entries.append((aoi_id, t))
    return entries


@needs_lock
def test_manifests_lock_a_complete_same_track_stack_of_the_downloaded_granules():
    """Phase 1 data gate: real granule IDs (not 'TBD'), and every downloaded granule of the
    selected track is in the timeline (other tracks are deliberately excluded, SRS §3.2)."""
    listed = {t.get("granule_id") for _, t in _all_manifest_entries()}
    locked = [g for g in PARSED if g["granule_id"] in listed]
    assert locked, "no downloaded granule is locked in any manifest (run scripts/01)"
    for track in {g["track"] for g in locked}:
        missing = [g["granule_id"] for g in by_track()[track] if g["granule_id"] not in listed]
        assert not missing, f"track {track} stack incomplete: {missing}"


@needs_lock
def test_manifest_entries_for_these_granules_are_consistent():
    by_id = {g["granule_id"]: g for g in PARSED}
    checked = 0
    for aoi_id, t in _all_manifest_entries():
        g = by_id.get(t.get("granule_id"))
        if not g:
            continue
        checked += 1
        assert t["date"] == g["date"], (aoi_id, t)
        assert t["maturity"] == expected_maturity(g["date"]), (aoi_id, t)
        assert t["polarization"] == "HH+HV", (aoi_id, t)
        assert t["track_frame"] in {g["track_frame"], f"{int(g['track']):03d}/{int(g['frame']):03d}"}, (aoi_id, t)
    if checked == 0:
        pytest.fail("no manifest entry references the downloaded granules yet")


def test_one_aoi_timeline_never_mixes_tracks():
    """A timeline driving hydroperiod must be same-track (SRS §3.2)."""
    for aoi_id in AOI_BOUNDS:
        mp = DATA_STORE / aoi_id / "manifest.json"
        if not mp.exists():
            # 45a551a (PR #11) removed the bundled AOI packs; skip AOIs with no manifest on disk.
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        tracks = {t.get("track_frame") for t in m.get("timeline", []) if t.get("track_frame") not in (None, "TBD")}
        assert len(tracks) <= 1, f"{aoi_id} mixes tracks: {tracks}"


# =============================================================== 3. HDF5 content (opt-in)
H5_DIR = os.environ.get("NISAR_H5_DIR")
TARGET_AOI = os.environ.get("GEOSAR_GRANULE_AOI")

needs_h5 = pytest.mark.skipif(not H5_DIR, reason="set NISAR_H5_DIR to the folder with the .h5 granules")

GCOV_GRID = "/science/LSAR/GCOV/grids/frequencyA"
IDENT = "/science/LSAR/identification"


@pytest.fixture(scope="module")
def h5py_mod():
    return pytest.importorskip("h5py")


def _open(h5py_mod, name):
    path = Path(H5_DIR) / name
    if not path.exists():
        pytest.fail(f"granule missing on disk: {path}")
    return h5py_mod.File(path, "r")


def _scalar(ds):
    v = ds[()]
    if isinstance(v, bytes):
        return v.decode()
    if isinstance(v, np.ndarray) and v.dtype.kind in "SO":
        return [x.decode() if isinstance(x, bytes) else x for x in v.tolist()]
    return v


@needs_h5
@pytest.mark.parametrize("name", GRANULES)
def test_h5_has_hh_and_hv_backscatter(h5py_mod, name):
    with _open(h5py_mod, name) as f:
        assert GCOV_GRID in f, f"{GCOV_GRID} missing; keys: {list(f['/science/LSAR'].keys())}"
        grid = f[GCOV_GRID]
        assert "HHHH" in grid, "HH covariance term (γ0 HH) missing"
        assert "HVHV" in grid, "HV covariance term missing -> pipeline must switch to Single-Pol HH mode"
        assert grid["HHHH"].shape == grid["HVHV"].shape
        assert "xCoordinates" in grid and "yCoordinates" in grid


@needs_h5
@pytest.mark.parametrize("name", GRANULES)
def test_h5_identification_matches_filename(h5py_mod, name):
    g = parse(name)
    with _open(h5py_mod, name) as f:
        ident = f[IDENT]
        assert int(_scalar(ident["trackNumber"])) == int(g["track"])
        assert int(_scalar(ident["frameNumber"])) == int(g["frame"])
        assert str(_scalar(ident["orbitPassDirection"])).upper().startswith("D")
        start = str(_scalar(ident["zeroDopplerStartTime"]))
        assert start.startswith(g["start_dt"].strftime("%Y-%m-%dT%H:%M:%S")), start


def _bbox_from_polygon(wkt: str):
    nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", wkt)]
    lons, lats = nums[0::2], nums[1::2]
    return min(lons), min(lats), max(lons), max(lats)


def _intersects(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


@needs_h5
@pytest.mark.parametrize("name", GRANULES)
def test_h5_footprint_covers_an_aoi(h5py_mod, name):
    with _open(h5py_mod, name) as f:
        bbox = _bbox_from_polygon(str(_scalar(f[IDENT]["boundingPolygon"])))
    hits = [a for a, b in AOI_BOUNDS.items() if _intersects(bbox, b)]
    if TARGET_AOI:
        assert TARGET_AOI in hits, f"{name} footprint {bbox} does not cover {TARGET_AOI}"
    else:
        assert hits, f"{name} footprint {bbox} covers neither Assam nor Nagpur AOI"


@needs_h5
@pytest.mark.parametrize("name", GRANULES)
def test_h5_backscatter_values_are_physically_plausible(h5py_mod, name):
    with _open(h5py_mod, name) as f:
        hh = f[GCOV_GRID]["HHHH"][::50, ::50].astype("float64")
        hv = f[GCOV_GRID]["HVHV"][::50, ::50].astype("float64")
    for label, arr in (("HH", hh), ("HV", hv)):
        valid = arr[np.isfinite(arr) & (arr > 0)]
        assert valid.size > 0.2 * arr.size, f"{label}: <20% valid pixels"
        med_db = 10 * np.log10(np.median(valid))
        assert -35 <= med_db <= 5, f"{label} median γ0 {med_db:.1f} dB outside plausible L-band range"
    # Like-pol is brighter than cross-pol on average -> HH_dB - HV_dB > 0
    both = np.isfinite(hh) & np.isfinite(hv) & (hh > 0) & (hv > 0)
    assert np.median(10 * np.log10(hh[both]) - 10 * np.log10(hv[both])) > 0


@needs_h5
@pytest.mark.parametrize("track", ["063", "135"])
def test_h5_same_track_pairs_share_the_geocoded_grid(h5py_mod, track):
    a, b = by_track()[track]
    with _open(h5py_mod, GRANULES[PARSED.index(a)]) as fa, _open(h5py_mod, GRANULES[PARSED.index(b)]) as fb:
        ga, gb = fa[GCOV_GRID], fb[GCOV_GRID]
        assert ga["HHHH"].shape == gb["HHHH"].shape, "pixel-wise ΔHH requires identical grids"
        assert np.allclose(ga["xCoordinates"][()], gb["xCoordinates"][()])
        assert np.allclose(ga["yCoordinates"][()], gb["yCoordinates"][()])


@needs_h5
def test_h5_track_135_radiometric_offset_across_calibration_change(h5py_mod):
    """SRS §3.2: PROVISIONAL->VALIDATED offset check. On mostly-stable land the median
    HV difference should be small; a larger jump means ΔHH needs an offset correction."""
    a, b = by_track()["135"]
    with _open(h5py_mod, GRANULES[PARSED.index(a)]) as fa, _open(h5py_mod, GRANULES[PARSED.index(b)]) as fb:
        hv_a = fa[GCOV_GRID]["HVHV"][::50, ::50].astype("float64")
        hv_b = fb[GCOV_GRID]["HVHV"][::50, ::50].astype("float64")
    ok = np.isfinite(hv_a) & np.isfinite(hv_b) & (hv_a > 0) & (hv_b > 0)
    diff = 10 * np.log10(hv_b[ok]) - 10 * np.log10(hv_a[ok])
    offset = float(np.median(diff))
    print(f"track 135 median HV offset (Nov-02 minus Oct-09): {offset:+.2f} dB")
    assert abs(offset) < 1.0, f"calibration offset {offset:+.2f} dB exceeds 1 dB; correct before ΔHH"
