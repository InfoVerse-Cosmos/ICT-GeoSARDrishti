# GeoSAR Drishti — Implementation Plan & Phase Roadmap

**Repository:** `InfoVerse-Cosmos/ICT-GeoSARDrishti`
**Source of truth:** [`Docs/geosar_intelligence_srs_and_implementation_blueprint.md`](./geosar_intelligence_srs_and_implementation_blueprint.md) (SRS v4.0)
**Team:** Cosmos InfoVerse Techky (6 members)
**Event:** NASA Space Apps Challenge 2026 — CH-06 *Dancing with the SARs* (WCEM, Nagpur, 14–15 Nov 2026)
**Plan status:** Authored before first code push. This document maps the SRS into an executable, phase-by-phase build plan with owners, deliverables, and acceptance criteria.

---

## 0. How this plan aligns with the SRS

This plan is a direct execution layer over the SRS. Nothing here overrides the SRS; it sequences it.

| SRS section | Drives | Plan phase |
| :-- | :-- | :-- |
| §2 Physics baseline (L-band, dB math) | Classifier + dB rules | Phase 2 |
| §3 Dual-AOI + 4-step fallback ladder | AOI packs, graceful degradation | Phases 1–3 |
| §4 Telemetry UI design system | Frontend theme + layout | Phases 1–3 |
| §5 Scientific pipeline (Otsu, Δdb, hydroperiod, GMM, validation) | Offline scripts + data store | Phase 2 |
| §6 Client–server architecture + monorepo layout | Repo scaffold (this push) | Phase 0–1 |
| §7 REST API blueprint + response envelope | FastAPI routers + fallbacks | Phases 1–2 |
| §8 Cloud deployment | Render/Vercel deploy | Phase 3 |
| §9 48-hour execution plan | Overall schedule | All phases |
| §10 Judge pitch guidance | Framing + copy | Phase 4 |
| §11 Citations + AI disclosure | README | Phase 4 |

**Non-negotiable framing rules carried from the SRS (§2, §7, §10):**
- Results are a *radar-derived surface/canopy-water indication for inspection*, never a confirmed flood or damage claim.
- OPERA agreement is *inter-sensor agreement %*, never "ground-truth accuracy".
- Hydroperiod is always "wet in **M of N** valid NISAR observations", never "days flooded".
- The **27 Jul – 10 Aug 2026 acquisition gap** is shown explicitly, never interpolated over.
- Every date carries a `PROVISIONAL` / `VALIDATED` maturity badge read from provider metadata, never fabricated.
- Fallback/placeholder data is labelled as such and never masquerades as NISAR.

---

## 1. First-Push Repository Layout

This is the structure created in the initial scaffold (SRS §6.2, de-spaced for a clean repo root). The workspace root **is** the repo root.

```text
ICT-GeoSARDrishti/
├── apps/
│   └── web/                         # Vite + React 18 (JS/JSX) + MapLibre GL JS + Tailwind
│       ├── public/fallback_data/    # Static manifest mirror for full-offline resilience
│       └── src/
│           ├── api/client.js        # Fetch wrapper: timeout, retry, envelope-safe
│           ├── components/          # TopTelemetryBar, MapWorkspace, MonsoonTimeSlider,
│           │                        #   PixelTrajectoryChart, EvidenceCardPanel,
│           │                        #   ExposureTable, ProvenanceModal
│           ├── store/useMissionStore.js   # Zustand: AOI, date, layer, clicked pixel
│           ├── App.jsx / main.jsx / index.css
│           └── (vite.config.js, jsconfig.json, tailwind/postcss config, package.json)
├── services/
│   └── api/                         # FastAPI (Python 3.11) + Uvicorn + Rasterio + NumPy
│       ├── app/
│       │   ├── main.py              # App, CORS, global exception handlers, envelope
│       │   ├── config.py            # Env: EARTHDATA_TOKEN, LLM_API_KEY, CORS_ORIGINS
│       │   ├── routers/             # aois, nisar, layers, inspect, exposure
│       │   └── services/            # earthdata_client, raster_sampler, evidence_narrator
│       ├── data_store/              # Committed lightweight AOI packs (< 35 MB target)
│       │   ├── aoi_assam_majuli/    # manifest.json, overlays/, time_series_cube.npz, osm_exposure.geojson
│       │   └── aoi_nagpur_kanhan/   # manifest.json, overlays/, time_series_cube.npz, context_layers.geojson
│       ├── requirements.txt
│       └── Dockerfile
├── scripts/                         # Offline data gate & processing (run on dev machines)
│   ├── 01_data_gate_vertex_query.py
│   ├── 02_subset_and_classify_sar.py
│   ├── 03_gmm_and_validation.py
│   ├── 04_osm_exposure_extract.py
│   └── requirements.txt
├── Docs/                            # SRS + this plan
├── .env.example
├── .gitignore
├── package.json                     # Root workspace scripts
└── README.md                        # Live URLs, citations, AI disclosure
```

