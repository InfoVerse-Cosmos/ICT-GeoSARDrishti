"""Backend behaviour against the real downloaded NISAR granule names (SRS §3.2 maturity badge)."""
from __future__ import annotations

import pytest

from app.services.earthdata_client import _maturity_from_entry

REAL = {
    "2026-10-04": "NISAR_L2_PR_GCOV_032_063_D_076_2005_DHDH_M_20261004T135735_20261004T135809_P05023_N_F_J_001",
    "2026-10-09": "NISAR_L2_PR_GCOV_032_135_D_076_2005_DHDH_M_20261009T134915_20261009T134950_P05023_N_F_J_001",
    "2026-10-16": "NISAR_L2_PR_GCOV_033_063_D_076_2005_DHDH_M_20261016T135735_20261016T135809_P05023_N_F_J_001",
    "2026-11-02": "NISAR_L2_PR_GCOV_034_135_D_076_2005_DHDH_M_20261102T134916_20261102T134950_P05036_N_F_J_001",
}


@pytest.mark.parametrize("date,expected", [
    ("2026-10-04", "PROVISIONAL"),
    ("2026-10-09", "PROVISIONAL"),
    ("2026-10-16", "PROVISIONAL"),
    ("2026-11-02", "VALIDATED"),
])
def test_live_cmr_maturity_badge_for_real_granules(date, expected):
    """CMR entries for real granules carry the filename as title. The word 'VALIDATED'
    never appears in it, so maturity must come from date / metadata, not substring match."""
    entry = {"title": REAL[date], "producer_granule_id": REAL[date],
             "time_start": f"{date}T13:50:00Z", "collection_concept_id": "C0000000000-ASF"}
    assert _maturity_from_entry(entry) == expected


def test_default_cmr_short_name_is_configurable_for_real_collection(client, monkeypatch):
    """The live endpoint must accept the real collection short_name the team found on CMR."""
    from app.services import earthdata_client
    from helpers import FakeResponse, make_fake_async_client

    calls: list = []
    monkeypatch.setattr(earthdata_client.httpx, "AsyncClient",
                        make_fake_async_client(response=FakeResponse({"feed": {"entry": []}}), calls=calls))
    client.get("/api/v1/nisar/earthdata-live", params={"short_name": "NISAR_L2_GCOV_BETA_V1"})
    assert calls[1]["params"]["short_name"] == "NISAR_L2_GCOV_BETA_V1"
