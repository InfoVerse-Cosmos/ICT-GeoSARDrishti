# GeoSAR Drishti: User Guide

How to set the app up, use it, and test it by hand. Plain steps, no jargon.

**What it does.** It shows where water spread and how long it stayed during the monsoon, using radar data from the NASA-ISRO NISAR satellite. Radar sees through clouds, so it works when normal satellite photos cannot. It also lists roads and villages worth inspecting first.

> **Important.** Everything on screen is a *radar-based water indication for inspection*. It is not a confirmed flood, a water depth or a damage report.

---

## 1. Set up (once)

You need: **Python 3.11 or newer**, **Node 18 or newer**, and **git**.

```bash
git clone https://github.com/InfoVerse-Cosmos/ICT-GeoSARDrishti.git
cd ICT-GeoSARDrishti
```

### Optional keys (a private file)

The first run creates `services/api/.env` for you. Open it and fill in what you want. **This file is never uploaded to GitHub.**

| Setting | What it gives you | Needed? |
|---|---|---|
| `EARTHDATA_TOKEN` | Lets the app fetch any place from NASA (the **New area** button). Get a free token at <https://urs.earthdata.nasa.gov> then **Generate Token**. | Only for **New area** |
| `LLM_API_KEY` | An OpenAI key. The app then writes a short plain-words explanation for a clicked spot. | No (a built-in explanation is used without it) |
| `GEOSAR_DATA_DIR` | A folder for your big NISAR `.h5` files (default: the `DATA/` folder). | No |
| `GEOSAR_DATA_STORE` | A folder for the finished results (default: inside the repo). Handy for another drive, e.g. `D:/geosar_packs`. | No |

Use `/` in paths, even on Windows.

---

## 2. Start the app

The app starts empty. **Nothing is pre-loaded.** Pick the way that matches what you have.

### A. You have NISAR `.h5` files
1. Put the files in the `DATA/` folder (or the folder you set in `GEOSAR_DATA_DIR`).
2. Run **one** file:
   - Windows: `analyze.bat`
   - Mac / Linux: `./analyze.sh`
3. Wait (about 10-15 minutes for a few large files). It installs what it needs, analyses every area it finds, then starts the app.

### B. You have no files (stream from NASA)
1. Put your `EARTHDATA_TOKEN` in `services/api/.env`.
2. Start the app: `run.bat` (Windows) or `./run.sh` (Mac / Linux).
3. Open the map and use **＋ New area** (see section 4).

### C. You already analysed your data
Just run `run.bat` / `./run.sh`. Nothing is reprocessed.

Open the address the terminal shows. Normally: **http://localhost:5173**. If that port is busy, Vite prints another one. The map page itself is `http://localhost:5173/#/explore`.

---

## 3. Using the app

**Landing page.** Pick **Explore the water story** (or **Launch map**) to open the map. **← Home** brings you back. The sun/moon button switches light and dark.

**Two modes** (top bar, **Simple | Scientific**):

| | Simple (default) | Scientific |
|---|---|---|
| For | Anyone | Experts |
| Layers | Open water, Water hidden under plants, Repeatedly wet areas | Adds Hydroperiod and GMM Regimes |
| Extras | One-line summary, plain explanation of a clicked spot | Red roads and villages to inspect, Before/After slider, opacity, base maps, charts, evidence card, Provenance |

**Basic moves**
- **Pick an area** with the dropdown at the top left.
- **Pick a date** with the chips at the bottom (PROV = early NASA data, VALI = checked data). **PLAY** steps through them. The striped band is a stretch with no satellite pass.
- **Click the map** inside the dashed box to see what the radar found at that spot.
- **📊 Report** gives a plain summary of the area.

### ＋ New area (any place, any dates)
1. Click **＋ New area**.
2. Choose the place, in any of these ways: **search** a name, **Draw on map** (drag a rectangle, or just click), **Use my location**, or type coordinates. A size menu sets the box size for a click.
3. Set **From / To** dates and press **Find available passes**. This is a quick search; nothing is downloaded.
4. **Tick the dates** you want (at least 2). If several satellite tracks cover the place, choose one. Tip: include a late-season date, because the last ticked date is used as the dry reference.
5. Press **Start analysis**. You will see the steps and a "time left" countdown. **Stop** cancels safely.
6. When it finishes, the new area is added to the list and opened.

Limits: each side under about 65 km, up to 400 days, one analysis at a time. Each satellite pass takes roughly 3 minutes. NISAR does not look at every place every 12 days, so some places have few passes. It only works on your own computer, not on a hosted server.

Where files go: finished results in `GEOSAR_DATA_STORE`; small streamed pieces in `DATA/_stream/` (or inside `GEOSAR_DATA_DIR`). Nothing is added to git.

---

## 4. Manual test guide

