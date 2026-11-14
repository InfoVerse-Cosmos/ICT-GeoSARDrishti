# Testing on Live NASA / ISRO Data

How we go from the deterministic local-cache demo to **real NISAR L-band data**, what
credentials are needed, and how to verify each live path. Secrets live only in `.env`
files, which are gitignored — **never commit a token** (Handbook Section 5).

---

## The two "live" paths

| Path | What it does | Needs credentials? |
| :-- | :-- | :-- |
| **A. Live catalogue** — `GET /api/v1/nisar/earthdata-live` | Queries NASA CMR for real NISAR granules over a bbox, proves live Earthdata connectivity. Falls back to cache on any failure. | Works **without** a token for public collections; a token raises rate limits and is required for restricted ones. |
| **B. Live processing** — `scripts/01→04` | Downloads real NISAR L2 GCOV granules, runs the SAR pipeline, and writes the `data_store/` packs the API serves. | **Yes** — NASA Earthdata Login. |

The app always *shows* NISAR as the target mission; path B is what actually turns real
granules into the overlays, hydroperiod, GMM regimes, and evidence cards.

---

## 1. Get NASA Earthdata credentials (free)

1. Create an account at **https://urs.earthdata.nasa.gov** (Earthdata Login / URS).
2. Approve the application authorizations when prompted (ASF DAAC, LP DAAC, PO.DAAC as needed).
3. Generate a **bearer token**: Earthdata profile → **Generate Token** → copy it.

That one account covers CMR search, ASF DAAC (NISAR/SAR), and OPERA products.

## 2. Put the token in the backend env (never in git)

```bash
# services/api/.env   (this file is gitignored)
EARTHDATA_TOKEN=eyJ0eXAiOiJKV1Q...your-token...
CORS_ORIGINS=*
# optional LLM narrator; blank = deterministic cards
LLM_API_KEY=
```

Restart the backend (or just re-run `./run.sh`). Confirm it's picked up:
```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
# expect:  "earthdata_token_configured": true
```

## 3. Verify the live catalogue (path A)

```bash
curl -s "http://localhost:8000/api/v1/nisar/earthdata-live?bbox=93.90,26.75,94.30,27.05" | python3 -m json.tool
```
- `"source_mode": "LIVE_API"` + a real `granules` list → live NASA CMR is working.
- `"source_mode": "LOCAL_VERIFIED_CACHE"` + `"fallback_active": true` → network/timeout; the cached list is shown (clearly labelled). This is the graceful fallback, not a bug.

> Tip: NISAR collection short_names change as the mission matures. Pass the correct one, e.g.
> `&short_name=NISAR_L2_GCOV_V1`. Confirm the exact short_name in CMR / ASF Vertex first.

## 4. Pull & process real granules (path B) — the offline pipeline

Run these on a dev machine (Python **3.11** recommended — the geospatial stack fights newer Pythons):

```bash
cd scripts
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# earthaccess authenticates via Earthdata Login. Either:
#   export EARTHDATA_USERNAME=... EARTHDATA_PASSWORD=...
# or let it write ~/.netrc on first run:
python -c "import earthaccess; earthaccess.login(persist=True)"

# 1) lock the same-track GCOV granule list for an AOI
python 01_data_gate_vertex_query.py --aoi aoi_assam_majuli
# 2) subset + classify + hydroperiod  -> overlays + time_series_cube.npz
python 02_subset_and_classify_sar.py --aoi aoi_assam_majuli
# 3) GMM regimes + OPERA DSWx / JRC validation
python 03_gmm_and_validation.py --aoi aoi_assam_majuli
# 4) OSM exposure (roads/villages wet on >=3 dates)
python 04_osm_exposure_extract.py --aoi aoi_assam_majuli
```
These write into `services/api/data_store/aoi_assam_majuli/`. Restart the API and the map now
serves **real** NISAR-derived layers, pixel trajectories, and provenance (granule IDs fill in,
`TBD` disappears).

> The scripts are scaffolds right now — the `# TODO(Phase 2)` blocks are where the real
> earthaccess/rasterio/sklearn calls get implemented during the hackathon.

## 5. ISRO data (Bhoonidhi)

NISAR is a joint NASA–ISRO mission. ISRO distributes NISAR and other EO products via
**Bhoonidhi** (https://bhoonidhi.nrsc.gov.in), which needs its **own** NRSC/Bhoonidhi login
(separate from Earthdata). For the hackathon the **primary** path is NASA Earthdata / ASF DAAC
(one login, well-documented API); treat Bhoonidhi as the ISRO-side cross-check. Keep any
Bhoonidhi credentials in `.env` too, never in git.

---

## Honesty rules when testing live (non-negotiable)

- Read product maturity (`PROVISIONAL` / `VALIDATED`) from the granule metadata verbatim — never set it by hand.
- Keep the **observation (acquisition) date** separate from the processing date.
- Label every result a *radar-derived indication for inspection*, and OPERA numbers as *inter-sensor agreement*.
- If you analyse a stand-in product while NISAR coverage is thin (e.g. Sentinel-1 / OPERA RTC-S1), say so in the UI/provenance — NISAR stays the clearly-labelled target mission, the analysed product is named separately.
- If NISAR coverage for the demo window is unavailable, step down the fallback ladder (SRS §3.3, Plans B–D) rather than faking data.

## Security

- `.env` files are gitignored. Double-check with `git status` before every push.
- If a token ever lands in a commit, revoke it immediately in the Earthdata profile and generate a new one.