**What the first push contains:** runnable skeletons — the FastAPI server boots and serves the full envelope contract from seed `manifest.json` files with fallbacks active; the React app renders the telemetry shell against the API. Real NISAR-derived data packs land in Phase 2.

---

## 2. Module Ownership (SRS roster → code areas)

| Owner | GitHub | Primary code area |
| :-- | :-- | :-- |
| Pravin Tawade | `@cosmosinfoverse` | Architecture, SAR physics thresholds, mission framing, review |
| kaushik zade | `@kaushik7` | `services/api` server, `earthaccess` connector, offline raster processing |
| Sharv Dalal | `@shardstax` | `apps/web` telemetry UI, MapLibre, time slider, Zustand store |
| Himanshu Sharma | `@lunar_node` | NISAR data gate, maturity/calibration, OPERA DSWx / JRC validation |
| Sakshi Manav Tayade | `@sakshitayade` | GMM regimes, ESA WorldCover, OSM exposure, Nagpur context |
| Prashan Arya | `@prashan_arya` | Evidence Card templates, error/fallback QA, hourly Git compliance |

---

## 3. Phase-by-Phase Plan

Each phase lists **objective → key tasks (owner) → deliverables → acceptance criteria → dependencies**.

### Phase 0 — Repo Bootstrap & Compliance (14 Nov, ~12:00–12:45 PM)

**Objective:** Fresh public repo + scaffold + compliance guardrails in place before feature work.

**Key tasks**
- Create fresh public repo `ICT-GeoSARDrishti` **after 12:00 PM, 14 Nov** (handbook rule).
- Land the first-push scaffold (this layout), `.gitignore`, `.env.example`, root `README.md` skeleton.
- Each of the 6 members verifies `git config user.name` / `user.email` matches their personal GitHub and pushes one genuine commit.
- Confirm no AI author/co-author trailers in any commit.

**Deliverables:** Scaffold on `main`; 6 human contributors visible; hourly-commit tracker (Prashan) running.

**Acceptance:** `services/api` boots locally (`uvicorn`), `apps/web` dev server renders shell, `git log` shows only human authors.

**Dependencies:** None (entry point).

> **Compliance note:** Kiro scaffolds files only. Git `init`/`add`/`commit`/`push` are performed by the human team members from their own accounts — no automated commits, no AI co-author tags.

---

### Phase 1 — Data Gate & Core Scaffold (14 Nov, 12:45 PM – 4:00 PM)
*SRS §9 Phase 1*

**Objective:** Lock the NISAR granule list, stand up server + client skeletons talking to each other, and pull auxiliary layers.

**Key tasks**
- **Himanshu + Pravin:** Run `scripts/01_data_gate_vertex_query.py` against ASF Vertex / NASA CMR for `aoi_assam_majuli` and `aoi_nagpur_kanhan`. Lock same-track L2 `GCOV` granule IDs; record track/frame, polarization (HH / HH+HV), and maturity per date. Decide active fallback plan (A/B/C/D).
- **Kaushik:** FastAPI skeleton live — `/health`, `/aois`, `/aois/{id}/timeline`, CORS, response envelope, global exception handler. Deploy staging service early (Render/Railway).
- **Sharv:** Vite + React JS + Tailwind + MapLibre shell with NASA–ISRO dark telemetry theme, Top Mission Bar, Dual-AOI switcher, empty map viewport + time-slider dock.
- **Sakshi:** Download ESA WorldCover 10 m, JRC Water Occurrence, OSM roads/villages (`osmnx`) clipped to both 30×30 km AOI boxes.
- **Prashan:** Deterministic Evidence Card templates + error-handling wrappers + hourly push tracker.

**Deliverables:** Granule manifest (seed), booting staging API, rendering UI shell, auxiliary layer rasters/vectors staged locally.

**Acceptance:** Frontend fetches `/aois` and `/timeline` from staging API and renders AOI selector + acquisition ticks (with the 27 Jul–10 Aug gap band) using real locked dates; envelope `status`/`source_mode`/`fallback_active` present on every response.

**Dependencies:** Phase 0.

---

### Phase 2 — SAR Physics Pipeline & Client–Server Wiring (14 Nov, 4:00 PM – 11:00 PM)
*SRS §9 Phase 2, §5 pipeline, §2 physics*

