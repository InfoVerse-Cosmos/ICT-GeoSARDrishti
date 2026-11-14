# GeoSAR Drishti — Testing Guide & Roadmap

How to verify **every feature** in the SRS, from raw NISAR `.h5` files to the judge demo.
Each feature has an automated test and a manual check, and the two are linked by ID (F1 … F28).

> **Status on 14 Nov 2026 (dev machine):** 266 automated tests pass (156 backend, 68 pipeline, 42 frontend).
> The full browser walkthrough (§5) passed against a synthetic GCOV pack with 0 console errors.
> The real-data tests (§4) are skipped until someone runs them on the machine that holds the `.h5` files.

---

## 0. Critical data finding (read first)

The 4 downloaded granules (**tracks 063 & 135, frame 076**) were looked up in NASA CMR.
**They do not cover either AOI:**

| Granules | Footprint (CMR) | Majuli 26.75–27.05°N 93.9–94.3°E | Nagpur 21.15–21.45°N 78.95–79.35°E |
|---|---|---|---|
| 063 / D / 076 | 23.5–26.2°N, 69.0–72.0°E (Kutch / W. Rajasthan) | ❌ | ❌ |
| 135 / D / 076 | 23.6–26.2°N, 71.1–74.1°E (Gujarat / S. Rajasthan) | ❌ | ❌ |

**These are the tracks that do cover the AOIs** (CMR search, Jun–Nov 2026, dual-pol `DHDH`):

| AOI | Track / frame | Dates | Plan |
|---|---|---|---|
| `aoi_assam_majuli` | **040 / A / 015** | 16 Jun, 28 Jun, 10 Jul, **22 Jul**, 15 Aug, 27 Aug, 8 Sep, 20 Sep, 2 Oct, 14 Oct, 26 Oct, 7 Nov (12) | **A**. Covers the 18–21 Jul flood. The 22 Jul → 15 Aug jump is exactly the SRS sensor gap |
| `aoi_nagpur_kanhan` | **156 / A / 012** | 25 Jun … 4 Nov (11) | **A** |

The fastest fix is to let the data gate download the right stack:
```bash
python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli --search --download D:/nisar/majuli
```
Script 01 also refuses granules whose footprint misses the AOI (`--h5-dir` mode), so a wrong
download is caught automatically.

CMR collections: `NISAR_L2_GCOV_PROVISIONAL_V1` (PROVISIONAL) and `NISAR_L2_GCOV_V1` (VALIDATED).
Both are queried by default, and maturity is taken from the collection.

---

## 1. One-time setup

```bash
# Backend (Python 3.11+; 3.14 also works with unpinned versions)
cd services/api
python -m venv .venv && .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt                    # version ranges -> wheels exist for Python 3.11 … 3.14

# Pipeline (the heavy geo stack — dev machines only)
cd ../../scripts
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt

# Frontend
cd .. && npm install
```

Earthdata login (stage 01 `--search` only): set `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` or create `~/.netrc`.

---

## 2. Roadmap: the order to test things in

```
Step 1  Automated suites (no data)          ~1 min   §3  -> must be all green before anything else
Step 2  Synthetic end-to-end pipeline       ~2 min   §4.1 -> proves 01→05 work on GCOV-format HDF5
Step 3  Real data: data gate                ~5 min   §4.2 -> lock the right same-track stack
Step 4  Real data: content checks           ~5 min   §4.3 -> HH/HV present, footprint, calibration
Step 5  Real data: full pipeline 01→05      ~10 min  §4.4 -> produces the committed data pack
Step 6  Browser walkthrough (demo script)   ~10 min  §5  -> every UI feature, incl. offline
Step 7  Deploy smoke test                   ~5 min   §6
```

---

## 3. Automated suites (Step 1)

| Suite | Command (from repo root) | Expect |
|---|---|---|
| Backend API | `cd services/api && python -m pytest tests -q` | 156 passed, 1 skipped (live NASA, opt-in) |
| Pipeline (unit + synthetic E2E) | `scripts/.venv/Scripts/python -m pytest scripts/tests -q` | 68 passed, 21 skipped (real-data, §4) |
| Frontend | `npm --workspace apps/web test` | 42 passed |
| Build | `npm --workspace apps/web run build` | `✓ built` |
| Live NASA CMR (opt-in) | `cd services/api && RUN_NETWORK_TESTS=1 python -m pytest tests -k real_nasa` | 1 passed |

