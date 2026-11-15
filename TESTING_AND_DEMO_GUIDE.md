# GeoSAR Drishti — Testing & Demo Guide

**One line:** an interactive NASA–ISRO **NISAR L-band (24 cm)** radar time-series console that shows, across a monsoon season, where water is **open**, where it is **hidden under vegetation**, **how long** it stayed, and **what changed** — with every number traceable and honestly framed.

> **Honest-framing rule (non-negotiable).** Every output is a *radar-derived surface/canopy-water indication for field inspection* — **not** a confirmed flood, depth, or damage claim. Agreement with OPERA/MODIS is *inter-sensor agreement*, never ground-truth accuracy. Hydroperiod is *"M of N valid NISAR observations,"* never "days flooded."

---

## 1. Run it (2 ways)

**A. You already have a pack (fast demo):**
```bash
./run.sh            # macOS/Linux   (run.bat on Windows)
```
→ FastAPI on `http://localhost:8000`, Vite UI on `http://localhost:5173`. Open the UI.

**B. Bring your own data (the open-source path):**
```bash
# 1. drop NISAR L2 GCOV .h5 granules into  DATA/
# 2.
./analyze.sh        # auto-detects the area, builds the pack, starts the app
```
`analyze.sh` creates the processing venv, guards against truncated downloads, builds the pack, then launches both tiers. Multi-frame mosaic:
```bash
python scripts/byod_build_aoi.py --mosaic --aoi-id aoi_gandak --name "Gandak River [Bihar]" \
    --h5-dir DATA --h5-dir DATA/gandak_frames_074_076
```

**Data note.** Nothing is shipped or simulated — the backend lists only AOIs you have real data for. To remove an AOI, delete its folder under `services/api/data_store/` (re-scanned without a restart). The pack's identity is the `aoi_id` inside its `manifest.json`, not the folder name.

---

## 2. The science & the parameters (say these, they're correct)

| Concept | Parameter / rule |
| :-- | :-- |
| Sensor | NASA–ISRO **NISAR**, **L-band λ ≈ 24 cm (1.25 GHz)**, L2 **GCOV** γ⁰ backscatter |
| Why L-band | 24 cm microwaves **penetrate canopy** (vs Sentinel-1 C-band ≈ 5.6 cm, which scatters off the top leaves) — lets us see water *under* vegetation |
| Polarisation | Dual-pol **HH + HV** (quad-pol granules used for their HH/HV); single-pol HH mode auto-engaged if HV absent |
| dB rule | `Ratio_dB = HH_dB − HV_dB` (subtraction — **never** divide negative dB) |
| **Open water** | Specular/dark: `HH_dB < τ_Otsu` (dynamic per scene within **[−22, −13] dB**) **and** `HV_dB < τ_HV` |
| **Flooded vegetation** (canopy-hidden) | Dihedral double-bounce: `ΔHH ≥ +3.0 dB` **and** `ΔRatio ≥ +1.5 dB` vs a dry post-monsoon reference, inside the vegetation mask |
| Speckle / prep | 3×3 median/Lee filter on **linear** power, floor-clip 1e-5, DEM slope **> 5° masked** |
| **Hydroperiod** | **M of N** valid observations wet (raw counts + %), per pixel |
| GMM regimes | Unsupervised `sklearn` Gaussian Mixture (k=5) on each pixel's temporal feature vector → 5 named hydrological regimes |
| Multi-frame **mosaic** | Composite adjacent along-track frames (e.g. 074/075/076) per date onto one AOI grid (linear-power NaN-aware union) for full spatial coverage |
| Maturity | **PROVISIONAL** (amber) vs **VALIDATED** (cyan) badge per date; validated from ~21–23 Oct 2026 |
| Acquisition gap | Real **27 Jul – 10 Aug 2026** NISAR gap shown explicitly as a hatched band |
| Validation | **OPERA DSWx-S1** inter-sensor agreement % (Sentinel-1-derived); **JRC** occurrence < 20 % flags *unusual* open water. Both optional; shown "not loaded" when no aux GeoTIFF supplied — never faked |
| Exposure | OSM roads/settlements wet on **M ≥ 3** observations → "ground-inspection candidates" (never a damage claim) |

