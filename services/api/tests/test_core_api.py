"""Envelope, health, AOI directory, timeline, provenance, CORS, config & data store.

SRS refs: §3.1 (dual AOI), §3.2 (maturity, gap, M/N), §6.1, §7.1, §7.2 (envelope).
"""
from __future__ import annotations

import json
import re

import pytest

from app import data_store as ds_module
from app.config import Settings
from app.envelope import envelope
from conftest import AOI_IDS, assert_envelope

GAP_START, GAP_END = "2026-07-27", "2026-08-10"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- envelope (§7.2)
def test_envelope_defaults():
    body = envelope({"x": 1})
    assert body == {
        "status": "ok", "aoi_id": None, "source_mode": "LOCAL_VERIFIED_CACHE",
        "fallback_active": False, "warning": None, "data": {"x": 1},
    }


@pytest.mark.parametrize("path", [
    "/",
    "/api/v1/health",
    "/api/v1/aois",
    *[f"/api/v1/aois/{a}/timeline" for a in AOI_IDS],
    *[f"/api/v1/aois/{a}/provenance" for a in AOI_IDS],
    *[f"/api/v1/aois/{a}/exposure" for a in AOI_IDS],
    "/api/v1/aois/aoi_assam_majuli/inspect?lat=26.9&lon=94.1",
    "/api/v1/aois/aoi_assam_majuli/inspect?lat=0&lon=0",
    "/api/v1/aois/not_a_real_aoi/timeline",
    "/api/v1/aois/not_a_real_aoi/provenance",
    "/api/v1/aois/not_a_real_aoi/exposure",
    "/api/v1/aois/not_a_real_aoi/inspect?lat=1&lon=1",
])
def test_every_json_endpoint_returns_standard_envelope(client, path):
    res = client.get(path)
    assert res.status_code == 200
    assert_envelope(res.json())


# ---------------------------------------------------------------- health (§7.1)
def test_health_reports_packs_and_config(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    data = body["data"]
    assert set(AOI_IDS) <= set(data["aoi_packs"])
    assert data["earthdata_token_configured"] is False
    assert data["llm_narrator_enabled"] is False
    assert data["data_store_fallback"] is False  # committed manifests exist


# ---------------------------------------------------------------- AOIs (§3.1)
def test_aoi_directory_lists_both_presets(client):
    aois = client.get("/api/v1/aois").json()["data"]["aois"]
    ids = [a["aoi_id"] for a in aois]
    assert "aoi_assam_majuli" in ids and "aoi_nagpur_kanhan" in ids


@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_aoi_bounds_are_valid_wgs84_and_about_30km(client, aoi_id):
    aoi = next(a for a in client.get("/api/v1/aois").json()["data"]["aois"] if a["aoi_id"] == aoi_id)
    west, south, east, north = aoi["bounds"]
    assert -180 <= west < east <= 180 and -90 <= south < north <= 90
    # ~30x30 km window (SRS §3.1); allow 20-50 km per side.
    import math
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians((south + north) / 2))
    assert 20 <= (north - south) * km_per_deg_lat <= 50
    assert 20 <= (east - west) * km_per_deg_lon <= 50
    assert aoi["layers"], "each AOI must expose at least one thematic layer"


def test_assam_aoi_exposes_the_pipeline_layers(client):
    aoi = next(a for a in client.get("/api/v1/aois").json()["data"]["aois"]
               if a["aoi_id"] == "aoi_assam_majuli")
    assert {"open_water", "flooded_veg", "hydroperiod", "gmm_regimes"} <= set(aoi["layers"])  # jrc_anomaly needs the optional JRC tile


# ---------------------------------------------------------------- timeline (§3.2)
@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_timeline_dates_are_iso_sorted_unique(client, aoi_id):
    tl = client.get(f"/api/v1/aois/{aoi_id}/timeline").json()["data"]["timeline"]
    dates = [t["date"] for t in tl]
    assert all(ISO_DATE.match(d) for d in dates)
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))


@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_timeline_every_date_has_maturity_badge(client, aoi_id):
    for t in client.get(f"/api/v1/aois/{aoi_id}/timeline").json()["data"]["timeline"]:
        assert t.get("maturity") in {"PROVISIONAL", "VALIDATED"}, t


@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_timeline_maturity_follows_calibration_transition(client, aoi_id):
    """June-Oct 2026 PROVISIONAL, Nov 2026 VALIDATED; 21-23 Oct is the transition window."""
    for t in client.get(f"/api/v1/aois/{aoi_id}/timeline").json()["data"]["timeline"]:
        if t["date"] < "2026-10-21":
            assert t["maturity"] == "PROVISIONAL", t
        if t["date"] >= "2026-11-01":
            assert t["maturity"] == "VALIDATED", t


