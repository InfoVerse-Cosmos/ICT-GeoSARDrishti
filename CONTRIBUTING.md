# Contributing — GeoSAR Drishti (Cosmos InfoVerse Techky)

This is our working agreement for the 48-hour sprint (14–15 Nov 2026). It keeps us
inside the NASA Space Apps Nagpur handbook rules and keeps the history clean for judging.

---

## The golden rules (don't break these)

1. **Push from your own GitHub account.** Your `git config user.email` must be the email on your
   personal GitHub. Check it before your first push.
2. **At least one genuine push every hour**, 12:00 PM 14 Nov → 2:00 PM 15 Nov, overnight included.
3. **No AI as author or co-author.** Never add a `Co-authored-by:` trailer for Copilot/Claude/ChatGPT,
   and never let a bot/script push. AI help is fine and disclosed in the README — it just never signs a commit.
4. **Nothing after the 2:00 PM freeze on 15 Nov.** No commits, merges, or edits.
5. Keep your laptop charged — the venue has 2–3 min power switchovers. Save and push often.

> Team size: 6 members is approved for us (NASA Space Apps portal allows it and the organisers
> confirmed our registration). Everyone must still show up in GitHub → Insights → Contributors.

---

## Hourly commit checklist

Run through this at the top of every hour (set a phone alarm):

- [ ] Is my `git config user.email` my own GitHub email? (`git config user.email`)
- [ ] Did I do real, incremental work since my last push? (not a whitespace commit)
- [ ] `git status` — am I staging only what I mean to? (no `.env`, no `node_modules`, no data dumps)
- [ ] Clear commit message with a type prefix (see below)?
- [ ] No AI co-author trailer anywhere?
- [ ] `git pull --rebase` so I'm on top of the latest, then `git push`.
- [ ] After push: `git log --pretty=fuller -1` — Author **and** Committer are me?
- [ ] Still blocked with nothing to show? Push WIP docs/tests/config so the hourly cadence holds.

---

## Who owns what

| Member | Area |
| :-- | :-- |
| Pravin `@cosmosinfoverse` | Architecture, SAR physics thresholds, review |
| Kaushik `@kaushik7` | `services/api` backend, earthaccess, raster processing |
| Sharv `@shardstax` | `apps/web` UI, MapLibre, time slider |
| Himanshu `@lunar_node` | NISAR data gate, maturity/calibration, OPERA/JRC validation |
| Sakshi `@sakshitayade` | GMM regimes, WorldCover, OSM exposure, Nagpur context |
| Prashan `@prashan_arya` | Evidence cards, error/fallback QA, hourly-push tracking |

Work in your own area to avoid stepping on each other. If you must touch a shared file
(`manifest.json`, store, API client), shout in the team chat first and rebase before pushing.

---

## Branching

Keep it simple for a 48-hour event:

- `main` is always deployable. Small changes go straight to `main`.
- For anything bigger or risky, branch `feature/<short-name>`, open a quick PR, get one teammate to glance at it, merge.
- Rebase on `main` before merging so history stays linear and readable.

## Commit message style

Short summary line (what changed, in plain words), optional body for the why. Use a prefix:

- `feat:` new capability — `feat: pixel click returns HH/HV dB trajectory`
- `fix:` bug fix — `fix: stop 500 when click lands outside the AOI box`
- `chore:` setup/config — `chore: add render deploy config`
- `docs:` documentation — `docs: fill granule IDs in provenance`
- `data:` data pack update — `data: add Majuli hydroperiod overlays`
- `refactor:` / `style:` — restructure / UI polish

Write like a human explaining it to a teammate, not a changelog robot.

## Before the freeze (Phase 4 checklist)

- [ ] Live URL pinned at the top of `README.md`
- [ ] All 6 members visible in Contributors
- [ ] `git log` has zero AI/bot authors or co-authors
- [ ] All six README sections complete + screenshots added
- [ ] Data citations + AI disclosure present
- [ ] Final commit pushed **before** 2:00 PM, 15 Nov 2026