---

## 4. Testing with the real NISAR data

### 4.1 Synthetic end-to-end (Step 2, no real data needed)
`scripts/make_synthetic_gcov.py` writes GCOV-format HDF5 files (the same
`/science/LSAR/GCOV/grids/frequencyA/HHHH|HVHV`, projection and identification layout) under the
team's real file names, plus optional WorldCover / JRC / DSWx GeoTIFFs. Every file is stamped
`GEOSAR_SYNTHETIC_TEST_DATA`, and the pipeline carries that flag through to a red **SYNTHETIC TEST DATA**
badge in the UI, so synthetic output can never be mistaken for real data.

```bash
export GEOSAR_DATA_STORE=scripts/_work/synthetic_store       # never touches the committed data_store
mkdir -p $GEOSAR_DATA_STORE && cp -r services/api/data_store/aoi_* $GEOSAR_DATA_STORE/
python scripts/make_synthetic_gcov.py --out scripts/_work/synthetic_h5 --ancillary
python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli --h5-dir scripts/_work/synthetic_h5
python scripts/02_subset_and_classify_sar.py --aoi aoi_assam_majuli --h5-dir scripts/_work/synthetic_h5 --worldcover scripts/_work/synthetic_h5/worldcover.tif
python scripts/03_gmm_and_validation.py --aoi aoi_assam_majuli --jrc scripts/_work/synthetic_h5/jrc_occurrence.tif --dswx scripts/_work/synthetic_h5/dswx_wtr.tif --dswx-date 2026-10-09
python scripts/04_osm_exposure_extract.py --aoi aoi_assam_majuli        # live OSM (needs internet)
# serve it:
cd services/api && GEOSAR_DATA_STORE=../../scripts/_work/synthetic_store uvicorn app.main:app --port 8000
```
Results on 14 Nov: wet date 177.7 km² open water and 77.3 km² flooded vegetation (46.1 natural + 31.2 paddy);
dry reference 0 km² flooded vegetation; calibration offset 0.00 dB; DSWx agreement 98.8 %; JRC unusual open water 26.9 %;
OSM returned 5,062 features, of which 126 are inspection candidates.

### 4.2 Data gate on the real files (Step 3)
```bash
python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli --h5-dir D:/nisar --dry-run
```
| Check | Pass condition |
|---|---|
| Footprint | No `skipped: footprint does not intersect AOI` (if every file is skipped, see §0) |
| Same-track | `selected_track_frame` is a single track/frame |
| Plan | `A` with ≥ 6 dual-pol dates, `C` with 2–5, `D` with fewer than 2 |
| Maturity | Dates before 23 Oct PROVISIONAL, after VALIDATED |

Then drop `--dry-run` to lock the manifest. (With only the file names: `--names-file names.txt`.)

### 4.3 Content checks on the real `.h5` (Step 4)
```bash
NISAR_H5_DIR=D:/nisar GEOSAR_GRANULE_AOI=aoi_assam_majuli python -m pytest scripts/tests/test_nisar_granules.py -v
GEOSAR_CHECK_LOCKED_MANIFEST=1 python -m pytest scripts/tests/test_nisar_granules.py -v   # after step 3
```
These check: the `HHHH` + `HVHV` datasets exist; track, frame and start time match the file name; the footprint covers the AOI;
median γ⁰ is plausible (−35…+5 dB) with HH > HV; same-track grids are identical; the PROVISIONAL→VALIDATED HV offset is under 1 dB.
*`test_nisar_granules.py` lists the 4 current file names in `GRANULES`. Edit that list when you download the correct stack.*

### 4.4 Full real pipeline (Step 5)
Same commands as §4.1 without `GEOSAR_DATA_STORE` (writes `services/api/data_store/`), using real
ancillary data: ESA WorldCover 10 m tile, JRC GSW occurrence tile, OPERA DSWx-S1 `WTR` tile, and an optional Copernicus DEM (`--dem`).
Finish with `python scripts/05_build_offline_mirror.py` so the offline mirror contains the real timeline.
Keep `data_store/` under 35 MB (SRS §8.1); a 30 km AOI at 100 m with 12 dates is about 3 MB.

---

## 5. Feature checklist (Step 6). Automated test ↔ manual browser check