@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_timeline_has_no_acquisitions_inside_sensor_gap(client, aoi_id):
    tl = client.get(f"/api/v1/aois/{aoi_id}/timeline").json()["data"]["timeline"]
    assert not [t["date"] for t in tl if GAP_START < t["date"] < GAP_END]


@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_timeline_metadata(client, aoi_id):
    data = client.get(f"/api/v1/aois/{aoi_id}/timeline").json()["data"]
    assert "2026-07-27/2026-08-10" in data["acquisition_gaps"]
    assert data["polarization"] in {"HH+HV", "HH"}  # Single-Pol HH mode allowed (§3.2)
    assert data["fallback_plan"] in {"A", "B", "C", "D"}


def test_timeline_unknown_aoi(client):
    body = client.get("/api/v1/aois/nope/timeline").json()
    assert body["status"] == "unknown_aoi"
    assert body["data"] is None
    assert body["fallback_active"] is True


# ---------------------------------------------------------------- provenance (§7.1, §10)
@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_provenance_thresholds_match_srs(client, aoi_id):
    data = client.get(f"/api/v1/aois/{aoi_id}/provenance").json()["data"]
    assert data["delta_hh_params"]["min_delta_hh_db"] == 3.0
    assert data["delta_hh_params"]["min_delta_ratio_db"] == 1.5


@pytest.mark.parametrize("aoi_id", AOI_IDS)
def test_provenance_limitations_use_honest_language(client, aoi_id):
    lims = " ".join(client.get(f"/api/v1/aois/{aoi_id}/provenance").json()["data"]["limitations"]).lower()
    if client.get(f"/api/v1/aois/{aoi_id}/provenance").json()["data"].get("opera_dswx_agreement_pct") is not None:
        assert "inter-sensor agreement" in lims   # only claimed when an OPERA comparison was actually made
    assert "m of n" in lims
    assert "not confirmed flood depth" in lims or "not a confirmed flood-depth" in lims
    # Pitch guide §10: "accuracy" may only appear negated.
    for m in re.finditer(r"accuracy", lims):
        assert "not ground-truth accuracy" in lims[max(0, m.start() - 20): m.end()]


# ---------------------------------------------------------------- exposure (§5.5)
def test_exposure_missing_pack_returns_empty_feature_collection(client, monkeypatch, tmp_path):
    from app.data_store import store
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: tmp_path)
    body = client.get("/api/v1/aois/aoi_assam_majuli/exposure").json()
    assert body["fallback_active"] is True
    assert body["data"]["geojson"] == {"type": "FeatureCollection", "features": []}
    assert body["data"]["ranked"] == []
    assert "never a damage claim" in body["data"]["note"]


def test_exposure_ranks_candidates_by_wet_observations(client, monkeypatch, tmp_path):
    from app.data_store import store
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "road/1", "geometry": None,
         "properties": {"kind": "road", "name": "NH715K", "wet_observations": 3, "total_observations": 9}},
        {"type": "Feature", "geometry": None,
         "properties": {"osm_id": "village/2", "kind": "village", "name": "Kamalabari",
                        "wet_observations": 7, "total_observations": 9}},
        {"type": "Feature", "id": "road/3", "geometry": None,
         "properties": {"kind": "road", "wet_observations": 5, "total_observations": 9}},
    ]}
    (tmp_path / "osm_exposure.geojson").write_text(json.dumps(fc))
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: tmp_path)

    data = client.get("/api/v1/aois/aoi_assam_majuli/exposure").json()["data"]
    assert [r["wet_observations"] for r in data["ranked"]] == [7, 5, 3]
    assert data["ranked"][0]["id"] == "village/2"       # falls back to properties.osm_id
    assert data["ranked"][1]["name"] == "unnamed"        # default name
    assert all(r["wet_observations"] >= 3 for r in data["ranked"])  # M >= 3 rule


def test_exposure_corrupt_geojson_does_not_500(client, monkeypatch, tmp_path):
    from app.data_store import store
    (tmp_path / "osm_exposure.geojson").write_text("{not json")
    monkeypatch.setattr(store, "aoi_dir", lambda aoi_id: tmp_path)
    res = client.get("/api/v1/aois/aoi_assam_majuli/exposure")
    assert res.status_code == 200
    assert_envelope(res.json())


