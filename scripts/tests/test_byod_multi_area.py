"""Multi-area auto-grouping for the bring-your-own-data flow (one folder, several incidents)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geosar_pipeline import common  # noqa: E402
import byod_build_aoi as byod  # noqa: E402


def test_known_area_matched_by_footprint_centre():
    assert common.match_known_area([93.0, 25.5, 95.5, 28.0]) == "aoi_assam_majuli"
    assert common.match_known_area([77.5, 20.0, 80.5, 22.5]) == "aoi_nagpur_kanhan"


def test_unknown_area_gets_no_known_match_and_a_stable_auto_id():
    fp = [10.0, 40.0, 12.0, 42.0]
    assert common.match_known_area(fp) is None
    assert byod.auto_identity("010/020", fp) == "aoi_n41_0_e11_0"
    assert byod.auto_identity("010/020", fp) == byod.auto_identity("010/020", fp)
    assert byod.AOI_ID_RE.match(byod.auto_identity("010/020", [-70.5, -10.2, -68.5, -8.2]))


def test_two_incident_folder_is_split_by_track_frame():
    names = [
        "NISAR_L2_PR_GCOV_025_040_A_015_4005_DHDH_A_20260710T230529_20260710T230603_P05023_N_F_J_001.h5",
        "NISAR_L2_PR_GCOV_026_040_A_015_4005_DHDH_A_20260722T230528_20260722T230602_P05023_N_F_J_001.h5",
        "NISAR_L2_PR_GCOV_025_156_A_012_4005_DHDH_A_20260719T001023_20260719T001058_P05023_N_F_J_001.h5",
    ]
    groups = {}
    for n in names:
        groups.setdefault(common.parse_granule_name(n)["track_frame"], []).append(n)
    assert sorted(groups) == ["040/015", "156/012"] and len(groups["040/015"]) == 2