Start `uvicorn` (`:8000`) and `npm run web:dev` (`:5173`) and open http://localhost:5173.

| ID | Feature (SRS) | Automated test | Manual check in the browser | ✓ 14 Nov |
|---|---|---|---|---|
| F1 | Standard JSON envelope (§7.2) | `test_every_json_endpoint_returns_standard_envelope` | — | ✅ |
| F2 | Health + data-pack status (§7.1) | `test_health_reports_packs_and_config`, e2e `test_backend_serves_the_generated_pack` | `GET /api/v1/health` → `data_packs` shows cube/overlays | ✅ |
| F3 | Dual-AOI selector (§3.1) | `test_aoi_directory_lists_both_presets`, UI `changing the selector…` | Switch Assam ↔ Nagpur: map refits, layers filter (Nagpur: Open Water / Hydroperiod / Regional Context) | ✅ |
| F4 | Same-track data gate + Plan A–D (§3.2–3.3) | `test_data_gate_*`, `test_dataset_supports_only_fallback_plan_c` | Top bar shows `PLAN x` and `T/F ttt/fff` | ✅ |
| F5 | Footprint check (wrong-area files rejected) | `test_data_gate_drops_granules_outside_the_aoi` | §4.2 output | ✅ |
| F6 | dB math rule, floor clip (§2, §5.1) | `test_ratio_is_subtraction_in_db_space`, `test_to_db_*` | — | ✅ |
| F7 | 3-class classifier, ΔHH ≥ 3 dB and ΔRatio ≥ 1.5 dB vs the reference HV (§5.2) | `test_double_bounce_*`, `test_delta_ratio_uses_reference_hv` | Flooded Vegetation layer on a wet date | ✅ |
| F8 | Single-Pol HH mode (§3.2) | `test_single_pol_mode`, `test_single_pol_mode_uses_hh_only` | Top bar `SINGLE-POL HH`; card notes the ratio test was skipped | ✅ |
| F9 | Paddy vs natural sub-label (WorldCover) | `test_paddy_sub_label_from_worldcover` | Flooded Vegetation: green natural vs amber paddy; Scene tab shows both areas | ✅ |
| F10 | Hydroperiod M of N (§5.3) | `test_inspect_hydroperiod_is_m_of_n`, `test_cube_and_overlays_written` | Hydroperiod layer + "wet m/n obs" on the chart | ✅ |
| F11 | Dynamic Otsu in [−22, −13] dB | `test_otsu_thresholds_within_srs_range` | Provenance → Otsu thresholds | ✅ |
| F12 | PROVISIONAL / VALIDATED badges + calibration check (§3.2) | `test_timeline_maturity_*`, `test_calibration_check_recorded`, `test_maturity_read_from_cmr_collection` | Tick colours (orange / cyan); Provenance → calibration offset | ✅ |
| F13 | 27 Jul – 10 Aug gap band (§3.2) | `test_timeline_has_no_acquisitions_inside_sensor_gap`, UI gap tests | Hatched band on the season ruler + label | ✅ |
| F14 | Animated time slider (§4.2.3) | UI `PLAY advances…` | ▶ PLAY cycles dates and the granule pill changes | ✅ |
| F15 | Overlays per date + season layers fallback (§7.1) | `test_existing_dated_overlay…`, e2e season fallback | Switch dates and layers; no broken images | ✅ |
| F16 | Placeholder PNG valid / no traversal | `test_placeholder_png_is_a_valid_decodable_image`, `test_date_param_cannot_escape_overlay_directory` | Console shows no "could not be decoded" errors | ✅ |
| F17 | Before / after compare (§4.2.2) | — (visual) | Map panel: "Before / after" → pick a date, drag the fader | ✅ |
| F18 | GMM regimes k=5 (§5.4) | `test_gmm_*`, `test_gmm_regimes_are_hydrologically_sensible` | GMM layer + legend; Scene tab regime areas | ✅ |
| F19 | JRC "unusual" open water (§5.5) | `test_jrc_and_dswx_validation` | JRC Anomaly layer red/blue; Scene tab km² and % | ✅ |
| F20 | OPERA DSWx inter-sensor agreement (§5.5) | `test_jrc_and_dswx_validation`, `test_dswx_agreement*` | Scene tab "inter-sensor agreement, not ground-truth accuracy" | ✅ |
| F21 | Pixel click → trajectory (§4.2 Tab 2) | `test_inspect_returns_full_trajectory…` | Click inside AOI → HH / HV / HH−HV chart, Otsu & dry-ref lines, per-date class chips | ✅ |
| F22 | Outside-AOI click (§7.2 rule 1) | `test_click_outside_aoi_returns_friendly_status` | Click outside the cyan box → exact SRS message | ✅ |
| F23 | Radar Evidence Card (§7.3) | `test_card_reproduces_srs_example`, `test_inspect_output_feeds_evidence_card…` | Card shows ΔHH, baseline→peak dB, ΔRatio, regime, M/N, WorldCover, JRC, confidence, verbatim caveat | ✅ |
| F24 | LLM narrator, 3 s timeout + fallback (§7.2 rule 2) | `test_llm_narrator_*` | Set `LLM_API_*`; with a bad key the card stays `mode: deterministic` | ✅ (mocked) |
| F25 | OSM inspection candidates M ≥ 3 (§5.5) | `test_exposure_from_local_osm_file`, `test_exposure_ranks…` | Inspection Log: sortable, filter by kind, row click flies the map; red lines on the map | ✅ |
| F26 | Live NASA CMR + verified fallback (§6.1, §7.1) | `test_any_failure_falls_back…`, `test_real_nasa_cmr_reachable` | Provenance → "Query NASA CMR now" → `LIVE_API`, real granules | ✅ (live: 20 real granules) |
| F27 | Offline mirror + uplink banner + auto-recovery (§7.2 rule 3) | client `aborts a hung request…`, `test_offline_mirror` | Stop the backend and reload → banner "ESTABLISHING TELEMETRY UPLINK…", `OFFLINE MIRROR`, ticks still clickable; restart the backend → recovers with no reload | ✅ |
| F28 | Honest language / pitch guide (§10) | `test_card_never_uses_forbidden_pitch_language`, `test_provenance_limitations_use_honest_language` | No "accuracy", "damage" or "stranded" claims anywhere | ✅ |
| F29 | Nagpur regional context (§3.1) | `/aois/{id}/context` envelope tests | Regional Context layer; needs `data_store/aoi_nagpur_kanhan/context_layers.geojson` (GSDA/CGWB export) | ⚠️ endpoint ready, data needed |

