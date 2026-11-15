"""Shared pytest fixtures for the GeoSAR Drishti FastAPI backend.

Run from services/api:   python -m pytest tests -v
Live-network tests are skipped unless RUN_NETWORK_TESTS=1.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

# Force deterministic mode: explicit empty env vars override any local .env file.
for _var in ("EARTHDATA_TOKEN", "LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"):
    os.environ[_var] = ""
os.environ["CORS_ORIGINS"] = "*"

from fastapi.testclient import TestClient  # noqa: E402

from app import data_store as ds_module  # noqa: E402
from app.main import app  # noqa: E402
from app.services import raster_sampler  # noqa: E402
from helpers import write_exposure, write_pack  # noqa: E402

AOI_IDS = ["aoi_assam_majuli", "aoi_nagpur_kanhan"]
ENVELOPE_KEYS = {"status", "aoi_id", "source_mode", "fallback_active", "warning", "data"}


def pytest_configure(config):
    config.addinivalue_line("markers", "network: hits real external services (RUN_NETWORK_TESTS=1)")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_NETWORK_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="set RUN_NETWORK_TESTS=1 to run live network tests")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def client():
    # raise_server_exceptions=False so we observe what a real browser would receive.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_llm_state():
    from app.services import evidence_narrator
    evidence_narrator._NARRATION_CACHE.clear()
    evidence_narrator._cooldown_until.clear()
    yield


@pytest.fixture(autouse=True)
def _clear_cube_cache():
    raster_sampler._load_cube.cache_clear()
    yield
    raster_sampler._load_cube.cache_clear()


@pytest.fixture(autouse=True)
def seed_data_store(monkeypatch, tmp_path_factory):
    """Seed a temp data store with synthetic packs for both standard AOIs.

    The repo ships no data packs (they are built on the user's machine), so every
    test that lists AOIs, resolves a manifest or loads a cube would otherwise see an
    empty store. This builds pack-free synthetic AOIs in a temp DATA_STORE and points
    BOTH the data store and the raster sampler at it, so ``store.get(aoi)`` returns the
    synthetic manifest and the cube loads from the same place.

    Runs before the per-test cube fixtures (synthetic_cube / no_cube), which then only
    re-point the raster sampler at their own cube directory; the seeded manifest keeps
    bounds/timeline available to the routers in every case.
    """
    data_store = tmp_path_factory.mktemp("data_store")
    for aoi_id in AOI_IDS:
        write_pack(data_store, aoi_id, cube=True, full=True)
    # The Assam pack stands in for the real Majuli pack: give it OSM exposure candidates.
    write_exposure(data_store, "aoi_assam_majuli")

    monkeypatch.setattr(ds_module, "DATA_STORE", data_store)
    monkeypatch.setattr(raster_sampler, "DATA_STORE", data_store)
    raster_sampler._load_cube.cache_clear()
    ds_module.store.load()
    yield data_store


def assert_envelope(body: dict) -> None:
    assert isinstance(body, dict)
    assert ENVELOPE_KEYS <= set(body), f"missing envelope keys: {ENVELOPE_KEYS - set(body)}"
    assert isinstance(body["fallback_active"], bool)
    assert body["source_mode"] in {"LIVE_API", "LOCAL_VERIFIED_CACHE"}