# ---------------------------------------------------------------- CORS (§6, §8.1)
def test_cors_allows_any_origin_in_demo_mode(client):
    res = client.get("/api/v1/health", headers={"Origin": "https://geosar.example"})
    assert res.headers.get("access-control-allow-origin") == "*"


def test_cors_preflight(client):
    res = client.options("/api/v1/evidence-card", headers={
        "Origin": "https://geosar.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert res.status_code == 200


# ---------------------------------------------------------------- config (§8.1)
def test_cors_origin_list_parsing():
    assert Settings(cors_origins="*", _env_file=None).cors_origin_list == ["*"]
    assert Settings(cors_origins="https://a.io, https://b.io ,", _env_file=None).cors_origin_list == [
        "https://a.io", "https://b.io"]


def test_llm_enabled_needs_only_a_key_and_defaults_to_openai():
    assert not Settings(_env_file=None).llm_enabled
    assert not Settings(llm_api_key="  ", _env_file=None).llm_enabled
    st = Settings(llm_api_key="k", _env_file=None)
    assert st.llm_enabled
    assert st.llm_base_url == "https://api.openai.com/v1"
    assert st.llm_model_name == "gpt-4o-mini"
    custom = Settings(llm_api_key="k", llm_api_base="http://x/v1/", llm_model="m", _env_file=None)
    assert (custom.llm_base_url, custom.llm_model_name) == ("http://x/v1", "m")


def test_default_external_timeout_is_within_srs_limits():
    assert Settings(_env_file=None).external_timeout_seconds <= 4.0


# ---------------------------------------------------------------- data store fallback (§7.1)
def _make_pack(root, aoi_id, cube=True, manifest='{"aoi_id": "%s", "bounds": [1, 2, 3, 4]}'):
    d = root / aoi_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(manifest % aoi_id if "%s" in manifest else manifest)
    if cube:
        (d / "time_series_cube.npz").write_bytes(b"x")


def test_empty_data_store_lists_nothing_and_never_invents_areas(client, monkeypatch, tmp_path):
    monkeypatch.setattr(ds_module, "DATA_STORE", tmp_path / "does_not_exist")
    s = ds_module.DataStore()
    s.load()
    assert s.list_aois() == [] and s.using_fallback is True
    monkeypatch.setattr("app.routers.aois.store", s)
    body = client.get("/api/v1/aois").json()
    assert body["status"] == "no_data" and body["data"]["aois"] == []
    assert body["data"]["onboarding"]["steps"]


def test_only_areas_with_a_built_pack_are_listed(monkeypatch, tmp_path):
    _make_pack(tmp_path, "aoi_built")
    _make_pack(tmp_path, "aoi_no_cube", cube=False)      # manifest only: not analysed -> hidden
    _make_pack(tmp_path, "aoi_corrupt", manifest="{corrupt")
    monkeypatch.setattr(ds_module, "DATA_STORE", tmp_path)
    s = ds_module.DataStore()
    s.load()
    assert [a["aoi_id"] for a in s.list_aois()] == ["aoi_built"]
    assert s.get("aoi_no_cube") is None and s.get("aoi_corrupt") is None


def test_new_pack_appears_without_restarting(monkeypatch, tmp_path):
    monkeypatch.setattr(ds_module, "DATA_STORE", tmp_path)
    s = ds_module.DataStore()
    s.load()
    assert s.list_aois() == []
    _make_pack(tmp_path, "aoi_fresh")
    assert [a["aoi_id"] for a in s.list_aois()] == ["aoi_fresh"]


def test_folder_name_is_the_single_source_of_truth_for_identity(monkeypatch, tmp_path):
    """A folder whose manifest.json still claims a different aoi_id (e.g. after a manual
    folder rename) must be listed under the FOLDER name, so /health, get() and aoi_dir()
    never drift apart. Renaming/removing the folder renames/removes the AOI."""
    _make_pack(tmp_path, "aoi_renamed", manifest='{"aoi_id": "aoi_old_name", "bounds": [1, 2, 3, 4]}')
    monkeypatch.setattr(ds_module, "DATA_STORE", tmp_path)
    s = ds_module.DataStore()
    s.load()
    assert [a["aoi_id"] for a in s.list_aois()] == ["aoi_renamed"]   # folder wins, not "aoi_old_name"
    assert s.get("aoi_renamed") is not None
    assert s.get("aoi_old_name") is None


def test_shipped_aoi_manifests_are_valid_json():
    for aoi_id in AOI_IDS:
        manifest = ds_module.DATA_STORE / aoi_id / "manifest.json"
        assert manifest.exists(), manifest
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["aoi_id"] == aoi_id
