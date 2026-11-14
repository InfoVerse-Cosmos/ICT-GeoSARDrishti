#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# GeoSAR Drishti — one-command "bring your own data" analyser.
#
#   1. Put your NISAR L2 GCOV .h5 granules in the ./DATA folder (see DATA/README.md).
#   2. Run ./analyze.sh
#
# It auto-detects the area from your granules, builds the analysis pack, and
# starts the app (FastAPI :8000 + Vite :5173). No bounding box or config needed.
#
#   AOI_ID=aoi_my_delta AOI_NAME="My Delta" ./analyze.sh   # optional overrides
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$ROOT/DATA"
# .env (GEOSAR_DATA_DIR) can point at a folder on another drive / mount
DATA_DIR="$(python3 "$ROOT/scripts/print_data_dir.py" 2>/dev/null || echo "$DATA_DIR")"
PVENV="$ROOT/scripts/.venv"

note() { printf "\033[36m[analyze]\033[0m %s\n" "$*"; }
err()  { printf "\033[31m[analyze]\033[0m %s\n" "$*" >&2; }

# --- 1. check for granules --------------------------------------------------
shopt -s nullglob
granules=("$DATA_DIR"/*.h5)
shopt -u nullglob
if [[ ${#granules[@]} -eq 0 ]]; then
  err "No NISAR .h5 granules found in $DATA_DIR"
  err "Download NISAR L2 GCOV .h5 files for your area (NASA Earthdata/ASF or ISRO Bhoonidhi),"
  err "copy them into the DATA/ folder, then run ./analyze.sh again. See DATA/README.md."
  exit 1
fi
note "Found ${#granules[@]} granule(s) in $DATA_DIR"

# --- 2. processing environment ----------------------------------------------
PYBIN="$(command -v python3.11 || command -v python3 || true)"
if [[ -z "$PYBIN" ]]; then err "python3 not found. Install Python 3.11+."; exit 1; fi
if [[ ! -d "$PVENV" ]]; then
  note "Creating processing environment (first run only)…"
  "$PYBIN" -m venv "$PVENV"
fi
# shellcheck disable=SC1091
source "$PVENV/bin/activate"
note "Installing processing dependencies…"
pip install --quiet --upgrade pip
if ! pip install --quiet numpy h5py pyproj; then
  err "Could not install the core processing dependencies (numpy, h5py, pyproj)."
  err "If a wheel failed to build, install Python 3.11 and delete scripts/.venv, then retry."
  exit 1
fi
# scikit-learn powers the optional GMM regime layer; best-effort, the pipeline degrades without it.
pip install --quiet scikit-learn || note "scikit-learn unavailable — GMM regimes will be skipped."

# --- 3. build the pack from your data ---------------------------------------
# No AOI_ID/AOI_NAME needed: each track/frame stack in the folder becomes its own area automatically.
EXTRA=()
[[ -n "${AOI_ID:-}" ]] && EXTRA+=(--aoi-id "$AOI_ID")
[[ -n "${AOI_NAME:-}" ]] && EXTRA+=(--name "$AOI_NAME")
note "Building the analysis pack (area auto-detected from the granules)…"
python "$ROOT/scripts/byod_build_aoi.py" ${EXTRA[@]+"${EXTRA[@]}"} --with-regimes --with-osm
deactivate || true

# --- 4. start the app -------------------------------------------------------
note "Pack built. Starting the app… (Ctrl-C stops it)"
exec "$ROOT/run.sh"
