# GeoSAR Intelligence — *GeoSAR Drishti* ("The Monsoon Dance of Water")
## Software Requirements Specification (SRS) & Development Implementation Blueprint

**NASA Space Apps Challenge 2026 — CH-06: Dancing with the SARs**  
**Project Title:** **GeoSAR Drishti** (*by GeoSAR Intelligence*) — *"Tracking the Monsoon Dance of Open and Canopy-Hidden Water with NASA–ISRO NISAR"*  
**Team Name:** Cosmos InfoVerse Techky  
**Organisation:** InfoVerse Cosmos / InfoVerse Tech Services  
**Version:** 4.0 — Production-Ready Client–Server Architecture (JavaScript NASA–ISRO Telemetry UI + FastAPI Hybrid NASA Earthdata/Local Cache Server + Graceful Fallbacks)  
**Date:** 14 November 2026  
**Event Window:** 14–15 November 2026 (Wainganga College of Engineering & Management — WCEM, Nagpur)

---

### Official Team Roster — Cosmos InfoVerse Techky

| # | Team Member Name | Space Apps / GitHub Handle | Role & Primary Module Ownership | Location |
| :- | :--- | :--- | :--- | :--- |
| 1 | **Pravin Tawade** | `@cosmosinfoverse` | **Team Owner** — System Architecture, L-Band SAR Physics & Mission Lead | India |
| 2 | **kaushik zade** | `@kaushik7` | FastAPI Backend Server, NASA `earthaccess` Connector & Offline SAR Raster Processor | India |
| 3 | **Sharv Dalal** | `@shardstax` | NASA–ISRO Mission Telemetry UI (`Vite + React JS`, `MapLibre GL JS`, Monsoon Time Slider) | India |
| 4 | **Himanshu Sharma** | `@lunar_node` | NISAR L2 `GCOV` Data Gate, `PROVISIONAL`/`VALIDATED` Calibration & OPERA DSWx / JRC Validation | India |
| 5 | **Sakshi Manav Tayade** | `@sakshitayade` | Unsupervised GMM Regime Clustering (`scikit-learn`), ESA WorldCover, OSM Exposure & Nagpur Context | India |
| 6 | **Prashan Arya** | `@prashan_arya` | Template-Grounded Evidence Card Service, Error/Fallback QA & Hourly Git Compliance Officer | India |

> **Critical Local & Global Rule Alignment:** All $6$ members above are registered on the official NASA Space Apps portal under **Cosmos InfoVerse Techky**. Per the Nagpur Participant Handbook (WCEM), the repository must be created fresh after $12:00\text{ PM}$ on $14\text{ November }2026$, every team member must push genuine incremental commits from their own personal GitHub account at least once every hour, no AI tool may appear as a Git author/co-author, and a hard code freeze applies at $2:00\text{ PM}$ on $15\text{ November }2026$.

---

## 1. Executive Summary & Problem Statement

### 1.1 Short Submission Problem Statement (One-Liner)
> *During the monsoon, floodplain managers cannot see where water spreads, how long it stays, or where it hides beneath vegetation, because clouds blind optical satellites and standard flood maps only show open water.*

### 1.2 Full Problem Statement
Monsoon floodplains—such as the **Brahmaputra Valley in Assam** (Majuli–Kaziranga stretch) and regional river corridors like the **Wainganga–Kanhan basin in Nagpur, Maharashtra**—experience complex seasonal inundation every year, impacting wetlands (*beels*), wildlife habitats, farmlands, and rural villages. In $2026$, a severe spell of heavy monsoon rainfall between $18\text{ and }21\text{ July}$ inundated $16\text{ districts}$ and $794\text{ villages}$ in Assam, with floodwaters persisting through late July and into early August. Yet wetland managers, protected-area wardens, and district disaster planners lack a clear picture of the monsoon season as a whole due to **three critical observational gaps**:

1. **Cloud Blindness During Peak Monsoon:** Optical satellites (Landsat, Sentinel-2) are blocked by persistent cloud cover during the exact months when inundation peaks.
2. **The "Hidden Water" Blind Spot:** Conventional flood maps and optical water archives (such as JRC Global Surface Water) detect only *open water*. Water standing beneath tall grassland, riparian forest, or paddy crops goes uncounted—even though this canopy-hidden water shapes wetland ecology, wildlife refugia, agricultural inundation, and village exposure.
3. **Single-Snapshot Myopia:** A single flood image cannot tell whether an inundation pattern is historically normal or unusual, how many observations a place stayed wet across the season (**hydroperiod**), or which rural roads and settlements were wet repeatedly rather than once.

### 1.3 Our Solution: *GeoSAR Drishti* ("The Monsoon Dance of Water")
**GeoSAR Drishti** (built on the **GeoSAR Intelligence** client–server platform) is an interactive NASA–ISRO mission telemetry application that uses **NISAR L-band ($24\text{ cm}$) radar time series** across a monsoon season to reveal:
* **Open Water vs. Canopy-Hidden Water:** Separating specular dark open water from bright L-band **double-bounce flooded vegetation** ($\Delta\text{HH} \ge +3\text{ dB}$).
* **Monsoon Hydroperiod ($M$ of $N$ Observations Wet):** Quantifying inundation persistence across all valid same-track NISAR acquisitions.
* **Normal vs. Unusual Context:** Comparing radar-indicated *open water* against historical **JRC Global Surface Water Occurrence**, cross-checking agreement with **OPERA DSWx-S1 / DSWx-NI**, and separating **paddy-like agricultural inundation** from natural wetlands using **ESA WorldCover**.
* **Repeatedly Wet Roads & Settlements (Exposure Log):** Intersecting **OpenStreetMap (OSM)** roads and village footprints with multi-date wet pixels to flag prioritized **"Ground Inspection Candidates"** (never unverified damage claims).
* **Plain-Language Radar Evidence Cards:** Clicking any location triggers a FastAPI request that returns a structured telemetry card (using deterministic templates and an optional tool-grounded LLM narrator) explaining what NISAR observed, when, and with what physical confidence.

