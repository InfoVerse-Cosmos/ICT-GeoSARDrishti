"""Analyse-any-area job endpoint: validation, token gate, single-job rule (no real job is started)."""
from __future__ import annotations

from app.routers import analyze

GOOD = {"bbox": [93.9, 26.75, 94.3, 27.05], "start": "2026-07-01", "end": "2026-11-30"}


def _post(client, **over):
    return client.post("/api/v1/analyze", json={**GOOD, **over}).json()


def test_capabilities_report_limits_and_token_state(client, monkeypatch):
    monkeypatch.setattr(analyze, "_token_configured", lambda: False)
    d = client.get("/api/v1/analyze").json()["data"]
    assert d["token_configured"] is False and d["max_span_deg"] == analyze.MAX_SPAN_DEG


def test_rejects_bad_requests_with_plain_messages(client, monkeypatch):
    monkeypatch.setattr(analyze, "_token_configured", lambda: True)
    cases = [
        (dict(bbox=[1, 2, 3]), "bbox must be"),
        (dict(bbox=[94.3, 26.75, 93.9, 27.05]), "not a valid"),
        (dict(bbox=[90.0, 26.0, 95.0, 27.0]), "too large"),
        (dict(bbox=[94.0, 26.0, 94.001, 26.001]), "too small"),
        (dict(start="2026-11-30", end="2026-07-01"), "date range"),
        (dict(start="not-a-date"), "YYYY-MM-DD"),
        (dict(name="<script>alert(1)</script>"), "name may only"),
    ]
    for over, text in cases:
        body = _post(client, **over)
        assert body["status"] == "invalid_request" and text in body["warning"], (over, body["warning"])


def test_missing_token_is_a_clear_message_not_a_crash(client, monkeypatch):
    monkeypatch.setattr(analyze, "_token_configured", lambda: False)
    body = _post(client)
    assert body["status"] == "no_token" and "EARTHDATA_TOKEN" in body["warning"]


def test_valid_request_starts_one_job_and_blocks_a_second(client, monkeypatch, tmp_path):
    monkeypatch.setattr(analyze, "_token_configured", lambda: True)
    monkeypatch.setattr(analyze, "JOB_DIR", tmp_path)
    started = []

    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(analyze.subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or FakeProc())
    analyze.JOBS.clear()
    first = _post(client, name="Brahmaputra bend")
    assert first["status"] == "started" and first["data"]["status"] == "running"
    cmd = started[0]
    assert "--stream" in cmd and "--bbox" in cmd and cmd[cmd.index("--name") + 1] == "Brahmaputra bend"
    assert all(isinstance(c, str) for c in cmd)                      # no shell, plain argv
    second = _post(client)
    assert second["status"] == "busy"
    job = client.get(f"/api/v1/analyze/{first['data']['job_id']}").json()["data"]
    assert job["status"] == "running" and job["aoi_id"].startswith("aoi_c")
    assert client.get("/api/v1/analyze/nope").json()["status"] == "unknown_job"
    analyze.JOBS.clear()


# ---------------------------------------------------------------- ETA countdown + place search
def test_eta_is_a_sensible_countdown_for_each_phase():
    run = "streaming the area from NASA"
    assert analyze._eta("running", "searching NASA catalogue", None, 0, []) is None          # unknown yet
    fresh = analyze._eta("running", run, 3, 0, [])
    assert 300 < fresh < 900                                                                  # one parallel batch + post-processing
    assert analyze._eta("running", run, 10, 3, [400, 400, 400]) > analyze._eta("running", run, 10, 9, [400, 400, 400])
    assert analyze._eta("running", "classifying water + hydroperiod", 3, 3, []) > analyze._eta("running", "building regimes", 3, 3, [])
    assert analyze._eta("done", "finished", 3, 3, []) == 0


def test_geocode_returns_places_and_caches(client, monkeypatch):
    calls = []

    class R:
        def raise_for_status(self): pass
        def json(self): return [{"display_name": "Kedarnath, Uttarakhand, India", "lat": "30.734", "lon": "79.067", "type": "hamlet"}]

    monkeypatch.setattr(analyze, "_GEO_CACHE", {})
    monkeypatch.setattr(analyze.httpx, "get", lambda *a, **k: calls.append(k) or R())
    first = client.get("/api/v1/geocode", params={"q": "Kedarnath"}).json()
    assert first["data"]["results"][0]["lat"] == 30.734 and first["data"]["results"][0]["lon"] == 79.067
    assert "User-Agent" in calls[0]["headers"]
    client.get("/api/v1/geocode", params={"q": " kedarnath "})
    assert len(calls) == 1                                                                  # second search served from cache


def test_geocode_failure_and_short_query_are_graceful(client, monkeypatch):
    def boom(*a, **k): raise analyze.httpx.ConnectError("offline")
    monkeypatch.setattr(analyze, "_GEO_CACHE", {})
    monkeypatch.setattr(analyze.httpx, "get", boom)
    body = client.get("/api/v1/geocode", params={"q": "Guwahati"}).json()
    assert body["status"] == "geocode_unavailable" and body["data"]["results"] == [] and "type coordinates" in body["warning"]
    assert client.get("/api/v1/geocode", params={"q": "x"}).json()["status"] == "invalid_request"