### Demo click-path (≈ 3 min, for judges)
1. Load the app: point out the LIVE API, PLAN, maturity and track/frame badges.
2. **▶ PLAY** through the season, then stop on the peak date. Point out the gap band.
3. Switch to Flooded Vegetation (green vs amber paddy), then Before/after against the dry reference.
4. Click a green pixel to show the trajectory and the Evidence Card. Read the ΔHH sentence aloud.
5. Hydroperiod, then GMM regimes.
6. Inspection Log: click the top row to fly to the road segment.
7. Provenance: Query NASA CMR now (live), then scroll through the limitations.
8. Switch to Kanhan–Pench [Nagpur].

---

## 6. Deploy smoke test (Step 7)
```bash
curl -s https://<api>/api/v1/health | jq '.data.data_packs'
curl -s "https://<api>/api/v1/aois/aoi_assam_majuli/inspect?lat=26.9&lon=94.1" | jq '.status'
curl -sI "https://<api>/api/v1/layers/aoi_assam_majuli/open_water.png" | grep -i x-geosar
```
Open the frontend URL and repeat F3, F14, F21–F23 and F27.

---

## 7. Known limitations / open items
- **Wrong area downloaded** (§0): the 4 files are Gujarat/Rajasthan. Download track 040/015 (Majuli) and track 156/012 (Nagpur).
- **Nagpur context layers**: the endpoint and UI are ready; someone needs to export the GSDA/CGWB layers to `context_layers.geojson`.
- **DEM slope mask** is optional (`--dem`). Without it, hill shadows could be misclassified as water (Majuli is flat, so the risk is low).
- **GCOV `mask` layer**: only the fill value 255 is used. Layover/shadow bit decoding should be confirmed against the NISAR product spec.
- **GMM labels** come from documented rules over the cluster means (`provenance.gmm.mapping_rule`). With only 2 dates, "Beel" can merge into "Permanent River".
- `fastapi.on_event` deprecation warning: harmless.