---

## 2. Why NISAR L-Band is Essential (The Physics Baseline)

1. **L-Band Canopy Penetration ($24\text{ cm}$ wavelength, $1.25\text{ GHz}$):** Unlike Sentinel-1 C-band radar ($\approx 5.6\text{ cm}$ wavelength), which scatters primarily off the top leaves and twigs of dense vegetation, NISAR’s longer $24\text{ cm}$ L-band microwaves penetrate through tall wetland grass, paddy crops, and moderate forest canopies.
2. **Physics of the Three Surface States in L2 `GCOV` ($\gamma^0$ Backscatter):**
   * **Open Water (Specular Reflection):** Smooth open water acts like a mirror, reflecting side-looking radar pulses away from the sensor. Both co-polarized ($\text{HH}$) and cross-polarized ($\text{HV}$) backscatter drop sharply (dark signature, typically $\text{HH}_{\text{dB}} < -16\text{ dB}$).
   * **Flooded Vegetation (Dihedral Double-Bounce):** When water stands beneath vertical plant stems or tree trunks, the L-band pulse penetrates the canopy, bounces off the horizontal water surface, hits the vertical trunk/stem, and reflects directly back toward the satellite. This **double-bounce effect** produces a sharp jump in $\text{HH}$ backscatter ($\Delta\text{HH} \ge +3.0\text{ dB}$ compared to a dry post-monsoon reference date) and an increase in the linear $\text{HH}/\text{HV}$ ratio.
   * **Critical Decibel Math Rule:** In decibel ($\text{dB}$) space, where $\gamma^0_{\text{dB}} = 10 \log_{10}(\gamma^0_{\text{linear}})$, the linear ratio $\gamma^0_{\text{HH}} / \gamma^0_{\text{HV}}$ MUST be computed as a subtraction:
     $$\text{Polarisation Ratio (dB)} = \text{HH}_{\text{dB}} - \text{HV}_{\text{dB}}$$
     *(Never divide negative $\text{dB}$ numbers directly in code.)*

---

## 3. Dual-AOI Strategy, Data Realities & 4-Step Fallback Ladder

### 3.1 Pre-Configured Dual-AOI Mission Selector ($\approx 30 \times 30\text{ km}$ Windows)
To satisfy both **global NASA challenge criteria** and **local Nagpur relevance at WCEM**, the application ships with two pre-configured AOIs selectable in the top telemetry bar:

| AOI ID | Region Name | Role in Demo | Key Scientific & Contextual Layers |
| :--- | :--- | :--- | :--- |
| **`aoi_assam_majuli`** *(Primary Default)* | **Majuli–Kaziranga Floodplain, Brahmaputra Valley, Assam** | **Primary CH-06 Monsoon Time-Series Showcase** | NISAR L2 `GCOV` same-track time series (June–Nov $2026$, covering the $18\text{–}21\text{ July}$ flood spell), Open Water vs. Flooded Vegetation, Hydroperiod ($M/N$), GMM Regimes, JRC Water Occurrence, OPERA DSWx-S1 agreement, ESA WorldCover (Paddy vs. *Beel* Wetland), OSM Roads/Villages. |
| **`aoi_nagpur_kanhan`** *(Regional Pilot)* | **Kanhan–Pench / Wainganga Corridor, Nagpur District, Maharashtra** | **Local Watershed & Multi-Source Context Showcase** | NISAR L-band / S-band water extent indication, GSDA/CGWB watershed & hydrogeological aquifer context (Deccan Trap / Alluvium), and Zilla Parishad agricultural belt context. Explicitly labels groundwater as official hydrogeological context, never direct SAR detection. |

### 3.2 Real-World NISAR Data Realities & Engineering Mitigations

| Data Reality | Project Risk | Built-in Mitigation in *GeoSAR Drishti* |
| :--- | :--- | :--- |
| **June–Oct $2026$ data are `PROVISIONAL`; Nov $2026$ is `VALIDATED`** | Radiometric calibration jump between maturity levels | Query overlapping `PROVISIONAL` and `VALIDATED` granules during the $21\text{–}23\text{ October }2026$ transition window to check offset; display a mandatory `PROVISIONAL` (Amber) or `VALIDATED` (Cyan) telemetry badge on every date in the UI. |
| **NISAR observation gap ($27\text{ Jul} \text{ – } 10\text{ Aug }2026$)** | Peak flood recession dates missing | Render an explicit hatched **"SENSOR ACQUISITION GAP (27 JUL – 10 AUG)"** band on the Monsoon Time Slider so users and judges see scientific honesty. |
| **Polarization mode varies by track/frame** | $\text{HV}$ channel may be absent (Single-Pol $\text{HH}$ only) | Backend inspects HDF5 dataset keys first. If $\text{HV}$ is missing, the pipeline automatically activates **Single-Pol $\text{HH}$ Mode** ($\text{HH}$ Otsu open water + $\Delta\text{HH}$ surge indicator) and updates the UI badge. |
| **$\approx 12\text{-day}$ orbital repeat cycle** | Cannot claim exact "days flooded" | Express Hydroperiod strictly as **"$M$ out of $N$ valid NISAR observations wet"** (e.g., $6/9$ acquisitions). |
| **L2 `GCOV` HDF5 granules are huge ($1\text{–}5\text{ GB}$ each)** | Live download/processing will time out during demo | Use `earthaccess` + HTTP Range requests (`h5py`/`rasterio`) in an offline preparation script to extract $\approx 30 \times 30\text{ km}$ AOI subsets into lightweight Cloud-Optimized GeoTIFFs (COGs), RGBA PNG overlays, and JSON summary matrices served by FastAPI. |
| **JRC Global Surface Water is optical** | JRC never sees water under canopy | Restrict the **"Normal vs. Unusual"** JRC comparison strictly to the **Open-Water** class; never compare flooded vegetation against optical JRC. |

