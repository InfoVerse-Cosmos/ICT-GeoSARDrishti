# GitHub & Commit Guide — Handbook Section 4 Compliance

This guide covers the **first commit**, the **hourly-push discipline**, and the **no-AI-author** rule. Every member runs git from their **own** account.

---

## Handbook rules this enforces (Section 4 & 5)

- New **public** repo created **after 12:00 PM, 14 Nov 2026**. ✅ confirm the repo was created in-window.
- **Hourly pushes** from 12:00 PM 14 Nov → 2:00 PM 15 Nov, including overnight. Each push = genuine incremental work.
- **Every member** appears in GitHub → Insights → Contributors, pushing from their own personal account.
- **No AI / bot contributors** — no Copilot/Claude/ChatGPT co-author tags, no automated commit scripts.
- **Live URL** at the top of `README.md` if deployed.
- **Hard freeze** — no commits/merges/edits after 2:00 PM, 15 Nov 2026.

> **Team size:** our 6-member roster is approved (NASA Space Apps portal allows it and the Nagpur organisers confirmed our registration).

---

## What the first commit contains (Phase 0 scaffold)

The initial push lands the project skeleton — structure and boilerplate only; the real SAR science is built in Phases 1–2.

- `apps/web/` — Vite + React (JS/JSX) + MapLibre + Tailwind telemetry UI shell (7 components, Zustand store, envelope-safe API client, offline fallback manifest).
- `services/api/` — FastAPI server: `/health`, `/aois`, `/timeline`, `/nisar/earthdata-live`, `/layers`, `/inspect`, `/evidence-card`, `/exposure`, `/provenance`; standard response envelope; global exception handler; Dockerfile.
- `services/api/data_store/` — seed AOI manifests for Majuli–Kaziranga and Kanhan–Pench (dates/granule IDs marked `TBD` until the Phase 1 data gate locks them).
- `scripts/` — offline NISAR data gate + SAR classify/hydroperiod + GMM/validation + OSM exposure (scaffolds with the dB/threshold math wired).
- `Docs/` — SRS + phase-by-phase implementation plan + this guide.
- `README.md`, `.env.example`, `.gitignore`.

---

## First commit — step by step (run from your own account)

From the repository root (`ICT-GeoSARDrishti/`):

```bash
# 0. Verify YOUR identity matches your GitHub account (critical — Section 4)
git config user.name "Pravin Tawade"
git config user.email "<your-github-noreply-or-account-email>"

# 1. Initialise and connect to the fresh public repo
git init -b main
git remote add origin https://github.com/InfoVerse-Cosmos/ICT-GeoSARDrishti.git

# 2. Review what will be committed (node_modules/.env/__pycache__ are already .gitignored)
git status

# 3. Stage and commit (NO AI co-author trailer — do not add Co-authored-by: for any AI tool)
git add .
git commit -m "chore: scaffold GeoSAR Drishti monorepo (Phase 0)

- apps/web: React JS + MapLibre + Tailwind telemetry UI shell
- services/api: FastAPI endpoints with standard envelope + graceful fallbacks
- scripts: offline NISAR data gate, SAR classify/hydroperiod, GMM/validation, OSM exposure (scaffolds)
- data_store: seed AOI manifests (Majuli-Kaziranga, Kanhan-Pench)
- Docs: SRS + phase-by-phase implementation plan
- README (handbook 6-section structure), .env.example, .gitignore"

# 4. Push
git push -u origin main
```

**Verify after pushing:**
```bash
git log --pretty=fuller -1     # Author AND Committer must be YOU, not any AI/bot
```

---

## Suggested first human commit per member (within the first hour)

So all members appear in Contributors early, each makes a genuine small commit in their own area:

| Member | First real commit idea |
| :-- | :-- |
| Pravin `@cosmosinfoverse` | Phase 0 scaffold push + lock SAR threshold constants in `scripts/02` |
| Himanshu `@lunar_node` | Fill real locked granule IDs/dates into `data_store/*/manifest.json` (Phase 1 data gate) |
| Kaushik `@kaushik7` | Backend: wire a real `/timeline` from the locked manifest + deploy staging API |
| Sharv `@shardstax` | Frontend: top mission bar + dual-AOI switch + time-slider gap band polish |
| Sakshi `@sakshitayade` | Add ESA WorldCover / JRC / OSM clip configs + `scripts/03` feature-vector build |
| Prashan `@prashan_arya` | Evidence-card templates + error-wrapper tests + hourly-push tracker note |

---

## Hourly-push discipline (overnight included)

- Commit small, meaningful increments every hour; push immediately.
- Never batch a whole feature into one 3 a.m. push — split it.
- If stuck, push WIP (docs, tests, config) so the hourly cadence holds.
- Keep laptops charged for the 2–3 min power switchovers; `git push` after every working change.

## Conventional commit prefixes (keep history readable)

`feat:` new capability · `fix:` bug fix · `chore:` scaffold/config · `docs:` documentation · `refactor:` restructure · `data:` data pack update · `style:` UI styling.