**Objective:** Generate real NISAR-derived data packs and wire every thematic layer and interaction end to end.

**Key tasks**
- **Kaushik + Himanshu:** Run `scripts/02_subset_and_classify_sar.py`:
  - Stream + subset `γ⁰_HH`, `γ⁰_HV` to AOI box; apply validity/layover-shadow + DEM slope (>5°) masks.
  - 3×3 median/Lee speckle filter on linear power; floor clip 1e-5; convert to dB.
  - **dB rule enforced in code:** `Ratio_dB = HH_dB − HV_dB` (never divide negative dB).
  - Per-date 3-class classifier: Open Water (dynamic Otsu HH in [−22,−13] dB + HV threshold), Possible Flooded Vegetation (`ΔHH ≥ +3.0 dB` AND `ΔRatio ≥ +1.5 dB`, inside veg/crop mask), Dry.
  - WorldCover sub-labels: cropland → "Paddy-Like", wetland/forest/grass → "Natural Flooded Vegetation".
  - Hydroperiod `M/N` raster (counts + %). Emit RGBA PNG overlays + `time_series_cube.npz`.
  - Auto Single-Pol HH mode when HV absent; update polarization badge.
- **Sakshi:** Run `scripts/03_gmm_and_validation.py` (sklearn `GaussianMixture` k=5 on temporal feature vector → 5 named regimes; OPERA DSWx-S1/NI inter-sensor agreement %; JRC occurrence context, flag <20% as "Unusual") and `scripts/04_osm_exposure_extract.py` (roads/villages wet on M≥3 dates → `osm_exposure.geojson`).
- **Sharv + Prashan:** Wire `client.js` to `/layers/{aoi}/{layer}.png`, `/inspect`, `/evidence-card`, `/exposure`, `/provenance`. Build layer toggles, before/after split swipe, Recharts HH/HV dB trajectory, Evidence Card panel, Exposure table (fly-to).

**Deliverables:** Populated `data_store/` packs for both AOIs; all five routers serving real data with fallbacks; interactive map with all layers + pixel-click evidence.

**Acceptance:**
- Clicking a pixel returns its HH/HV dB trajectory, hydroperiod M/N, GMM regime, JRC %, WorldCover class, and a deterministic Evidence Card.
- Out-of-AOI click returns `status:"outside_aoi"` (no 500).
- Overlays align geographically in MapLibre; maturity badge reflects per-date metadata.
- Data pack total stays lightweight (quantized PNG + float16 npz; < 35 MB target).

**Dependencies:** Phase 1 (locked granules, booting API, UI shell, aux layers).

---

### Phase 3 — Overnight Polish, Nagpur Context & Cloud Deploy (14 Nov 11:00 PM – 15 Nov 9:00 AM)
*SRS §9 Phase 3, §8 deployment*

**Objective:** Second AOI fully integrated, deployed to custom domain, resilient offline behaviour proven.

**Key tasks**
- Integrate `aoi_nagpur_kanhan` with GSDA/CGWB watershed + hydrogeology context (labelled official context, never SAR detection).
- Deploy FastAPI backend (Render/Railway/Cloud Run) with `EARTHDATA_TOKEN`, `CORS_ORIGINS`, optional `LLM_API_KEY`; start cmd `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- Deploy `apps/web` (Vercel/Netlify, root `apps/web`, output `dist`, `VITE_API_BASE_URL` set) to a custom subdomain.
- Verify live `/api/v1/nisar/earthdata-live` with 4s timeout → cached fallback (`source_mode: LOCAL_VERIFIED_CACHE`).
- Prove full-offline: kill network, confirm `public/fallback_data/manifest.json` keeps map + slider interactive; cold-start "ESTABLISHING TELEMETRY UPLINK…" banner + retry works.
- Maintain genuine hourly human commits across all 6 members.

**Deliverables:** Both AOIs live on public URLs; offline + cold-start resilience demonstrated.

**Acceptance:** Live frontend talks to live backend over HTTPS+CORS; pulling the plug degrades gracefully with explicit labels; both AOIs switch cleanly.

**Dependencies:** Phase 2.

---

### Phase 4 — Verification, Pitch Rehearsal & Code Freeze (15 Nov 9:00 AM – 2:00 PM)
*SRS §9 Phase 4, §10 pitch, §11 citations/disclosure*

**Objective:** Submission-ready repo, defensible pitch, clean compliance — frozen before 2:00 PM IST.

**Key tasks**
- Complete `README.md`: live domain URL at top, architecture diagram, mandatory NASA/ISRO/OPERA/JRC/ESA/GSDA-CGWB/OSM citations (§11), and the AI Usage Disclosure block verbatim-compliant.
- Fill `/provenance` per AOI: exact granule IDs/DOIs, Otsu thresholds, ΔHH params, DSWx agreement %, explicit limitations.
- QA pass on honest-framing copy (§10 "Say this / Never say this").
- Verify all 6 members in GitHub → Insights → Contributors; `git log` free of AI bot/co-author tags.
- Rehearse pitch against the Evidence Card example (§7.3).
- **Hard code freeze before 2:00 PM IST, 15 Nov 2026.**

**Deliverables:** Final README, provenance manifests, rehearsed pitch, compliance sign-off.

**Acceptance:** Submission checklist (below) fully green at freeze.

**Dependencies:** Phase 3.

---

## 4. API Contract (envelope + endpoints, from SRS §7)

Every response uses the envelope:
```json
{ "status": "ok", "aoi_id": "aoi_assam_majuli", "source_mode": "LOCAL_VERIFIED_CACHE",
  "fallback_active": false, "warning": null, "data": { } }