### 3.3 The 4-Step Scientific Fallback Ladder (Never Change the App, Step Down Gracefully)
* **Plan A (Full Multi-Pol Season):** Full June–Nov time series with $\text{HH}+\text{HV}$, 3 classes (Open Water, Flooded Vegetation, Dry), GMM regimes, DSWx-S1 agreement, and OSM exposure log.
* **Plan B (If Flooded-Vegetation Signal is Noisy or $\text{HV}$ is Missing):** Step down to verified **Open-Water Hydroperiod ($M/N$)** + $\Delta\text{HH}$ anomaly overlay + JRC Historical Context + OSM Exposure.
* **Plan C (If Only $2\text{–}3$ Compatible Dates Exist in Track):** Render a high-precision **Pre-Monsoon vs. Peak-Monsoon vs. Post-Monsoon Change Triad** with full validation metrics.
* **Plan D (If Primary Assam Frame Has Coverage Issues):** Switch primary default to an alternate monsoon floodplain (e.g., **Kosi Basin, Bihar** or **Kolleru Lake, AP**) or **ASF NISAR Science Team Supplemental Time-Series Frames** alongside the **Nagpur Kanhan–Pench AOI**.

---

## 4. NASA–ISRO Mission Telemetry UI Design System (Strict Non-AI Aesthetic)

To align with authentic **NASA Earthdata Worldview**, **ASF Vertex**, and **ISRO Bhoonidhi / VEDAS** interfaces, the frontend strictly avoids generic "AI startup" tropes (no neon purple/pink gradients, no glowing chatbot avatars, no "magic AI" buttons).

### 4.1 Color Palette & Typography
* **Background Surfaces:** Deep Orbital Slate `#0B0F19` (canvas), Telemetry Panel Navy `#111827` (cards/drawers), Subtle Grid Border `#1E293B`.
* **Agency Accent Colors:**
  * **NASA Mission Blue:** `#0B3D91` (primary active controls, headers) & Telemetry Cyan `#38BDF8` (validated badges, active track outlines).
  * **ISRO Solar Orange:** `#F47216` (time-slider playhead, double-bounce highlight accents, inspection candidate alerts).
* **Scientific Layer Palette (Colorblind-Safe):**
  * **Open Water (Low $\text{HH}$, Low $\text{HV}$):** Deep Radar Cyan-Blue `#0284C7`
  * **Possible Flooded Vegetation (High $\Delta\text{HH}$, High $\text{HH}-\text{HV}$):** Vibrant Emerald-Lime `#10B981`
  * **Paddy-Like Agricultural Inundation (WorldCover Cropland Mask):** Warm Amber-Gold `#F59E0B`
  * **OSM Repeatedly Wet Road / Settlement Inspection Candidate:** High-Contrast Coral Red `#EF4444`
* **Typography:** `Inter` or `IBM Plex Sans` for UI labels; **`JetBrains Mono` or `IBM Plex Mono`** for all coordinates, $\text{dB}$ backscatter values, granule IDs, and area metrics.

### 4.2 Core Workspace Layout (Single-Screen Telemetry Console)
1. **Top Mission Bar:** NASA/ISRO NISAR mission identifier, **Dual-AOI Selector** (`Majuli–Kaziranga [Assam]` | `Kanhan–Pench [Nagpur]`), Active Granule ID, Track/Frame badge, Polarization badge (`Dual-Pol HH+HV`), Maturity badge (`PROVISIONAL` / `VALIDATED`), and Backend Connection Indicator (`LIVE API` / `LOCAL CACHE`).
2. **Center MapLibre GL JS Viewport:** Interactive vector + raster canvas supporting layer toggles (SAR $\text{HH}$ dB, SAR Classification, Hydroperiod $M/N$, GMM Regimes, JRC Occurrence, ESA WorldCover, OSM Exposure) and a before/after split swipe bar.
3. **Bottom Monsoon Time-Series Scrubbing Dock:** Animated timeline from June to November $2026$ showing acquisition ticks, maturity badges per date, and the grey hatched **27 Jul – 10 Aug Acquisition Gap** marker.
4. **Right Telemetry & Evidence Drawer:**
   * **Tab 1 — Scene & Validation Metrics:** Area (sq. km / ha) per class, valid pixel %, **OPERA DSWx-S1 Agreement %**, and JRC anomaly breakdown.
   * **Tab 2 — Pixel Click Trajectory & Evidence Card:** Interactive chart of $\text{HH}_{\text{dB}}$ and $\text{HV}_{\text{dB}}$ across all monsoon dates for the clicked coordinate, paired with the plain-language **Radar Evidence Card**.
   * **Tab 3 — OSM Inspection Candidates Log:** Sortable table of roads and villages ranked by number of wet observations ($M/N$), clickable to fly the map directly to the segment.