Do these in order. Each line says what to do and what you should see. Tests marked **(data)** need at least one analysed area.

### Start
| # | Do | You should see |
|---|---|---|
| 1 | Open the app | The landing page, with no errors |
| 2 | **(no data)** Start with an empty results folder | The map page shows "No NISAR data analysed yet" with 3 steps (no fake areas) |
| 3 | Click the sun/moon button | The whole page, including the top bar and the Earth section, switches light and dark |
| 4 | Click **Launch map**, then **← Home** | Map opens; Home returns to the landing page |

### Simple mode (data)
| # | Do | You should see |
|---|---|---|
| 5 | Open the map | Simple mode, a satellite background, a one-line summary ("On <date>, radar indicated X km² of open water"), the Report button visible |
| 6 | Switch the 3 layers | The map and the "You're viewing" text change each time |
| 7 | Click each date chip, then **PLAY** | The summary changes and the map changes; PLAY loops through the dates |
| 8 | Click inside the dashed box | A line like "Water seen in 2 of 3 satellite passes", then (with an OpenAI key) "Writing a plain explanation…" turning into a short paragraph |
| 9 | Click outside the dashed box | "That point is outside the studied area" |
| 10 | Click **📊 Report** | A summary with areas, how long water stayed, what changed and roads to inspect, plus the "not a confirmed flood" note |

### Scientific mode (data)
| # | Do | You should see |
|---|---|---|
| 11 | Switch to **Scientific** | Extra pills (granule, track, polarisation, plan), 4 layers, a base-map row, a **Provenance** button |
| 12 | Tick/untick **Inspection candidates** | Red roads and villages appear and disappear |
| 13 | Choose a date in **Before / After**, move the slider | The map fades between the two dates |
| 14 | Switch the base maps and the opacity | The background and layer strength change |
| 15 | Click the map, open **PIXEL TRAJECTORY** | A chart and a **Radar Evidence Card**; the last line says whether a built-in template or AI wrote the wording |
| 16 | Open **SCENE & VALIDATION** and **INSPECTION LOG** | Area numbers for the date; a list of roads and villages |
| 17 | Click **Provenance** | Satellite files, thresholds and honest limitations |

### New area (needs `EARTHDATA_TOKEN`)
| # | Do | You should see |
|---|---|---|
| 18 | Open **＋ New area** with no token | A clear message about the missing token, and Start is disabled |
| 19 | Type a place name (e.g. Guwahati), press Search, choose a result | The map moves there and an orange dashed rectangle appears |
| 20 | **Draw on map**, then drag a rectangle | The popup returns with the numbers filled in ("Area drawn on the map…") |
| 21 | **Draw on map**, then click once | A standard box around the click; **Esc** cancels |
| 22 | **Use my location** | The browser asks for permission; the box centres on you |
| 23 | Press **Find available passes** | A list of dates with PROV/VALI. Selecting fewer than 2 disables Start. Changing the area or dates clears the list |
| 24 | Tick 2 or more dates, **Start analysis** | Steps and a countdown that falls. Roughly 3 minutes per date |
| 25 | Press **■ Stop analysis** during a run | "Stopped". Nothing half-built appears in the area list |
| 26 | Let one run finish | "Done", and the new area is selected and shows its own dates |
| 27 | Try a box wider than 65 km, or dates in the wrong order | A red message; nothing starts |

### When things go wrong
| # | Do | You should see |
|---|---|---|
| 28 | Stop the backend, refresh the page | An "establishing uplink" banner and an offline note; no crash. It reconnects when the backend returns |
| 29 | Remove `LLM_API_KEY`, click a spot | The built-in explanation still appears; nothing breaks |

### Automated checks (for developers)
```bash
cd services/api && python -m pytest tests -q        # backend
cd apps/web && npx vitest run                       # frontend
python -m pytest scripts/tests -q                   # pipeline (use scripts/.venv from analyze)
```

---

## 5. If something does not work

| Problem | Try this |
|---|---|
| "No NISAR data analysed yet" | Add `.h5` files to `DATA/` and run `analyze`, or stream a place with **New area** |
| Port 5173 is busy | Vite picks another port and prints it. Use that address |
| **New area** says the token is missing | Put `EARTHDATA_TOKEN` in `services/api/.env`, restart the backend |
| "NASA has no granule…" | NISAR did not image that place in those dates. Widen the dates or move the box. NISAR data only exists from 2026 |
| No AI text on a clicked spot | Add `LLM_API_KEY`. Without it the built-in explanation is used. If the key is out of credit, the built-in one is used too |
| Streaming is slow | One pass can take 8-10 minutes on a slow network. Already finished dates are kept, so a rerun is faster |
| Want to start fresh | Delete the area folders in your results folder (`GEOSAR_DATA_STORE`) and the `_stream` folder |