```

| Method | Endpoint | Fallback |
| :-- | :-- | :-- |
| GET | `/api/v1/health` | always 200 |
| GET | `/api/v1/aois` | static default dict |
| GET | `/api/v1/aois/{aoi_id}/timeline` | cached baseline timeline |
| GET | `/api/v1/nisar/earthdata-live` | cached CMR response, `source_mode: LOCAL_VERIFIED_CACHE` |
| GET | `/api/v1/layers/{aoi_id}/{layer_id}.png` | transparent placeholder PNG + warning |
| GET | `/api/v1/aois/{aoi_id}/inspect?lat&lon` | `outside_aoi` / `nodata` card |
| POST | `/api/v1/evidence-card` | deterministic physics template |
| GET | `/api/v1/aois/{aoi_id}/exposure` | empty FeatureCollection + status |
| GET | `/api/v1/aois/{aoi_id}/provenance` | always available |

Hard rules in code: coordinate bounds check before array index (no 500); `httpx.Timeout(3.5)` on all external calls with caught fallback; frontend never reads `undefined` (envelope guaranteed).

---

## 5. 4-Step Fallback Ladder (SRS §3.3) — pick the highest viable, never change the app

- **Plan A:** Full multi-pol season (HH+HV, 3 classes, GMM, DSWx agreement, OSM exposure).
- **Plan B:** HV missing/noisy → Open-Water Hydroperiod M/N + ΔHH anomaly + JRC context + OSM exposure.
- **Plan C:** Only 2–3 compatible dates → Pre/Peak/Post-monsoon change triad with validation.
- **Plan D:** Assam frame coverage issue → swap primary AOI (Kosi/Kolleru or ASF supplemental frames) + keep Nagpur.

The chosen plan is recorded in each AOI `manifest.json` and surfaced in `/provenance`.

---

## 6. Submission Compliance Checklist (freeze gate)

- [ ] Repo created fresh after 12:00 PM, 14 Nov 2026.
- [ ] All 6 members committed hourly from personal accounts; visible in Contributors.
- [ ] No AI tool appears as Git author/co-author anywhere in history.
- [ ] Live frontend URL at top of README; backend reachable over HTTPS+CORS.
- [ ] Mandatory data citations present (NASA/ISRO/OPERA/JRC/ESA/GSDA-CGWB/OSM).
- [ ] AI Usage Disclosure block present (handbook-compliant).
- [ ] Maturity badges driven by real metadata; 27 Jul–10 Aug gap shown.
- [ ] All results framed as inspection indications; agreement labelled inter-sensor.
- [ ] Fallbacks verified: offline map, cold-start banner, external-timeout degradation.
- [ ] Hard code freeze committed before 2:00 PM IST, 15 Nov 2026.

---

## 7. Risk Register (top risks → mitigation)

| Risk | Mitigation |
| :-- | :-- |
| L2 GCOV granules 1–5 GB time out live | Offline subset to COG/PNG/npz committed in `data_store/` |
| HV channel missing on track | Auto Single-Pol HH mode + badge |
| Free-tier backend cold start during demo | Uplink banner + retry + static fallback manifest |
| Venue Wi-Fi drops | `public/fallback_data/` keeps UI interactive |
| PROVISIONAL↔VALIDATED calibration jump | Check overlap in 21–23 Oct window; show maturity badge |
| Overclaiming in pitch | §10 framing table enforced in QA |
| Missed hourly commit rule | Prashan's tracker + per-member task slices |

---

*End of plan. Build order: Phase 0 → 4. This document is reviewed with the SRS at each phase boundary.*