---

## 3. Testing checklist

**Backend (`http://localhost:8000`):**
- `GET /api/v1/health` → `200`, lists `aoi_packs` actually on disk.
- `GET /api/v1/aois` → your AOIs with WGS84 bounds.
- `GET /api/v1/aois/{id}/timeline` → acquisition dates, track/frame, polarization, maturity, gaps.
- `GET /api/v1/layers/{id}/{layer}.png?date=YYYY-MM-DD` → real overlay with header `X-GeoSAR-Fallback: false` (transparent 1×1 placeholder if missing — never a 404).
- `GET /api/v1/aois/{id}/inspect?lat=&lon=` inside the footprint → `status: ok`, full HH/HV dB trajectory + hydroperiod. Outside → friendly `outside_aoi` / `nodata`, never a 500.
- `GET /api/v1/aois/{id}/report` → aggregate numbers (hydroperiod, class areas, before/after change, exposure) + caveat + provenance.
- `GET /api/v1/nisar/earthdata-live` → live NASA CMR query, falls back to a labelled cached response.

**Frontend (`http://localhost:5173`):**
- Loads in **Simple** mode by default: satellite basemap, plain layers ("Open water", "Water hidden under plants", "Repeatedly wet"), one-line per-click summary — no jargon. Toggle to **Scientist** for the full console.
- AOI selector lists your areas; selecting one flies the map and loads the timeline.
- Click a pixel → Pixel Trajectory (HH/HV dB chart) + plain-language Evidence Card.
- **📊 Report** opens the in-place analysis report.
- Bottom time slider steps dates (watch layers change per date); the 27 Jul–10 Aug gap is hatched.
- Robustness: a truncated `.h5` in `DATA/` is skipped with a warning (not a crash); cold backend shows "ESTABLISHING TELEMETRY UPLINK…" and retries.

**Regression:** `cd services/api && pytest` (pipeline + report tests); `cd apps/web && npm run build` + `npx vitest run`.

---

## 4. Demo pitch (≈ 4 minutes)

1. **The problem (20s).** "During the monsoon, managers can't see where water spreads, how long it stays, or where it hides under vegetation — clouds blind optical satellites exactly when flooding peaks, and standard flood maps show only *open* water."
2. **Why NISAR L-band (20s).** "NISAR's 24 cm L-band sees through clouds *and* penetrates canopy, so it reveals water hidden under vegetation that optical sensors miss."
3. **Live — Simple mode (60s).** Pick the area → show open-water and "water hidden under plants" layers → click a point → read the plain one-line summary and the Evidence Card. Open the **Report**.
4. **Live — Scientist mode (60s).** Toggle over: HH/HV dB trajectory, dynamic Otsu open water, **ΔHH ≥ +3 dB** double-bounce flooded vegetation, **M-of-N** hydroperiod, GMM regimes, maturity badges, acquisition-gap band, provenance modal.
5. **The Gandak result — honest (40s).** "Real NISAR, track 149, frames 074/075/076 mosaicked, 4 vs 28 Sept 2026, one day from NASA's MODIS view. Here open water actually **receded** between visits while **canopy-hidden flooded vegetation spread** — the signal MODIS optical can't see. That's the L-band advantage, shown honestly."
6. **The differentiator (30s).** "Open source: clone it, drop any NISAR granules in `DATA/`, run one command, and analyze *your own* area — with multi-frame mosaic for full coverage."
7. **Close on honesty (10s).** "Every layer is a radar-derived indication for inspection, never a confirmed flood. Numbers are computed, sources are shown, limitations are explicit."

---

## 5. Known limitations (state them — credibility)
- ~12-day NISAR repeat → short windows give a **change triad (Plan C)**, not a full-season hydroperiod; a 9-day flood window may have only 1–2 same-track passes.
- A descending frame is a tilted swath — corners of the bounding box honestly show "no data."
- OPERA DSWx / JRC / ESA WorldCover layers are off unless their GeoTIFFs are supplied (shown "not loaded", never faked).
- Groundwater/aquifer context (GSDA/CGWB) is official hydrogeology, never a direct SAR detection.