def test_stop_cancels_a_running_job_and_kills_its_process_tree(client, monkeypatch, tmp_path):
    monkeypatch.setattr(analyze, "_token_configured", lambda: True)
    monkeypatch.setattr(analyze, "JOB_DIR", tmp_path)
    killed = []

    class FakeProc:
        pid = 4242
        alive = True
        def poll(self): return None if self.alive else -9
        def wait(self, timeout=None): return -9
        def kill(self): self.alive = False

    proc = FakeProc()
    monkeypatch.setattr(analyze.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(analyze, "_kill_tree", lambda p: (killed.append(p.pid), setattr(p, "alive", False)))
    analyze.JOBS.clear()
    job_id = _post(client)["data"]["job_id"]
    res = client.post(f"/api/v1/analyze/{job_id}/stop").json()
    assert res["status"] == "stopped" and res["data"]["status"] == "cancelled" and res["data"]["phase"] == "stopped"
    assert killed == [4242]
    assert analyze._running() is None                              # a new analysis may start straight away
    assert client.post("/api/v1/analyze/nope/stop").json()["status"] == "unknown_job"
    analyze.JOBS.clear()


def test_disabled_when_the_pipeline_is_absent_or_switched_off(client, monkeypatch):
    """A public deployment (no scripts/ next to the API) or GEOSAR_ENABLE_ANALYZE=0 never starts jobs."""
    monkeypatch.setattr(analyze, "_token_configured", lambda: True)
    monkeypatch.setenv("GEOSAR_ENABLE_ANALYZE", "0")
    assert client.get("/api/v1/analyze").json()["data"]["enabled"] is False
    body = _post(client)
    assert body["status"] == "disabled" and "own machine" in body["warning"]
    monkeypatch.delenv("GEOSAR_ENABLE_ANALYZE")
    monkeypatch.setattr(analyze, "REPO_ROOT", analyze.REPO_ROOT / "does_not_exist")
    assert analyze._enabled() is False


# ---------------------------------------------------------------- choose which passes to fetch
def test_nisar_passes_groups_by_track_and_recommends_the_longest(monkeypatch):
    from app.services import nisar_passes

    def entry(track, frame, day, coll_name="NISAR_L2_PR_GCOV_%s_%s_A_%s_4005_DHDH_A_2026%s T230529_2026%s T230603_P05023_N_F_J_001"):
        return {"producer_granule_id": f"NISAR_L2_PR_GCOV_025_{track}_A_{frame}_4005_DHDH_A_2026{day}T230529_2026{day}T230603_P05023_N_F_J_001.h5"}

    feeds = {
        "NISAR_L2_GCOV_PROVISIONAL_V1": [entry("040", "015", "0710"), entry("040", "015", "0722"), entry("156", "012", "0707")],
        "NISAR_L2_GCOV_V1": [entry("040", "015", "1107"), entry("040", "015", "1107")],     # duplicate date is de-duplicated
    }

    class R:
        def __init__(self, short): self.short = short
        def raise_for_status(self): pass
        def json(self): return {"feed": {"entry": feeds[self.short]}}

    monkeypatch.setattr(nisar_passes.httpx, "get", lambda url, params, timeout: R(params["short_name"]))
    out = nisar_passes.find_passes([93.9, 26.75, 94.3, 27.05], "2026-07-01", "2026-11-30")
    assert out["recommended"] == "040/015"
    g = out["groups"][0]
    assert [p["date"] for p in g["passes"]] == ["2026-07-10", "2026-07-22", "2026-11-07"]
    assert [p["maturity"] for p in g["passes"]] == ["PROVISIONAL", "PROVISIONAL", "VALIDATED"]
    assert out["groups"][1]["track_frame"] == "156/012"


def test_passes_endpoint_validates_and_degrades_gracefully(client, monkeypatch):
    from app.routers import analyze as a
    bad = client.post("/api/v1/analyze/passes", json={"bbox": [90, 26, 95, 27], "start": "2026-07-01", "end": "2026-07-20"}).json()
    assert bad["status"] == "invalid_request"
    monkeypatch.setattr(a.nisar_passes, "find_passes", lambda *x, **k: (_ for _ in ()).throw(a.httpx.ConnectError("offline")))
    down = client.post("/api/v1/analyze/passes", json=GOOD).json()
    assert down["status"] == "catalogue_unavailable" and "internet" in down["warning"]
    monkeypatch.setattr(a.nisar_passes, "find_passes", lambda *x, **k: {"groups": [], "recommended": None})
    none = client.post("/api/v1/analyze/passes", json=GOOD).json()
    assert "no NISAR" in none["warning"].lower() or "no nisar" in none["warning"].lower()


def test_start_passes_the_chosen_track_and_dates_to_the_pipeline(client, monkeypatch, tmp_path):
    monkeypatch.setattr(analyze, "_token_configured", lambda: True)
    monkeypatch.setattr(analyze, "JOB_DIR", tmp_path)
    started = []

    class FakeProc:
        def poll(self): return None

    monkeypatch.setattr(analyze.subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or FakeProc())
    analyze.JOBS.clear()
    body = _post(client, track_frame="040/015", dates=["2026-07-22", "2026-07-10"])
    assert body["status"] == "started"
    cmd = started[0]
    assert cmd[cmd.index("--track-frame") + 1] == "040/015"
    assert cmd[cmd.index("--only-dates") + 1] == "2026-07-10,2026-07-22"          # sorted, unique
    analyze.JOBS.clear()
    for over, text in [(dict(dates=["2026-07-10"]), "at least 2"), (dict(dates=["2026-07-10", "2026-12-25"]), "inside the chosen"),
                       (dict(dates=["x", "y"]), "YYYY-MM-DD"), (dict(track_frame="40-15"), "track_frame")]:
        r = _post(client, **over)
        assert r["status"] == "invalid_request" and text in r["warning"], (over, r)