---

## 5. Core Scientific Pipeline & Honest Role of AI

### 5.1 Pre-Processing & Radiometric Preparation (Offline Python Script $\rightarrow$ FastAPI Data Store)
1. **Stream & Subset:** Query same-track NISAR L2 `GCOV` granules via `earthaccess`. Extract $\gamma^0_{\text{HH}}$ and $\gamma^0_{\text{HV}}$ arrays only for the $\approx 30 \times 30\text{ km}$ AOI bounding box.
2. **Validity & Terrain Masking:** Apply NISAR quality/layover-shadow masks and a Copernicus DEM slope mask (exclude slopes $> 5^\circ$ so hill shadows are never misclassified as water).
3. **Speckle Filtering & Decibel Conversion:** Apply a $3 \times 3$ median/Lee filter on linear power, clip floor at $10^{-5}$, and convert to decibels:
   $$\text{HH}_{\text{dB}} = 10 \log_{10}(\gamma^0_{\text{HH}}), \quad \text{HV}_{\text{dB}} = 10 \log_{10}(\gamma^0_{\text{HV}}), \quad \text{Ratio}_{\text{dB}} = \text{HH}_{\text{dB}} - \text{HV}_{\text{dB}}$$

### 5.2 Per-Date Three-Class Physics Classifier
For each acquisition date $t$, relative to the post-monsoon dry reference scene $t_{\text{ref}}$:
* **Class 1 — Open Water:** $\text{HH}_{\text{dB}}(t) < \tau_{\text{Otsu, HH}}(t)$ AND $\text{HV}_{\text{dB}}(t) < \tau_{\text{HV}}$ (where $\tau_{\text{Otsu, HH}}(t)$ is computed dynamically per scene within $[-22\text{ dB}, -13\text{ dB}]$).
* **Class 2 — Possible Flooded Vegetation (Canopy-Hidden Water):** Not Open Water, located inside the vegetation/wetland/cropland mask, exhibiting a strong co-pol double-bounce surge:
  $$\Delta\text{HH}_{\text{dB}}(t) = \text{HH}_{\text{dB}}(t) - \text{HH}_{\text{dB}}(t_{\text{ref}}) \ge +3.0\text{ dB} \quad \text{AND} \quad \Delta\text{Ratio}_{\text{dB}}(t) \ge +1.5\text{ dB}$$
  *Sub-labeling via **ESA WorldCover 10m**:* Pixels falling on WorldCover Class 40 (Cropland) are sub-labeled **"Paddy-Like Agricultural Inundation"**; pixels on Class 90/95/10/30 (Herbaceous Wetland, Tree Cover, Grassland) are labeled **"Natural Flooded Vegetation"**.
* **Class 3 — Dry / Other Surface:** All remaining valid pixels.

### 5.3 Monsoon Hydroperiod Calculation ($M$ of $N$ Observations)
For every pixel $(x,y)$ with $N(x,y)$ valid observations across the monsoon stack:
$$\text{Hydroperiod}_{\text{Total}}(x,y) = \frac{M_{\text{open}}(x,y) + M_{\text{flooded\_veg}}(x,y)}{N(x,y)}$$
Stored both as raw counts ($M$ and $N$) and percentage, ensuring the UI always reports **"Wet in $M$ of $N$ NISAR observations"**.

### 5.4 Honest Role of Machine Learning: Unsupervised GMM Hydrological Regimes
We do **not** train deep neural networks on unverified flood labels during the 48-hour hackathon. Instead, we run an unsupervised **Gaussian Mixture Model (`sklearn.mixture.GaussianMixture`, $k=5$)** on each pixel’s temporal SAR feature vector:
$$\mathbf{x}_i = \left[ \mu_{\text{HH}}, \, \min(\text{HH}), \, \max(\Delta\text{HH}), \, \mu_{(\text{HH}-\text{HV})}, \, \frac{M_{\text{open}}}{N}, \, \frac{M_{\text{fveg}}}{N} \right]$$
The resulting clusters are mapped by the team to five interpretable **Hydrological Regimes**:
1. *Permanent River / Deep Channel*
2. *Seasonal Open Floodplain / Beel*
3. *Seasonally Flooded Canopy / Tall Grassland*
4. *Seasonal Paddy-Like Inundation Cycle*
5. *Stable Dry Upland / Levee*

### 5.5 Validation & Exposure Pipeline
* **OPERA DSWx-S1 / DSWx-NI Agreement:** Compare NISAR Open Water against temporally nearest OPERA Dynamic Surface Water Extent (`DSWx-S1` or `DSWx-NI` post-Oct 21) and report **Spatial Agreement %** (explicitly termed *inter-sensor agreement*, never "ground-truth accuracy").
* **JRC Historical Context:** Intersect NISAR Open Water with JRC Water Occurrence ($0\text{–}100\%$). Open water on pixels with JRC occurrence $< 20\%$ is flagged as **"Unusual / Low-Historical-Frequency Open Water"**.
* **OSM Infrastructure Exposure (`osmnx` + `geopandas`):** Intersect OpenStreetMap roads (`highway=*`) and settlements (`place=village|hamlet|town`) with the Hydroperiod raster. Any road segment or settlement intersecting wet pixels on $M \ge 3$ dates is exported to the **Inspection Candidates Log**.

---

## 6. Lean Client–Server Architecture (JavaScript UI + FastAPI Server + NASA Earthdata)

To ensure **true client–server separation**, cloud deployability, and sub-second responsiveness without overengineering, the system uses a **Two-Tier Hybrid FastAPI Architecture**:

