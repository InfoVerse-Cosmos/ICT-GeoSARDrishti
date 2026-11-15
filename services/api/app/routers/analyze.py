"""Analyse ANY area / date range from NASA Earthdata Cloud, on this machine (window-only streaming).

POST /api/v1/analyze            start a job {bbox:[w,s,e,n], start, end, name?}
GET  /api/v1/analyze/{job_id}   status + progress + last log lines
GET  /api/v1/analyze            capabilities (token configured? limits) + recent jobs

The job is the same offline pipeline (scripts/byod_build_aoi.py --stream) run as a subprocess; when it
finishes the new pack is picked up by the data store automatically (no restart). One job at a time.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import uuid
from datetime import date

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from ..config import DATA_STORE, REPO_ROOT, get_settings
from ..envelope import envelope
from ..services import nisar_passes

router = APIRouter(tags=["analyze"])

MAX_SPAN_DEG = 0.6            # keep a job to ~65 km x 65 km (time + memory bound)
MAX_DAYS = 400
JOBS: dict[str, dict] = {}
JOB_DIR = REPO_ROOT / "scripts" / "_work" / "jobs"


def _token_configured() -> bool:
    import os
    if os.environ.get("EARTHDATA_TOKEN"):
        return True
    for f in (REPO_ROOT / "services" / "api" / ".env", REPO_ROOT / ".env"):
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                k, _, v = line.partition("=")
                if k.strip() == "EARTHDATA_TOKEN" and v.strip():
                    return True
        except OSError:
            pass
    return False


def _enabled() -> bool:
    """Only on a developer/analyst machine: needs the repo's pipeline script, and can be switched off with
    GEOSAR_ENABLE_ANALYZE=0. A public deployment (API image without scripts/) never exposes it, so strangers
    cannot start heavy NASA-streaming jobs on the server."""
    import os
    if os.environ.get("GEOSAR_ENABLE_ANALYZE", "").strip() == "0":
        return False
    return (REPO_ROOT / "scripts" / "byod_build_aoi.py").is_file()


_DISABLED_MSG = "Analysing new areas is only available when the app runs on your own machine (it needs the local pipeline)."


def _pipeline_python() -> str:
    for rel in ("scripts/.venv/Scripts/python.exe", "scripts/.venv/bin/python"):
        p = REPO_ROOT / rel
        if p.exists():
            return str(p)
    return sys.executable


class AnalyzeRequest(BaseModel):
    bbox: list[float]
    start: str
    end: str
    name: str | None = None
    track_frame: str | None = None      # chosen from /analyze/passes (same-track passes only)
    dates: list[str] | None = None      # the passes the user ticked (at least 2)


def _validate(req: AnalyzeRequest) -> str | None:
    if len(req.bbox) != 4:
        return "bbox must be [west, south, east, north]"
    w, s, e, n = req.bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        return "bbox is not a valid WGS84 box (west<east, south<north)"
    if (e - w) > MAX_SPAN_DEG or (n - s) > MAX_SPAN_DEG:
        return f"area too large: keep each side under {MAX_SPAN_DEG} degrees (about 65 km)"
    if (e - w) < 0.02 or (n - s) < 0.02:
        return "area too small: at least 0.02 degrees (about 2 km) per side"
    try:
        d0, d1 = date.fromisoformat(req.start), date.fromisoformat(req.end)
    except ValueError:
        return "dates must be YYYY-MM-DD"
    if d1 < d0 or (d1 - d0).days > MAX_DAYS:
        return f"date range must be 0-{MAX_DAYS} days with end after start"
    if req.track_frame is not None and not re.match(r"^\d{3}/\d{3}$", req.track_frame):
        return "track_frame must look like 040/015"
    if req.dates is not None:
        try:
            ds = sorted({date.fromisoformat(x) for x in req.dates})
        except ValueError:
            return "dates must be YYYY-MM-DD"
        if len(ds) < 2:
            return "Choose at least 2 passes (a comparison needs two dates)."
        if len(ds) > 60:
            return "Too many passes selected (max 60)."
        if ds[0] < d0 or ds[-1] > d1:
            return "Selected passes must lie inside the chosen date range."
    if req.name and (len(req.name) > 80 or not re.match(r"^[\w .,'()/&-]+$", req.name)):
        return "name may only contain letters, numbers and simple punctuation (max 80 chars)"
    return None


def _running() -> dict | None:
    for j in JOBS.values():
        if j["proc"].poll() is None:
            return j
    return None


STREAM_WORKERS = 3          # must match stream.fetch_stack(workers=3)
DEFAULT_PASS_S = 360        # seconds for one parallel batch of passes when nothing has finished yet (observed 130-500)
POST_S = {"streaming": 150, "classifying": 120, "regimes": 90, "roads": 60}   # work left after streaming, per phase


def _eta(status: str, phase: str, total, done: int, durations: list[float]):
    """Approximate seconds left (None while the catalogue search is still running)."""
    if status != "running":
        return 0
    if total is None:
        return None
    if phase.startswith("streaming"):
        remaining = max(total - done, 0)
        per_batch = (sum(durations) / len(durations)) if durations else DEFAULT_PASS_S
        batches = -(-remaining // STREAM_WORKERS)
        return int(batches * per_batch + POST_S["streaming"])
    key = "classifying" if "classifying" in phase else "regimes" if "regimes" in phase else "roads"
    return POST_S[key]


def _progress(job: dict) -> dict:
    try:
        lines = job["log"].read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    total, done, phase = None, 0, "searching NASA catalogue"
    durations: list[float] = []
    for ln in lines:
        m = re.search(r"using track/frame \S+: \[(.*)\]", ln)
        if m:
            total = len(re.findall(r"'\d{4}-\d\d-\d\d'", m.group(1)))
            phase = "streaming the area from NASA"
        if re.match(r"^\[stream\] \d{4}-\d\d-\d\d ", ln):
            done += 1
            m2 = re.search(r"MB in ([\d.]+) s", ln)
            if m2:
                durations.append(float(m2.group(1)))
        if ln.startswith("[02]"):
            phase = "classifying water + hydroperiod"
        if ln.startswith("[03]"):
            phase = "building regimes"
        if ln.startswith("[04]"):
            phase = "finding roads and villages (OpenStreetMap)"
    rc = job["proc"].poll()
    status = "running" if rc is None else ("cancelled" if job.get("cancelled") else "done" if rc == 0 else "error")
    pct = None
    if total:
        pct = round(min(done / total, 1.0) * 70) if status == "running" and phase.startswith("streaming") else None
    if status == "done":
        phase, pct = "finished", 100
    elif status == "cancelled":
        phase = "stopped"
    elif status == "error":
        phase = "failed"
    elif phase != "searching NASA catalogue" and not phase.startswith("streaming"):
        pct = 70 + (10 if "classifying" in phase else 20 if "regimes" in phase else 27 if "roads" in phase else 0)
    eta = _eta(status, phase, total, done, durations)
    err = [ln for ln in lines if "ERROR" in ln or "Traceback" in ln or "error:" in ln]
    return {
        "job_id": job["id"], "status": status, "phase": phase, "percent": pct,
        "dates_total": total, "dates_streamed": done, "aoi_id": job["aoi_id"], "eta_s": eta,
        "elapsed_s": round((job.get("ended") or time.time()) - job["started"]),
        "log_tail": lines[-14:], "error": err[-1] if status == "error" and err else None,
    }


_GEO_CACHE: dict[str, list] = {}


@router.get("/geocode")
def geocode(q: str = "") -> dict:
    """Place-name search (OpenStreetMap Nominatim) for "Analyse a new area". Only the typed text is sent."""
    q = " ".join(q.split())[:100]
    if len(q) < 2:
        return envelope({"results": []}, status="invalid_request", fallback_active=True, warning="Type at least 2 letters.")
    key = q.lower()
    if key in _GEO_CACHE:
        return envelope({"results": _GEO_CACHE[key]})
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search",
                      params={"q": q, "format": "jsonv2", "limit": 6, "addressdetails": 0},
                      headers={"User-Agent": "GeoSAR-Drishti/1.0 (NASA Space Apps hackathon project)"},
                      timeout=get_settings().external_timeout_seconds)
        r.raise_for_status()
        results = [{"name": x.get("display_name", q), "lat": float(x["lat"]), "lon": float(x["lon"]),
                    "kind": x.get("type") or x.get("category")} for x in r.json()]
    except Exception as exc:  # noqa: BLE001 - offline / rate limited: the map and typed coordinates still work
        return envelope({"results": []}, status="geocode_unavailable", fallback_active=True,
                        warning=f"Place search is unavailable right now ({type(exc).__name__}). Pick on the map or type coordinates.")
    _GEO_CACHE[key] = results
    return envelope({"results": results}, warning=None if results else "No place found. Try a bigger nearby town or river.")


class PassesRequest(BaseModel):
    bbox: list[float]
    start: str
    end: str


@router.post("/analyze/passes")
def passes(req: PassesRequest) -> dict:
    """List the NISAR passes NASA has over this area and period, so the user can choose which dates to fetch."""
    problem = _validate(AnalyzeRequest(bbox=req.bbox, start=req.start, end=req.end))
    if problem:
        return envelope(None, status="invalid_request", fallback_active=True, warning=problem)
    try:
        found = nisar_passes.find_passes(req.bbox, req.start, req.end, timeout=max(get_settings().external_timeout_seconds, 15.0))
    except Exception as exc:  # noqa: BLE001 - offline / CMR busy
        return envelope(None, status="catalogue_unavailable", fallback_active=True,
                        warning=f"Could not reach the NASA catalogue ({type(exc).__name__}). Check the internet and try again.")
    if not found["groups"]:
        return envelope(found, warning="NASA has no NISAR GCOV pass over this area in this period. Try a wider date range or another area.")
    return envelope(found)


@router.get("/analyze")
def capabilities() -> dict:
    cur = _running()
    return envelope({
        "enabled": _enabled(),
        "token_configured": _token_configured(),
        "max_span_deg": MAX_SPAN_DEG, "max_days": MAX_DAYS,
        "running_job": cur["id"] if cur else None,
        "recent": [_progress(j) for j in list(JOBS.values())[-5:]],
    })


@router.post("/analyze")
def start(req: AnalyzeRequest) -> dict:
    if not _enabled():
        return envelope(None, status="disabled", fallback_active=True, warning=_DISABLED_MSG)
    problem = _validate(req)
    if problem:
        return envelope(None, status="invalid_request", fallback_active=True, warning=problem)
    if not _token_configured():
        return envelope(None, status="no_token", fallback_active=True,
                        warning="NASA Earthdata token missing. Add EARTHDATA_TOKEN to services/api/.env "
                                "(urs.earthdata.nasa.gov -> Generate Token), then try again.")
    cur = _running()
    if cur:
        return envelope(_progress(cur), status="busy", fallback_active=True,
                        warning="Another analysis is still running. Wait for it to finish.")
    job_id = uuid.uuid4().hex[:10]
    w, s, e, n = req.bbox
    aoi_id = f"aoi_c{abs(round((s + n) / 2 * 100)):04d}{'n' if (s + n) >= 0 else 's'}_{abs(round((w + e) / 2 * 100)):05d}{'e' if (w + e) >= 0 else 'w'}"
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    log = JOB_DIR / f"{job_id}.log"
    cmd = [_pipeline_python(), str(REPO_ROOT / "scripts" / "byod_build_aoi.py"), "--stream",
           "--bbox", f"{w},{s},{e},{n}", "--start", req.start, "--end", req.end,
           "--aoi-id", aoi_id, "--data-store", str(DATA_STORE), "--with-regimes", "--with-osm"]
    if req.name:
        cmd += ["--name", req.name]
    if req.track_frame:
        cmd += ["--track-frame", req.track_frame]
    if req.dates:
        cmd += ["--only-dates", ",".join(sorted(set(req.dates)))]
    env = {**__import__("os").environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    fh = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=fh, stderr=subprocess.STDOUT, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            start_new_session=(os.name != "nt"))
    JOBS[job_id] = {"id": job_id, "proc": proc, "log": log, "started": time.time(), "ended": None, "aoi_id": aoi_id}
    return envelope(_progress(JOBS[job_id]), status="started")


def _kill_tree(proc: subprocess.Popen) -> None:
    """Stop the job AND its worker processes (the streaming pool)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001 - fall back to the plain kill below
        pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


@router.post("/analyze/{job_id}/stop")
def stop(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        return envelope(None, status="unknown_job", fallback_active=True, warning="Unknown job id.")
    if job["proc"].poll() is None:
        job["cancelled"] = True
        _kill_tree(job["proc"])
        try:
            job["proc"].wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        job["ended"] = time.time()
    return envelope(_progress(job), status="stopped" if job.get("cancelled") else "ok")


@router.get("/analyze/{job_id}")
def status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        return envelope(None, status="unknown_job", fallback_active=True, warning="Unknown job id.")
    if job["proc"].poll() is not None and not job["ended"]:
        job["ended"] = time.time()
    return envelope(_progress(job))