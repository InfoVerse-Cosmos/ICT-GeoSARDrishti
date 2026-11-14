# Commit Storyline (for the judges' overview)

A suggested run of commits across the 48 hours. Read top to bottom, it tells the
story of how we built GeoSAR Drishti. These are written to sound like us, not a
changelog bot. Keep the hourly cadence — add more small ones between these as you go.

> Each line is: `author handle` — the commit message. Use the message after the `—`.
> Don't paste the `(why)` notes into git; they're just reminders of what that commit should actually contain.

---

## Phase 1 — Data gate & scaffold (Sat 12:00 PM – 4:00 PM)

- `@cosmosinfoverse` — **chore: scaffold the GeoSAR Drishti monorepo so the team can start**
  _(why: the Phase 0 skeleton — apps/web, services/api, scripts, docs)_
- `@cosmosinfoverse` — **docs: lock our SAR thresholds (ΔHH ≥ +3 dB, Otsu −22 to −13 dB) in one place**
- `@lunar_node` — **feat: query ASF/CMR for the Majuli same-track GCOV granules**
- `@lunar_node` — **data: lock the Majuli granule list and write real dates into the manifest**
  _(why: replaces the TBD placeholders with actual acquisition dates + maturity)_
- `@kaushik7` — **feat: FastAPI boots with /health and /aois, CORS on**
- `@kaushik7` — **chore: deploy the API to Render staging so the frontend has something to hit**
- `@shardstax` — **feat: React shell with the NASA–ISRO dark telemetry theme**
- `@shardstax` — **feat: dual-AOI switcher in the top mission bar**
- `@sakshitayade` — **data: clip ESA WorldCover and JRC occurrence to both AOI boxes**
- `@sakshitayade` — **data: pull OSM roads and villages for Majuli with osmnx**
- `@prashan_arya` — **feat: deterministic evidence-card templates (no made-up numbers)**
- `@prashan_arya` — **chore: wrap every endpoint in the standard envelope so the UI never breaks**

## Phase 2 — SAR pipeline & wiring (Sat 4:00 PM – 11:00 PM)

- `@kaushik7` — **feat: subset HH/HV to the AOI and convert to dB (ratio = HH − HV, done right)**
- `@lunar_node` — **feat: per-date Otsu open-water + ΔHH double-bounce classifier**
- `@kaushik7` — **feat: build the M-of-N hydroperiod stack across the season**
- `@kaushik7` — **data: export RGBA overlays and the pixel time-series cube for Majuli**
- `@shardstax` — **feat: MapLibre overlays + layer toggles wired to the API**
- `@shardstax` — **feat: click a pixel, get its HH/HV dB trajectory on the chart**
- `@prashan_arya` — **feat: evidence card now explains the double-bounce in plain language**
- `@sakshitayade` — **feat: 5-cluster GMM on pixel backscatter, mapped to our hydrological regimes**
- `@sakshitayade` — **feat: OPERA DSWx inter-sensor agreement + JRC "unusual water" flag**
- `@sakshitayade` — **feat: OSM exposure log — roads/villages wet on 3+ dates**
- `@shardstax` — **feat: monsoon time slider with the 27 Jul–10 Aug acquisition gap band**
- `@cosmosinfoverse` — **fix: handle clicks outside the AOI without blowing up (outside_aoi)**

## Phase 3 — Nagpur, deploy, resilience (Sat 11:00 PM – Sun 9:00 AM)

- `@sakshitayade` — **feat: add the Nagpur Kanhan–Pench AOI with GSDA/CGWB watershed context**
- `@sakshitayade` — **docs: label groundwater as official context, not SAR detection**
- `@kaushik7` — **feat: live Earthdata endpoint with a 4s timeout and cached fallback**
- `@shardstax` — **feat: "establishing uplink" banner + retry for backend cold starts**
- `@shardstax` — **feat: bundle a static manifest so the map survives a venue wifi drop**
- `@kaushik7` — **chore: production deploy of the API**
- `@shardstax` — **chore: deploy the frontend and point it at the live API**
- `@prashan_arya` — **fix: a few null-safety spots so nothing renders undefined**
- `@lunar_node` — **data: lock the Nagpur granule list and fill its manifest**

## Phase 4 — Verify, polish, freeze (Sun 9:00 AM – 2:00 PM)

- `@cosmosinfoverse` — **docs: finish the README (live URL, architecture, citations)**
- `@prashan_arya` — **docs: AI usage disclosure with the component-level breakdown**
- `@lunar_node` — **docs: fill provenance — granule IDs, Otsu thresholds, DSWx agreement %**
- `@shardstax` — **docs: add interface screenshots to the README**
- `@cosmosinfoverse` — **chore: final pass before the 2 PM freeze — everything green**

---

### Tips so this reads as genuine to the judges
- Commit the actual work described, in that order — don't write ahead of the code.
- Spread real hourly commits between these; small `fix:`/`style:`/`docs:` ones are fine.
- Each member should author their own section from their own machine/account.
- Keep messages in your own voice. If you'd say it differently to a teammate, say it that way.