```text
+-----------------------------------------------------------------------------------+
| CLIENT TIER (Custom Domain — Vercel / Cloudflare Pages / Netlify)                 |
| apps/web (Vite + React 18 JavaScript ES6+/JSX + MapLibre GL JS + Tailwind CSS)    |
|  - Renders NASA-ISRO Telemetry UI, Time Slider, Split Map, Recharts dB Trajectory |
|  - Communicates strictly via REST JSON & PNG Overlay URLs (VITE_API_BASE_URL)     |
+-----------------------------------------+-----------------------------------------+
                                          | HTTPS REST API (CORS Enabled)
                                          v
+-----------------------------------------------------------------------------------+
| SERVER TIER (Cloud Container — Render / Railway / Fly.io / Cloud Run)             |
| services/api (Python 3.11 + FastAPI + Uvicorn + Rasterio + NumPy + Earthaccess)   |
|                                                                                   |
|  +-----------------------------------+   +-------------------------------------+  |
|  | 1. Live External Connectors       |   | 2. Local Pre-Computed Data Store    |  |
|  | - NASA Earthdata CMR / ASF API    |   |    (services/api/data_store/)       |  |
|  |   (Live granule search & metadata |   | - Validated AOI COGs & RGBA PNGs    |  |
|  |    via server EARTHDATA_TOKEN)    |   | - Pixel dB Time-Series Lookup Grids |  |
|  | - Optional LLM API (Evidence Card |   | - Pre-computed GMM, DSWx & OSM JSON |  |
|  |   narration with 3s timeout)      |   | - Instant Deterministic Fallbacks   |  |
|  +-----------------------------------+   +-------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 6.1 Why This Hybrid Architecture is Optimal for a 48-Hour Hackathon
1. **Real Client–Server Communication:** The frontend is a pure JavaScript (`JSX`) client deployed on a custom domain; all data queries, pixel time-series extractions, live NASA CMR metadata checks, and Evidence Card generations happen over HTTP via the **FastAPI** backend.
2. **Zero Database Setup Overhead:** Instead of wasting 6 hours configuring PostgreSQL/PostGIS migrations on free cloud tiers, spatial manifests and OSM inspection candidates are stored as indexed **GeoJSON + JSON + lightweight NumPy/COG cubes** inside `services/api/data_store/`. FastAPI loads them into memory on startup for $< 20\text{ ms}$ response times.
3. **Live NASA Earthdata Attachment with Zero-Crash Guarantee:** FastAPI includes a live `/api/v1/nisar/earthdata-live` endpoint powered by NASA’s `earthaccess` / CMR API to prove live NASA catalogue integration, while automatically falling back to the verified local manifest if venue Wi-Fi or Earthdata servers hiccup.

### 6.2 Monorepo Directory Structure (JavaScript Frontend + Python FastAPI Backend)

```text
geosar-GeoSAR Drishti/
├── apps/
│   └── web/                               # FRONTEND CLIENT (JavaScript ES6+ / JSX)
│       ├── public/
│       ├── src/
│       │   ├── api/
│       │   │   └── client.js              # Fetch wrapper with timeout & error handling
│       │   ├── components/
│       │   │   ├── TopTelemetryBar.jsx    # NASA-ISRO header, AOI selector, status pills
│       │   │   ├── MapWorkspace.jsx       # MapLibre GL JS canvas + RGBA raster overlays
│       │   │   ├── MonsoonTimeSlider.jsx  # Animated date scrubber + 27 Jul-10 Aug gap band
│       │   │   ├── PixelTrajectoryChart.jsx # Recharts HH/HV dB time-series plot
│       │   │   ├── EvidenceCardPanel.jsx  # Plain-language radar evidence card + confidence
│       │   │   ├── ExposureTable.jsx      # OSM roads/villages inspection candidate log
│       │   │   └── ProvenanceModal.jsx    # Granule IDs, DSWx agreement & limitations
│       │   ├── store/
│       │   │   └── useMissionStore.js     # Zustand state (active AOI, date, layer, pixel)
│       │   ├── App.jsx
│       │   ├── main.jsx
│       │   └── index.css                  # Tailwind + NASA-ISRO dark telemetry styles
│       ├── index.html
│       ├── jsconfig.json                  # Pure JS path aliases (@/* -> ./src/*)
│       ├── vite.config.js
│       └── package.json
├── services/
│   └── api/                               # BACKEND SERVER (FastAPI Python 3.11+)
│       ├── app/
│       │   ├── main.py                    # FastAPI app, CORS, global exception handlers
│       │   ├── config.py                  # Env vars (EARTHDATA_TOKEN, LLM_API_KEY, CORS)
│       │   ├── routers/
│       │   │   ├── aois.py                # AOI metadata, bounds & available dates
│       │   │   ├── nisar.py               # Live NASA CMR query + local granule timeline
│       │   │   ├── layers.py              # Serves RGBA PNG overlays & metrics per date
│       │   │   ├── inspect.py             # Pixel click dB trajectory + Evidence Card API
│       │   │   └── exposure.py            # OSM roads/settlements inspection list + provenance
│       │   └── services/
│       │       ├── earthdata_client.py    # NASA CMR / ASF search with 4s timeout fallback
│       │       ├── raster_sampler.py      # Fast coordinate-to-pixel time-series lookup
│       │       └── evidence_narrator.py   # Deterministic template + optional LLM narrator
│       ├── data_store/                    # Pre-computed & cached AOI packs (committed)
│       │   ├── aoi_assam_majuli/
│       │   │   ├── manifest.json          # Granule IDs, dates, maturity, bounds, stats
│       │   │   ├── overlays/              # Georeferenced RGBA PNGs per date & hydroperiod
│       │   │   ├── time_series_cube.npz   # Compressed 3D array for instant pixel click lookup
│       │   │   └── osm_exposure.geojson   # Flagged OSM road segments & villages
│       │   └── aoi_nagpur_kanhan/
│       │       ├── manifest.json
│       │       ├── overlays/
│       │       ├── time_series_cube.npz
│       │       └── context_layers.geojson # GSDA/CGWB watersheds & hydrogeology context
│       ├── requirements.txt
│       └── Dockerfile
├── scripts/                               # OFFLINE DATA GATE & PROCESSING SCRIPTS
│   ├── 01_data_gate_vertex_query.py       # Queries ASF/CMR for same-track NISAR GCOV
│   ├── 02_subset_and_classify_sar.py      # Streams AOI, runs Otsu + Double-Bounce + Hydroperiod
│   ├── 03_gmm_and_validation.py           # Runs scikit-learn GMM, DSWx-S1 & JRC comparison
│   └── 04_osm_exposure_extract.py         # Intersects OSM roads/villages with wet frequency
├── .env.example
├── README.md                              # Includes Live URLs, Data Citations & AI Disclosure
└── package.json
```

---

## 7. REST API Blueprint, Error Handling & Graceful Fallback Contract

### 7.1 FastAPI Endpoint Specification (`services/api`)

| Method | Endpoint | Description | Primary Data Source | Fallback if External/Live Fails |
| :- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Returns server health, active data packs, and NASA Earthdata token configuration status. | Internal state | Always returns `200 OK` |
| `GET` | `/api/v1/aois` | Lists available mission AOIs (`aoi_assam_majuli`, `aoi_nagpur_kanhan`), WGS84 bounding boxes `[west, south, east, north]`, default zoom, and available thematic layers. | `data_store/*/manifest.json` | Static default dictionary |
| `GET` | `/api/v1/aois/{aoi_id}/timeline` | Returns all NISAR acquisition dates for the AOI, granule IDs, track/frame, polarization (`HH+HV`), maturity badge (`PROVISIONAL`/`VALIDATED`), observation gaps, and per-date area metrics. | `data_store/{aoi_id}/manifest.json` | Cached baseline timeline |
| `GET` | `/api/v1/nisar/earthdata-live` | Queries **live NASA CMR / ASF Search API** (`short_name=NISAR_L2_GCOV_*`) for a bounding box to demonstrate live NASA Earthdata connectivity. | Live NASA CMR REST API (`4.0s` timeout) | Returns cached CMR granule response with `"source_mode": "LOCAL_VERIFIED_CACHE"` |
| `GET` | `/api/v1/layers/{aoi_id}/{layer_id}.png` | Serves georeferenced transparent RGBA PNG overlays (`open_water`, `flooded_veg`, `hydroperiod`, `gmm_regimes`, `jrc_anomaly`) for MapLibre `image` source rendering. | `data_store/{aoi_id}/overlays/` | Generates clean transparent placeholder PNG with warning header |
| `GET` | `/api/v1/aois/{aoi_id}/inspect` | Query params: `?lat=26.95&lon=94.15`. Extracts the clicked pixel’s full monsoon $\text{HH}_{\text{dB}}$ and $\text{HV}_{\text{dB}}$ trajectory, hydroperiod ($M/N$), GMM regime class, JRC occurrence %, and WorldCover class. | `time_series_cube.npz` via `raster_sampler.py` | Returns structured `"out_of_bounds"` or `"nodata"` telemetry card if clicked outside AOI |
| `POST` | `/api/v1/evidence-card` | Accepts pixel telemetry JSON from `/inspect` and returns a plain-language **Radar Evidence Card** explaining what NISAR observed, when, and confidence level. | Optional LLM API (`3.0s` timeout) grounded strictly on input JSON | **Instant Deterministic Physics Template** (zero latency, $100\%$ factual) |
| `GET` | `/api/v1/aois/{aoi_id}/exposure` | Returns GeoJSON + ranked table of OSM road segments and villages that fell within wet pixels across $M \ge 3$ acquisitions ("Ground Inspection Candidates"). | `osm_exposure.geojson` | Empty FeatureCollection with status message |
| `GET` | `/api/v1/aois/{aoi_id}/provenance` | Returns complete scientific provenance manifest: exact NISAR granule DOIs/IDs, Otsu thresholds, $\Delta\text{HH}$ parameters, OPERA DSWx-S1 agreement %, and explicit limitations. | `manifest.json` | Always available |

### 7.2 Standardized Response Envelope & Fault-Tolerant Error Handling
Every JSON response from FastAPI follows a predictable envelope so the React JavaScript frontend never encounters `undefined` property crashes:

```json
{
  "status": "ok",
  "aoi_id": "aoi_assam_majuli",
  "source_mode": "LOCAL_VERIFIED_CACHE",
  "fallback_active": false,
  "warning": null,
  "data": { ... }
}
```

#### Mandatory Error Handling Rules in Code:
1. **Out-of-Bounds Map Clicks (`422` Prevention):** If a user clicks on the map outside the $30 \times 30\text{ km}$ AOI boundary, `/api/v1/aois/{aoi_id}/inspect` does **not** throw a `500 IndexError`. It catches the coordinate bounds check and returns `"status": "outside_aoi"` with a friendly message: *"Clicked coordinate lies outside the pre-computed NISAR AOI footprint. Click inside the highlighted cyan telemetry boundary."*
2. **External API Timeout Protection (`httpx.Timeout(3.5)`):** Both the live NASA CMR query (`earthdata_client.py`) and the optional LLM Evidence Card narrator (`evidence_narrator.py`) use strict timeouts. If an external API takes longer than $3.5\text{ seconds}$ or returns an HTTP error, the backend catches the exception, logs it, and serves the deterministic local fallback without interrupting the user experience.
3. **Frontend Offline Resilience (`apps/web/src/api/client.js`):** If the cloud backend is temporarily cold-starting (e.g., on Render free tier), the frontend displays a NASA-style **`ESTABLISHING TELEMETRY UPLINK...`** banner with automatic retry, and bundles a lightweight static mirror of `manifest.json` in `apps/web/public/fallback_data/` so the map and time slider remain interactive even if the entire venue loses internet!

### 7.3 Deterministic vs. LLM-Grounded Evidence Card Design
When a user clicks any pixel at `(lat, lon)`, the **Radar Evidence Card** is constructed strictly from computed numbers—never free-form hallucination:

> **Example Deterministic / Grounded Evidence Card Output:**  
> **Location:** $26.9421^\circ\text{ N}, 94.1834^\circ\text{ E}$ (Majuli–Kaziranga Sector)  
> **Hydrological Regime (GMM):** Seasonally Flooded Canopy / Tall Grassland  
> **Monsoon Persistence (Hydroperiod):** Wet in **$6\text{ out of }9$ valid NISAR L-band observations** ($66.7\%$).  
> **Radar Physics Evidence:** During the $22\text{ July }2026$ acquisition (`PROVISIONAL`), $\text{HH}$ backscatter jumped by **$+4.6\text{ dB}$** (from $-11.8\text{ dB}$ dry baseline to $-7.2\text{ dB}$) with a $+2.4\text{ dB}$ rise in $\text{HH}-\text{HV}$ difference—consistent with L-band dihedral **double-bounce scattering** from water beneath emergent vegetation.  
> **Land Cover & Historical Context:** Classified as Herbaceous Wetland in ESA WorldCover ($10\text{ m}$). Optical JRC historical water occurrence is low ($14\%$) because optical sensors cannot penetrate the vegetation canopy.  
> **Confidence & Caveat:** **Moderate-High** (Multi-date dual-pol signature). *This is a radar-derived surface/canopy-water indication for field inspection, not a confirmed flood-depth measurement.*

---

## 8. Cloud Deployment Blueprint (Custom Domain Frontend + Cloud FastAPI Server)

### 8.1 Backend Server Deployment (`services/api` $\rightarrow$ Render / Railway / Cloud Run)
1. **Committed AOI Data Pack:** Keep the processed `services/api/data_store/` directory lightweight ($< 35\text{ MB}$ total by storing 8-bit quantized RGBA PNG overlays and compressed `.npz` float16 time-series arrays) so it commits cleanly into the repository and deploys automatically with the FastAPI container.
2. **Start Command:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```
3. **Environment Variables on Server Host:**
   * `EARTHDATA_TOKEN`: Your NASA Earthdata Bearer Token (for `/api/v1/nisar/earthdata-live`).
   * `CORS_ORIGINS`: `*` or your custom frontend domain (e.g., `https://GeoSAR Drishti.infoverse.tech`).
   * `LLM_API_KEY`: *(Optional)* API key for Groq / Gemini / OpenRouter; if left blank, the server automatically runs in $100\%$ deterministic template mode.

### 8.2 Frontend Deployment (`apps/web` $\rightarrow$ Vercel / Netlify / Cloudflare Pages + Custom Domain)
1. **Build Configuration:**
   * **Root Directory:** `apps/web`
   * **Build Command:** `npm run build` (or `pnpm build`)
   * **Output Directory:** `dist`
   * **Environment Variable:** `VITE_API_BASE_URL=https://your-fastapi-service.onrender.com`
2. **Custom Domain Attachment:** Point a clean subdomain (e.g., `GeoSAR Drishti.cosmosinfoverse.tech` or your domain’s CNAME record) to Vercel/Netlify and place the live URL at the very top of `README.md`.

---

## 9. 48-Hour Execution Plan for Cosmos InfoVerse Techky (6 Members)

### Phase 1: Data Gate & Core Scaffold (14 Nov, 12:00 PM – 4:00 PM)
* **All 6 Members:** Verify local `git config user.name` and `git config user.email`. Push first human commits to the newly created public repo.
* **Himanshu (`@lunar_node`) & Pravin (`@cosmosinfoverse`):** Run `scripts/01_data_gate_vertex_query.py` on ASF Vertex / NASA Earthdata for **Majuli–Kaziranga** and **Nagpur Kanhan–Pench**. Lock the same-track L2 `GCOV` granule list and verify $\text{HH}/\text{HV}$ availability.
* **Kaushik (`@kaushik7`):** Stand up the `services/api` FastAPI skeleton (`/health`, `/aois`, `/timeline`, CORS) and deploy the staging service early.
* **Sharv (`@shardstax`):** Initialize `apps/web` (Vite + React JS + Tailwind + MapLibre GL JS) with the NASA–ISRO dark telemetry theme and Dual-AOI switcher.
* **Sakshi (`@sakshitayade`):** Download ESA WorldCover ($10\text{ m}$), JRC Water Occurrence, and OSM roads/villages (`osmnx`) clipped to both $30 \times 30\text{ km}$ AOI bounding boxes.
* **Prashan (`@prashan_arya`):** Set up the hourly Git push tracker, error-handling wrappers, and deterministic Evidence Card templates.

### Phase 2: SAR Physics Pipeline & Client–Server Wiring (14 Nov, 4:00 PM – 11:00 PM)
* **Kaushik & Himanshu:** Run `02_subset_and_classify_sar.py` to generate per-date Open Water (Otsu) + Flooded Vegetation ($\Delta\text{HH} \ge +3\text{ dB}$) rasters, Hydroperiod ($M/N$) raster, RGBA PNG overlays, and `time_series_cube.npz`.
* **Sakshi:** Run `03_gmm_and_validation.py` (`scikit-learn` 5-cluster GMM regimes + OPERA DSWx-S1 agreement %) and `04_osm_exposure_extract.py` (flagged OSM roads/villages GeoJSON).
* **Sharv & Prashan:** Connect the React frontend (`client.js`) to FastAPI endpoints (`/timeline`, `/layers/*.png`, `/inspect`, `/evidence-card`, `/exposure`) and build the Monsoon Time Slider with the **27 Jul – 10 Aug Gap** indicator.

### Phase 3: Overnight Polish, Nagpur Context & Cloud Deployment (14 Nov, 11:00 PM – 15 Nov, 9:00 AM)
* Integrate the second preset (**AOI-2: Nagpur Kanhan–Pench Corridor**) with watershed and hydrogeology context layers.
* Deploy FastAPI backend and custom-domain React frontend; test full client–server communication and offline fallback behavior.
* Maintain genuine hourly human commits across all $6$ team members overnight.

### Phase 4: Verification, Pitch Rehearsal & Code Freeze (15 Nov, 9:00 AM – 2:00 PM)
* Complete `README.md` with live domain URL, architecture diagram, mandatory NASA/ESA/JRC/OSM data citations, and **AI Usage Disclosure**.
* Verify all $6$ members appear in `GitHub -> Insights -> Contributors` and that no AI bot/co-author tags exist in `git log`.
* **Hard Code Freeze before 2:00 PM IST on 15 November 2026.**

---

## 10. Winning Judge Pitch Guide ("What to Say" vs. "What Never to Say")

| Say This (Scientifically Defensible & Impressive) | Never Say This (Triggers Judge Disqualification/Skepticism) |
| :--- | :--- |
| *"At this wetland pixel, $6\text{ out of }9$ NISAR L-band acquisitions showed a $+4.5\text{ dB}$ $\text{HH}$ surge and elevated $\text{HH}-\text{HV}$ difference consistent with double-bounce scattering under vegetation."* | *"Our AI detects floods under trees with $95\%$ accuracy."* |
| *"Our open-water layer achieved $84\%$ spatial agreement with temporally matched OPERA DSWx-S1 observations."* | *"Our accuracy is $84\%$."* *(DSWx-S1 is another satellite product, so call it **inter-sensor agreement**, not ground-truth accuracy.)* |
| *"This rural road segment intersected radar-indicated wet pixels in $5\text{ of }9$ monsoon acquisitions, making it a prioritized candidate for ground inspection."* | *"This road is washed out and $5,000$ people are stranded."* |
| *"We use unsupervised Gaussian Mixture Models on pixel backscatter trajectories to group seasonal hydrological regimes, and a template-grounded narrator to explain exact radar numbers."* | *"Our LLM analyzes satellite images to predict flood depth and underground aquifers."* |

---

## 11. Mandatory Data Citations & AI Usage Disclosure Template

Include the following sections directly in your repository `README.md`:

### Data & Mission Citations
* **NASA–ISRO NISAR L2 GCOV Data:** Accessed via NASA Earthdata / Alaska Satellite Facility (ASF DAAC) and ISRO Bhoonidhi. Contains modified Copernicus/NASA/ISRO mission data ($2026$).
* **OPERA DSWx-S1 / DSWx-NI:** Observational Products for End-Users from Remote Sensing Analysis (OPERA), Jet Propulsion Laboratory (JPL) / NASA Earthdata.
* **EC JRC / Google Global Surface Water:** Pekel et al. (*Nature*, $2016$), European Commission Joint Research Centre.
* **ESA WorldCover $10\text{ m}$:** ESA WorldCover Consortium ($2021$/$2024$).
* **Nagpur Regional Context:** Groundwater Surveys and Development Agency (GSDA, Govt. of Maharashtra) & Central Ground Water Board (CGWB, Nagpur District Aquifer Management Plan).
* **OpenStreetMap:** © OpenStreetMap contributors, extracted via `osmnx`.

### AI Usage Disclosure (Nagpur Handbook Compliant)
```markdown
## AI Usage Disclosure
Our team (**Cosmos InfoVerse Techky**) used generative AI tools strictly as human-supervised development and documentation assistants during the NASA Space Apps Challenge 2026:
- **Development Assistance:** Gemini / Claude / Copilot were used to assist withSRS refinement, FastAPI boilerplate structuring, and React UI component debugging.
- **In-App Machine Learning & Narration:** The application uses `scikit-learn` Gaussian Mixture Models (GMM) for unsupervised time-series clustering of SAR backscatter trajectories and an optional template-grounded LLM endpoint (with deterministic fallback) to format computed pixel metrics into plain-language Evidence Cards. All SAR backscatter math, Otsu thresholding, double-bounce filtering, and area metrics are 100% deterministic.
- **Human Authorship & Accountability:** Every line of code and scientific threshold was reviewed, tested, and committed exclusively by the 6 registered human team members from their personal GitHub accounts.
```