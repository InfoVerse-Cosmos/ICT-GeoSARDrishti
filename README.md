<!--
  Handbook Section 6 — Mandatory README structure (6 sections):
  1. Project Title & Problem Statement
  2. Team Details
  3. Solution Overview & Architecture
  4. Live Demo & Screenshots
  5. Installation & Setup Guide
  6. AI Usage Disclosure
  Live deployment URL MUST sit at the very top (Handbook Section 4).
-->

# 🛰️ Live Demo: <https://geosardrishti.infoversecosmostech.com>

[![GitHub Repository](https://img.shields.io/badge/GitHub-ICT--GeoSARDrishti-181717?logo=github&logoColor=white)](https://github.com/InfoVerse-Cosmos/ICT-GeoSARDrishti)

> Live app: <https://geosardrishti.infoversecosmostech.com>
> Source code: <https://github.com/InfoVerse-Cosmos/ICT-GeoSARDrishti>

---

# 1. Project Title & Problem Statement

## GeoSAR Drishti — *The Monsoon Dance of Water*

**NASA Space Apps Challenge 2026 · Nagpur (WCEM) · CH-06 "Dancing with the SARs"**

**Problem.** During the monsoon, floodplain managers cannot see where water spreads, how long it stays, or where it hides beneath vegetation — clouds blind optical satellites exactly when inundation peaks, and standard flood maps show only *open* water.

**What we built.** An interactive NASA–ISRO NISAR L-band ($24\,\text{cm}$) radar time-series console that reveals, across a whole monsoon season:

- **Open water vs. canopy-hidden water** — specular dark open water vs. L-band double-bounce flooded vegetation (`ΔHH ≥ +3 dB`).
- **Monsoon hydroperiod** — "wet in **M of N** valid NISAR observations" (never "days flooded").
- **Normal vs. unusual** — radar open water vs. JRC historical occurrence + OPERA DSWx inter-sensor agreement.
- **Repeatedly wet roads & settlements** — OSM exposure log of ground-inspection candidates.
- **Plain-language radar evidence cards** — grounded strictly on computed numbers.

> **Honest framing.** Every result is a *radar-derived surface/canopy-water indication for field inspection* — not a confirmed flood, depth, or damage claim. Agreement with OPERA is *inter-sensor agreement*, not ground-truth accuracy.

---

# 2. Team Details

**Team name:** Cosmos InfoVerse Techky · **Org:** InfoVerse Cosmos / InfoVerse Tech Services

| # | Full Name | GitHub Username | Affiliation | Role |
| :- | :-- | :-- | :-- | :-- |
| 1 | Pravin Tawade | `@cosmosinfoverse` | InfoVerse Cosmos | Team Owner — architecture, L-band SAR physics, mission lead |
| 2 | Kaushik Zade | `@kaushik7` | InfoVerse Cosmos | FastAPI backend, NASA `earthaccess` connector, offline raster processing |
| 3 | Sharv Dalal | `@shardstax` | InfoVerse Cosmos | Telemetry UI (React/MapLibre), monsoon time slider |
| 4 | Himanshu Sharma | `@lunar_node` | InfoVerse Cosmos | NISAR L2 GCOV data gate, PROVISIONAL/VALIDATED calibration, OPERA/JRC validation |
| 5 | Sakshi Manav Tayade | `@sakshitayade` | InfoVerse Cosmos | GMM regime clustering, ESA WorldCover, OSM exposure, Nagpur context |
| 6 | Prashan Arya | `@prashan_arya` | InfoVerse Cosmos | Evidence-card service, error/fallback QA, scientific review |

> **Team:** We are a 6-member professional team under **InfoVerse Cosmos**, registered and approved on the NASA Space Apps portal for this challenge. Work is shared across the team — engineering, research, validation and presentation — so contributions reach the project through collaboration, not only through direct code commits.

---

# 3. Solution Overview & Architecture

Two-tier hybrid client–server platform (true client–server separation, cloud-deployable, graceful offline fallbacks).

```text
apps/web (Vite + React 18 JS/JSX + MapLibre GL JS + Tailwind)
      │  HTTPS REST JSON + RGBA PNG overlays (CORS)
      ▼
services/api (Python 3.11 + FastAPI + Uvicorn + Rasterio + NumPy + earthaccess)
      ├─ Live connectors: NASA Earthdata CMR / ASF, optional OpenAI narrator (strict timeouts)
      └─ AOI packs built locally by `analyze` from your granules: RGBA-PNG overlays, time_series_cube.npz, GeoJSON
```

**Your areas, your data.** The app lists only the areas you analysed from your own NISAR granules (our reference runs: Majuli-Kaziranga, Assam, and Kanhan-Pench, Nagpur). Nothing is pre-loaded or simulated.

**Two audiences, one console.** A top-bar **Simple / Scientist** toggle switches the whole experience:

- **Simple (default)** — satellite backdrop, plain result layers (*Open water*, *Water hidden under plants*, *Repeatedly wet areas*), a one-line plain "what happened here" on map click, and a **one-click Analysis Report** — no dB, Otsu thresholds, or granule/track jargon.
- **Scientist** — the full telemetry console unchanged (per-scene Otsu/ΔHH thresholds, dB trajectories, granule/track-frame/polarization/maturity pills, provenance).

The **Analysis Report** (📊 button, either mode) summarises the current AOI in plain language — where water was, hydroperiod (M of N), what changed between passes (computed *within* a single track, since NISAR images an AOI from more than one track), which roads/settlements are inspection candidates — grounded strictly in computed numbers, with the honest caveat and a provenance footer (granules, dates, thresholds).

**Scientific pipeline (100% deterministic math):** γ⁰ HH/HV subset → validity + DEM-slope masks → speckle filter + dB conversion (`Ratio_dB = HH_dB − HV_dB`) → per-date 3-class classifier (Otsu open water, ΔHH double-bounce flooded vegetation, dry) → M-of-N hydroperiod → unsupervised GMM regimes → OPERA DSWx / JRC validation → OSM exposure.

**Tech stack**

| Layer | Technology |
| :-- | :-- |
| Frontend | React 18 (JS/JSX), Vite, MapLibre GL JS, Tailwind CSS, Recharts, Zustand |
| Backend | FastAPI, Uvicorn, Rasterio, NumPy, httpx, earthaccess |
| Processing | scikit-learn (GMM), scikit-image (Otsu), h5py, geopandas, osmnx, Pillow |
| Data | NASA–ISRO NISAR L2 GCOV, OPERA DSWx-S1/NI, EC JRC GSW, ESA WorldCover, OSM, GSDA/CGWB |
| Hosting | GitHub Pages / Vercel / Netlify (web) · Render / Railway / Cloud Run (API) |

Full design: [`Docs/geosar_intelligence_srs_and_implementation_blueprint.md`](Docs/geosar_intelligence_srs_and_implementation_blueprint.md) · build plan: [`Docs/IMPLEMENTATION_PLAN.md`](Docs/IMPLEMENTATION_PLAN.md).

---

# 4. Live Demo & Screenshots

- **Live app:** <https://geosardrishti.infoversecosmostech.com> (also pinned at the top of this README)
- **Demo video:** _TBD (optional)_
- **Screenshots:** _add after your first run (the repo ships none, so everything you see comes from your data)._

```text
[ Top mission bar: NISAR · dual-AOI selector · granule/track/pol/maturity pills · LIVE API / LOCAL CACHE ]
[ Center MapLibre viewport: SAR layers, AOI boundary, click-to-inspect ]
[ Bottom monsoon time slider: acquisition ticks + 27 Jul–10 Aug gap band ]
[ Right drawer: scene metrics · pixel dB trajectory + evidence card · OSM inspection log ]
```

---

# 5. Installation & Setup Guide

**Prerequisites:** Python 3.11+, Node 18+, git. Nothing else to configure.

> New here? Read the step-by-step **[User Guide](USER_GUIDE.md)** (setup, how to use the app, and a manual test checklist).

## ⚡ Quick start: one file does everything

This repo ships **no data and no pre-built results**. You bring your own NISAR granules; the app is built from them on your machine.

1. **Get the data.** Download NISAR **L2 GCOV** `.h5` files for your area and monsoon window (your responsibility; both sources give the same product):
   - NASA Earthdata / ASF: <https://search.earthdata.nasa.gov/> (collections `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GCOV_V1`)
   - ISRO Bhoonidhi: <https://bhoonidhi.nrsc.gov.in/>
2. **Drop the `.h5` files into the `DATA/` folder.** (Files are ~7 GB each and never committed. Short on disk? Keep them anywhere and set `GEOSAR_DATA_DIR=D:/my/folder` in `services/api/.env`.)
3. **Run ONE file:**

   ```bash
   analyze.bat        # Windows
   ./analyze.sh       # macOS / Linux
   ```
4. **Open <http://localhost:5173>** (if that port is busy the terminal shows the actual one), click **Explore the water story** (or open the map directly at `http://localhost:5173/#/explore`), pick your area at the top-left, or tap **📊 Report**.

`analyze` installs everything on first run, auto-detects every area in your folder (one area per satellite track/frame, so several incidents in one folder are fine), builds the analysis, and starts the app. Expect roughly 10-15 minutes for a few 7 GB granules (the OpenStreetMap road download is the slow part).

**Next time** (data already analysed) just start the app, no reprocessing: `run.bat` / `./run.sh`.
Add more granules later: copy them into `DATA/` and run `analyze` again; the new area appears automatically.

Nothing in `DATA/` yet? The app still opens and shows a "No NISAR data analysed yet" screen with these same steps. It never shows pre-loaded or simulated areas.

## Settings (optional): `services/api/.env`

Created automatically from `.env.example` on first run. Everything is optional.

| Key | What it does |
| :-- | :-- |
| `LLM_API_KEY` | OpenAI key for the optional plain-language wording on the Evidence Card (uses `gpt-4o-mini`, cheap). Blank = the built-in physics template is used. |
| `GEOSAR_DATA_DIR` | Where your `.h5` granules are (default `./DATA`). |
| `GEOSAR_DATA_STORE` | Where analysed results are written (default `services/api/data_store`). |
| `EARTHDATA_TOKEN` | NASA Earthdata token: enables **＋ New area** (stream any place from NASA) and the live CMR check. Optional; keep it only in this git-ignored file. |

**Evidence Card, honest by design.** The card first appears instantly from a deterministic physics template. If an OpenAI key is set, the AI re-words it a few seconds later; any number the AI writes that is not in the computed card is rejected, and the card says which engine wrote it. If the AI is unavailable (no key, no internet, rate limit) the built-in template stays: same numbers, nothing breaks.

## Analyse any area from NASA, no big downloads (optional)

Besides your own `.h5` files, the app can analyse **any place and date range** straight from NASA Earthdata Cloud. It reads only the window you ask for (about 90 MB per satellite pass instead of a ~7 GB file) and builds the same analysis.

1. Get a free NASA token: log in at <https://urs.earthdata.nasa.gov> → **Generate Token**, and put it in `services/api/.env` as `EARTHDATA_TOKEN=...` (that file is git-ignored; never commit it).
2. Start the app (`run.bat` / `./run.sh`) and open the map. Click **＋ New area** in the top bar.
3. Choose the place: **search** a name (e.g. "Guwahati"), **Draw on map** (drag a rectangle, or just click), **Use my location** (GPS), or type coordinates. Pick a date range, press **Find available passes** (a quick NASA catalogue search, nothing is downloaded) and tick the dates you want, then press **Start analysis**. If several satellite tracks cover the place, choose one (only passes from the same track can be compared); the last ticked date is used as the dry reference.
4. A progress bar with a time-left countdown runs; **Stop** cancels safely. When it finishes, the new area is added to the list and selected.

Limits: each side under 0.6° (about 65 km), up to 400 days, one analysis at a time. NISAR does not image every place every 12 days, so some areas or periods have few or no passes (the app tells you). Expect roughly 3 minutes per satellite pass. Streamed windows are cached under `DATA/_stream/` (or `GEOSAR_DATA_DIR`), results go to `GEOSAR_DATA_STORE`. This only works on your own machine: a hosted server never exposes it (`GEOSAR_ENABLE_ANALYZE=0` also switches it off).

## Run each tier manually (developers)
```bash
# Backend (FastAPI)
cd services/api
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (Vite + React), new terminal
cd apps/web && npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev
```
Tests: `cd services/api && python -m pytest tests -q` · `cd apps/web && npx vitest run` · `python -m pytest scripts/tests -q` (use the `scripts/.venv` created by `analyze`).

**Advanced build options:** `python scripts/byod_build_aoi.py --help` (custom id/name/bbox, WorldCover, DEM, JRC, OPERA DSWx, local OSM file).

**Deploy.** API: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` (set `CORS_ORIGINS`, optional `LLM_API_KEY`, `EARTHDATA_TOKEN`). Because results are generated, not shipped, run `analyze` on the server (or mount a volume at `GEOSAR_DATA_STORE`) so it has packs to serve. Web: `npm run build` in `apps/web`, host `dist` anywhere, with `VITE_API_BASE_URL` pointing at the API.

> **Honest framing applies to every result:** a radar-derived surface/canopy-water indication for field inspection, not a confirmed flood, depth, or damage claim. Hydroperiod is *M of N valid NISAR observations*, never "days flooded".

---

# 6. AI Usage Disclosure

Our team (**Cosmos InfoVerse Techky**) used generative AI tools strictly as human-supervised assistants, with full component-level transparency (Handbook Section 5):

| AI tool | Where it helped | Human engineering on top |
| :-- | :-- | :-- |
| Claude / Kiro, Gemini, GitHub Copilot | SRS/doc refinement; monorepo scaffold; FastAPI boilerplate (routers, response envelope, exception handlers); React component skeletons; config files | All SAR backscatter math, Otsu thresholds, ΔHH double-bounce logic, hydroperiod and area metrics, GMM regime mapping, validation, data-gate processing, integration, testing, and scientific review — authored and verified by the team |

- **In-app ML & narration:** `scikit-learn` Gaussian Mixture Models for unsupervised SAR time-series clustering; an **optional** OpenAI model (`gpt-4o-mini`) that only re-words already-computed pixel numbers into plain-language Evidence Cards, guarded by a number-grounding check and a 100% deterministic built-in fallback. No AI invents numbers.
- **Zero AI commit authorship:** AI tools **never** appear as git authors, co-authors, or repository contributors. Every commit is authored and pushed by a registered human team member from their own GitHub account (Handbook Sections 4 & 5).

---

## Data & Mission Citations

- **NASA–ISRO NISAR L2 GCOV** — NASA Earthdata / ASF DAAC and ISRO Bhoonidhi. Modified Copernicus/NASA/ISRO mission data (2026).
- **OPERA DSWx-S1 / DSWx-NI** — OPERA, JPL / NASA Earthdata.
- **EC JRC / Google Global Surface Water** — Pekel et al. (*Nature*, 2016), European Commission JRC.
- **ESA WorldCover 10 m** — ESA WorldCover Consortium (2021/2024).
- **Nagpur regional context** — GSDA (Govt. of Maharashtra) & CGWB (Nagpur District Aquifer Management Plan). Groundwater is official hydrogeological context, never direct SAR detection.
- **OpenStreetMap** — © OpenStreetMap contributors, via `osmnx`.

## License

MIT
