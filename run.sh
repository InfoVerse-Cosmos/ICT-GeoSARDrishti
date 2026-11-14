#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# GeoSAR Drishti — one-command local dev runner.
# Starts the FastAPI backend (:8000) and the Vite frontend (:5173) together,
# wires the frontend to the backend, and cleans both up on Ctrl-C.
#
#   ./run.sh            # install deps if needed, then run both
#   ./run.sh --no-install   # skip dependency install (faster restarts)
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT/services/api"
WEB_DIR="$ROOT/apps/web"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
DO_INSTALL=1
[[ "${1:-}" == "--no-install" ]] && DO_INSTALL=0

note() { printf "\033[36m[geosar]\033[0m %s\n" "$*"; }
err()  { printf "\033[31m[geosar]\033[0m %s\n" "$*" >&2; }

# --- pick a Python: prefer 3.11 (SRS target), fall back to python3 ----------
PYBIN="$(command -v python3.11 || command -v python3 || true)"
if [[ -z "$PYBIN" ]]; then err "python3 not found. Install Python 3.11+."; exit 1; fi
PYVER="$("$PYBIN" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
if [[ "$PYVER" != "3.11" && "$PYVER" != "3.12" ]]; then
  note "Using Python $PYVER ($PYBIN). SRS targets 3.11; if dependency install fails, install Python 3.11."
fi
if ! command -v npm >/dev/null 2>&1; then err "npm not found. Install Node 18+."; exit 1; fi

# --- backend: venv + deps ---------------------------------------------------
VENV="$API_DIR/.venv"
# If an existing venv was built with a different Python than the one we picked, rebuild it.
if [[ -d "$VENV" ]]; then
  VENV_VER="$("$VENV/bin/python" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "?")"
  if [[ "$VENV_VER" != "$PYVER" ]]; then
    note "Existing venv is Python $VENV_VER but selected is $PYVER — recreating it."
    rm -rf "$VENV"
  fi
fi
if [[ ! -d "$VENV" ]]; then
  note "Creating backend virtualenv (Python $PYVER)…"
  "$PYBIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
if [[ "$DO_INSTALL" == "1" ]]; then
  note "Installing backend deps…"
  pip install --quiet --upgrade pip
  if ! pip install -r "$API_DIR/requirements.txt"; then
    err "Backend dependency install failed."
    err "Most likely your Python ($PYVER) has no prebuilt wheel for a dependency and the source build failed."
    err "Fix: install Python 3.11 (e.g. 'brew install python@3.11'), delete services/api/.venv, then re-run ./run.sh."
    exit 1
  fi
fi
[[ -f "$API_DIR/.env" ]] || { [[ -f "$ROOT/.env.example" ]] && cp "$ROOT/.env.example" "$API_DIR/.env" && note "Created services/api/.env from template."; }

# --- frontend: deps + API url ----------------------------------------------
if [[ "$DO_INSTALL" == "1" && ! -d "$WEB_DIR/node_modules" ]]; then
  note "Installing frontend deps (first run, this can take a minute)…"
  (cd "$WEB_DIR" && npm install --no-fund --no-audit)
fi
echo "VITE_API_BASE_URL=http://localhost:$API_PORT" > "$WEB_DIR/.env"

# --- start both, clean up on exit ------------------------------------------
API_PID=""; WEB_PID=""
cleanup() {
  note "Shutting down…"
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

note "Starting FastAPI on http://localhost:$API_PORT …"
( cd "$API_DIR" && exec uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" ) &
API_PID=$!

# wait for the API to answer /health before launching the UI
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
    note "Backend is up ✓"; break
  fi
  [[ "$i" == "30" ]] && err "Backend did not become healthy in time (check logs above)."
  sleep 1
done

note "Starting Vite on http://localhost:$WEB_PORT …"
( cd "$WEB_DIR" && exec npm run dev -- --port "$WEB_PORT" ) &
WEB_PID=$!

note "Both running. API: http://localhost:$API_PORT/docs  |  UI: http://localhost:$WEB_PORT"
note "Press Ctrl-C to stop both."
wait
