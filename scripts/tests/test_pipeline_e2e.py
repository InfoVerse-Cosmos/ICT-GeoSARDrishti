"""End-to-end pipeline test on SYNTHETIC GCOV granules carrying the team's real names.

01 data gate -> 02 classify/hydroperiod -> 03 GMM + JRC + DSWx -> 04 exposure (offline OSM file)
-> 05 offline mirror, then the FastAPI backend serves the produced pack.

Needs: h5py, pyproj, scikit-learn, rasterio, geopandas, shapely  (scripts/requirements.txt)
Run:   python -m pytest scripts/tests/test_pipeline_e2e.py -v
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("h5py")
pytest.importorskip("pyproj")

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from geosar_pipeline import common, data_gate, process  # noqa: E402
from geosar_pipeline.physics import FLOODED_VEG, OPEN_WATER  # noqa: E402
import make_synthetic_gcov as synth  # noqa: E402

AOI = "aoi_assam_majuli"
BOUNDS = common.AOI_BOUNDS[AOI]


@pytest.fixture(scope="module")
def h5_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("h5")
    for i, name in enumerate(synth.REAL_NAMES):
        synth.write_granule(d / name, name, BOUNDS, spacing_m=60.0, seed=i)
    try:
        synth.write_ancillary(d, BOUNDS)
    except ImportError:
        pass
    return d


@pytest.fixture(scope="module")
def store(tmp_path_factory, h5_dir):
    s = tmp_path_factory.mktemp("store")
    for aoi in common.AOI_BOUNDS:
        shutil.copytree(common.DEFAULT_DATA_STORE / aoi, s / aoi)
    return s


@pytest.fixture(scope="module")
def processed(store, h5_dir):
    data_gate.lock(AOI, data_gate.granules_from_dir(h5_dir, AOI), store)
    wc = h5_dir / "worldcover.tif"
    return process.run(AOI, h5_dir, store, res_m=150, worldcover=str(wc) if wc.exists() else None,
                       log=lambda *_: None)


# ------------------------------------------------------------------ 01 data gate
def test_data_gate_picks_a_same_track_stack(store, h5_dir):
    report = data_gate.lock(AOI, data_gate.granules_from_dir(h5_dir, AOI), store, dry_run=True)
    assert set(report["tracks_found"]) == {"063/076", "135/076"}
    assert report["fallback_plan"] == "C"
    assert report["dual_pol"] is True
    assert len({g["track_frame"] for g in report["stack"]}) == 1


def test_data_gate_can_force_a_track(store, h5_dir):
    report = data_gate.lock(AOI, data_gate.granules_from_dir(h5_dir, AOI), store, "063/076", dry_run=True)
    assert [g["date"] for g in report["stack"]] == ["2026-10-04", "2026-10-16"]
    assert {g["maturity"] for g in report["stack"]} == {"PROVISIONAL"}


def test_data_gate_from_names_only():
    gs = data_gate.granules_from_names(synth.REAL_NAMES)
    assert len(gs) == 4 and gs[3]["maturity"] == "VALIDATED" and gs[0]["polarization"] == "HH+HV"


def test_data_gate_drops_granules_outside_the_aoi(h5_dir):
    gs = data_gate.granules_from_dir(h5_dir, "aoi_nagpur_kanhan")   # synthetic files cover Assam only
    assert gs and all(g.get("skipped") for g in gs)


# ------------------------------------------------------------------ 02 classify + hydroperiod
def test_manifest_is_locked_with_real_granule_ids(processed):
    assert processed["track_frame"] == "135/076"
    assert [t["date"] for t in processed["timeline"]] == ["2026-10-09", "2026-11-02"]
    assert [t["maturity"] for t in processed["timeline"]] == ["PROVISIONAL", "VALIDATED"]
    assert all(t["granule_id"].startswith("NISAR_L2_PR_GCOV_") for t in processed["timeline"])
    assert processed["synthetic_test_data"] is True
    assert processed["provenance"]["limitations"][0].startswith("SYNTHETIC TEST DATA")


def test_wet_date_has_more_water_than_dry_reference(processed):
    wet, dry = (t["metrics"] for t in processed["timeline"])
    assert dry["is_reference"] and not wet["is_reference"]
    assert wet["open_water_km2"] > dry["open_water_km2"] > 0
    assert wet["flooded_veg_km2"] > 5 and dry["flooded_veg_km2"] == 0
    assert wet["valid_pixel_pct"] > 95


def test_paddy_sub_label_from_worldcover(processed):
    wet = processed["timeline"][0]["metrics"]
    if "ESA WorldCover" not in processed["provenance"]["masks"]["vegetation"]:
        pytest.skip("rasterio missing — no WorldCover")
    assert wet["paddy_like_km2"] > 0 and wet["natural_flooded_veg_km2"] > 0


def test_otsu_thresholds_within_srs_range(processed):
    for t in processed["provenance"]["otsu_thresholds"].values():
        assert -22.0 <= t["hh_db"] <= -13.0


def test_calibration_check_recorded(processed):
    cal = processed["provenance"]["calibration_check"]
    assert cal["provisional_date"] == "2026-10-09" and cal["validated_date"] == "2026-11-02"
    assert cal["within_1db"] is True


def test_cube_and_overlays_written(store, processed):
    with np.load(store / AOI / "time_series_cube.npz") as z:
        assert z["hh_db"].shape[0] == 2 and z["hv_db"].shape == z["hh_db"].shape
        cls = z["cls"]
        m = z["m_open"] + z["m_fveg"]
        assert (m <= z["n_valid"]).all()
        assert ((cls == OPEN_WATER).sum(0) == z["m_open"]).all()
        assert ((cls == FLOODED_VEG).sum(0) == z["m_fveg"]).all()
    ov = store / AOI / "overlays"
    for name in ("open_water_2026-10-09.png", "flooded_veg_2026-10-09.png", "hydroperiod.png", "open_water.png"):
        data = (ov / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        (length,) = struct.unpack(">I", data[8:12])
        w, h = struct.unpack(">II", data[16:24])
        assert w > 100 and h > 100


def test_single_pol_mode(tmp_path, store):
    d = tmp_path / "sp"
    d.mkdir()
    for i, name in enumerate(synth.REAL_NAMES[1::2]):           # track 135 only
        synth.write_granule(d / name, name, BOUNDS, spacing_m=90.0, seed=i, single_pol=True)
    s2 = tmp_path / "store"
    shutil.copytree(store / AOI, s2 / AOI)
    m = process.run(AOI, d, s2, res_m=300, log=lambda *_: None)
    assert m["single_pol_mode"] is True and m["polarization"] == "HH"
    assert m["provenance"]["otsu_thresholds"]["2026-10-09"]["hv_db"] is None
    assert m["timeline"][0]["metrics"]["open_water_km2"] > 0


# ------------------------------------------------------------------ 03 GMM + validation
@pytest.fixture(scope="module")
def regimes_done(store, processed, h5_dir):
    pytest.importorskip("sklearn")
    from geosar_pipeline import regimes
    jrc, dswx = h5_dir / "jrc_occurrence.tif", h5_dir / "dswx_wtr.tif"
    return regimes.run(AOI, store, jrc=str(jrc) if jrc.exists() else None,
                       dswx=str(dswx) if dswx.exists() else None, dswx_date="2026-10-09", log=lambda *_: None)


def test_gmm_regimes_are_hydrologically_sensible(regimes_done):
    area = regimes_done["provenance"]["gmm"]["regime_area_km2"]
    assert area["Stable Dry Upland / Levee"] > area["Permanent River / Deep Channel"] > 0
    assert area["Seasonally Flooded Canopy / Tall Grassland"] + area["Seasonal Paddy-Like Inundation Cycle"] > 0
    assert "gmm_regimes" in regimes_done["layers"]


def test_jrc_and_dswx_validation(regimes_done):
    prov = regimes_done["provenance"]
    if "jrc" not in prov:
        pytest.skip("rasterio missing")
    assert prov["jrc"]["unusual_open_water_km2"] > 0
    assert 80 <= prov["opera_dswx_agreement_pct"] <= 100
    assert "not ground-truth accuracy" in prov["opera_dswx"]["note"]
    wet_entry = next(t for t in regimes_done["timeline"] if t["date"] == "2026-10-09")
    assert wet_entry["metrics"]["dswx_agreement_pct"] == prov["opera_dswx_agreement_pct"]


# ------------------------------------------------------------------ 04 exposure (offline OSM file)
def test_exposure_from_local_osm_file(store, processed, tmp_path):
    pytest.importorskip("geopandas")
    from geosar_pipeline import exposure
    west, south, east, north = BOUNDS
    with np.load(store / AOI / "time_series_cube.npz") as z:
        wet_any = ((z["cls"] == 1) | (z["cls"] == 2)).all(0)
    rows, cols = wet_any.shape
    r, c = np.argwhere(wet_any)[len(np.argwhere(wet_any)) // 2]
    lat = north - (r + 0.5) * (north - south) / rows
    lon = west + (c + 0.5) * (east - west) / cols
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"highway": "secondary", "name": "Wet Road", "osmid": 1, "element": "way"},
         "geometry": {"type": "LineString", "coordinates": [[lon - 0.002, lat], [lon + 0.002, lat]]}},
        {"type": "Feature", "properties": {"place": "village", "name": "Dry Village", "osmid": 2, "element": "node"},
         "geometry": {"type": "Point", "coordinates": [west + 0.001, south + 0.001]}},
        {"type": "Feature", "properties": {"highway": "footway", "name": "Footpath", "osmid": 3, "element": "way"},
         "geometry": {"type": "LineString", "coordinates": [[lon - 0.001, lat], [lon + 0.001, lat]]}},
    ]}
    osm = tmp_path / "osm.geojson"
    osm.write_text(json.dumps(fc))
    out = exposure.run(AOI, store, osm_file=str(osm), log=lambda *_: None)
    names = [f["properties"]["name"] for f in out["features"]]
    assert names == ["Wet Road"]                        # dry village + footway excluded
    p = out["features"][0]["properties"]
    assert p["wet_observations"] == 2 and p["total_observations"] == 2
    assert out["_meta"]["threshold"] == 2 and "lowered" in out["_meta"]["note"]
    assert "never a damage claim" in out["_meta"]["note"]


# ------------------------------------------------------------------ 05 mirror + backend serves the pack
def test_offline_mirror(store, processed, tmp_path):
    from geosar_pipeline import mirror
    m = mirror.run(store, tmp_path / "manifest.json")
    a = next(x for x in m["aois"] if x["aoi_id"] == AOI)
    assert [t["date"] for t in a["timeline"]] == ["2026-10-09", "2026-11-02"]
    assert a["synthetic_test_data"] is True


def test_backend_serves_the_generated_pack(store, processed, monkeypatch):
    """The FastAPI app pointed at the produced pack answers /inspect with real evidence."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    api_root = REPO / "services" / "api"
    monkeypatch.setenv("GEOSAR_DATA_STORE", str(store))
    for k in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[k]
    monkeypatch.syspath_prepend(str(api_root))
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        health = client.get("/api/v1/health").json()["data"]["data_packs"][AOI]
        assert health["cube"] and health["overlays"] >= 5 and health["synthetic_test_data"]
        # pick a pixel that is flooded vegetation on the wet date
        with np.load(store / AOI / "time_series_cube.npz") as z:
            r, c = np.argwhere(z["cls"][0] == FLOODED_VEG)[0]
            rows, cols = z["cls"].shape[1:]
        west, south, east, north = BOUNDS
        lat = north - (r + 0.5) * (north - south) / rows
        lon = west + (c + 0.5) * (east - west) / cols
        d = client.get(f"/api/v1/aois/{AOI}/inspect", params={"lat": lat, "lon": lon}).json()["data"]
        assert d["classes"][0] == "flooded_veg" and d["delta_hh_db"] >= 3.0 and d["peak_date"] == "2026-10-09"
        card = client.post("/api/v1/evidence-card", json={"aoi_id": AOI, "telemetry": d}).json()["data"]["card"]
        assert "double-bounce" in card["radar_physics_evidence"]
        assert card["data_notice"].startswith("SYNTHETIC TEST DATA")
        png = client.get(f"/api/v1/layers/{AOI}/open_water.png", params={"date": "2026-10-09"})
        assert png.headers["x-geosar-fallback"] == "false"
        season = client.get(f"/api/v1/layers/{AOI}/hydroperiod.png", params={"date": "2026-10-09"})
        assert season.headers["x-geosar-overlay"] == "hydroperiod.png"   # season layer fallback
    for k in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[k]
