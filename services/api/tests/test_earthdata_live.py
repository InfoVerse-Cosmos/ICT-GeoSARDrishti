"""Live NASA CMR connector with cache fallback (SRS §6.1 item 3, §7.1, §7.2 rule 2)."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import Settings
from app.services import earthdata_client
from app.services.earthdata_client import _maturity_from_entry, cached_response, earthdata_live_search
from conftest import assert_envelope
from helpers import FakeResponse, make_fake_async_client

CMR_PAYLOAD = {"feed": {"entry": [
    {"producer_granule_id": "NISAR_L2_GCOV_A_20261107", "time_start": "2026-11-07T00:12:00Z",
     "title": "NISAR_L2_GCOV VALIDATED 20261107"},
    {"id": "G123-ASF", "time_start": "2026-07-22T00:12:00Z", "title": "NISAR_L2_GCOV 20260722"},
]}}


def _patch_client(monkeypatch, **kw):
    calls: list = []
    monkeypatch.setattr(earthdata_client.httpx, "AsyncClient", make_fake_async_client(calls=calls, **kw))
    return calls


def test_live_success_is_parsed(monkeypatch):
    _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    data, mode, fallback, warning = asyncio.run(earthdata_live_search("93.9,26.75,94.3,27.05", "NISAR_L2_GCOV_V1"))
    assert (mode, fallback, warning) == ("LIVE_API", False, None)
    assert data["granule_count"] == 2
    assert data["granules"][0] == {"id": "NISAR_L2_GCOV_A_20261107", "date": "2026-11-07", "maturity": "VALIDATED"}
    assert data["granules"][1] == {"id": "NISAR_L2_GCOV 20260722", "date": "2026-07-22", "maturity": "PROVISIONAL"}


def test_live_query_sends_bbox_and_short_name(monkeypatch):
    calls = _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    asyncio.run(earthdata_live_search("1,2,3,4", "NISAR_L2_GCOV_V1"))
    req = calls[1]
    assert req["url"] == "https://cmr.earthdata.nasa.gov/search/granules.json"
    assert req["params"]["bounding_box"] == "1,2,3,4"
    assert req["params"]["short_name"] == "NISAR_L2_GCOV_V1"


def test_no_token_sends_no_auth_header(monkeypatch):
    calls = _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    asyncio.run(earthdata_live_search("1,2,3,4", "X"))
    assert "Authorization" not in calls[1]["headers"]


def test_token_is_sent_as_bearer(monkeypatch):
    monkeypatch.setattr(earthdata_client, "get_settings",
                        lambda: Settings(earthdata_token="tok123", _env_file=None))
    calls = _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    asyncio.run(earthdata_live_search("1,2,3,4", "X"))
    assert calls[1]["headers"]["Authorization"] == "Bearer tok123"


def test_default_short_name_comes_from_settings(monkeypatch):
    calls = _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    asyncio.run(earthdata_live_search("1,2,3,4"))
    assert calls[1]["params"]["short_name"] == ["NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_V1"]


def test_maturity_read_from_cmr_collection():
    assert _maturity_from_entry({"dataset_id": "NISAR Provisional Geocoded Polarimetric Covariance Product (Version 1)",
                                 "time_start": "2026-11-04T00:00:00Z"}) == "PROVISIONAL"
    assert _maturity_from_entry({"dataset_id": "NISAR Validated Geocoded Polarimetric Covariance Product (Version 1)",
                                 "time_start": "2026-07-04T00:00:00Z"}) == "VALIDATED"


def test_timeout_is_strict(monkeypatch):
    calls = _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    asyncio.run(earthdata_live_search("1,2,3,4", "X"))
    assert calls[0]["init"]["timeout"].read <= 4.0


@pytest.mark.parametrize("kw", [
    {"exc": httpx.ConnectTimeout("venue wifi")},
    {"exc": httpx.ReadTimeout("slow cmr")},
    {"exc": httpx.ConnectError("dns")},
    {"response": FakeResponse(status_code=503)},
    {"response": FakeResponse(status_code=401)},
])
def test_any_failure_falls_back_to_labelled_cache(monkeypatch, kw):
    _patch_client(monkeypatch, **kw)
    data, mode, fallback, warning = asyncio.run(earthdata_live_search("93.9,26.75,94.3,27.05", "X"))
    assert data == cached_response("93.9,26.75,94.3,27.05", "X")
    assert mode == "LOCAL_VERIFIED_CACHE" and fallback is True
    assert warning.startswith("Live NASA CMR unavailable")


def test_cached_response_comes_from_manifests_and_never_lists_placeholders():
    data = cached_response("93.9,26.75,94.3,27.05", "X")
    assert data["aois"] == ["aoi_assam_majuli"]          # bbox picks the intersecting AOI only
    assert data["granule_count"] == len(data["granules"])
    assert all(g["id"] != "TBD" for g in data["granules"])


def test_cached_response_reads_locked_granules(monkeypatch):
    from app.data_store import store
    fake = {"aoi_id": "aoi_assam_majuli", "bounds": [93.9, 26.75, 94.3, 27.05], "timeline": [
        {"date": "2026-10-04", "granule_id": "NISAR_L2_PR_GCOV_032_063_D_076", "maturity": "PROVISIONAL",
         "track_frame": "063/076"}]}
    monkeypatch.setattr(store, "list_aois", lambda: [fake])
    data = cached_response("93.9,26.75,94.3,27.05", "X", "aoi_assam_majuli")
    assert data["granule_count"] == 1 and data["granules"][0]["track_frame"] == "063/076"
    assert "not a live pull" in data["note"]


@pytest.mark.parametrize("entry,expected", [
    ({"title": "x VALIDATED y"}, "VALIDATED"),
    ({"collection_concept_id": "C1-VALIDATED"}, "VALIDATED"),
    ({"title": "plain"}, "PROVISIONAL"),
    ({}, "PROVISIONAL"),
    ({"time_start": "2026-11-02T13:49:16Z"}, "VALIDATED"),     # derived from date
    ({"time_start": "2026-10-04T13:57:35Z"}, "PROVISIONAL"),
])
def test_maturity_from_entry(entry, expected):
    assert _maturity_from_entry(entry) == expected


def test_endpoint_wraps_fallback_in_envelope(client, monkeypatch):
    _patch_client(monkeypatch, exc=httpx.ConnectTimeout("offline"))
    body = client.get("/api/v1/nisar/earthdata-live").json()
    assert_envelope(body)
    assert body["source_mode"] == "LOCAL_VERIFIED_CACHE"
    assert body["fallback_active"] is True
    assert body["data"]["granule_count"] == len(body["data"]["granules"])


def test_endpoint_default_bbox_is_assam_aoi(client, monkeypatch):
    calls = _patch_client(monkeypatch, response=FakeResponse(CMR_PAYLOAD))
    client.get("/api/v1/nisar/earthdata-live")
    assert calls[1]["params"]["bounding_box"] == "93.90,26.75,94.30,27.05"


@pytest.mark.network
def test_real_nasa_cmr_reachable(client):
    """Live check against cmr.earthdata.nasa.gov (opt-in)."""
    body = client.get("/api/v1/nisar/earthdata-live").json()
    assert_envelope(body)
    assert body["source_mode"] in {"LIVE_API", "LOCAL_VERIFIED_CACHE"}
