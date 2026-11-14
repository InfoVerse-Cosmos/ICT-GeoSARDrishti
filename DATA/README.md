# 📂 DATA — drop your NISAR granules here

This is the folder where **you** put the satellite data you want to analyse. Nothing
else to configure: put files here, run one command, open the app.

## What to put here

NISAR **L2 GCOV** radar granules — the `.h5` files — for the area and monsoon window
you care about. Download them yourself (it is your responsibility to obtain the data)
from either source; both distribute the same NISAR GCOV product:

- **NASA Earthdata / ASF** — <https://search.earthdata.nasa.gov/> (collections
  `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GCOV_V1`)
- **ISRO Bhoonidhi** — <https://bhoonidhi.nrsc.gov.in/>

Just copy the `.h5` files into this folder. You do **not** need to unzip, rename, or
pre-process anything.

```
DATA/
├── README.md                 (this file — kept in the repo)
├── NISAR_L2_..._001.h5        (your granules — ignored by git, never uploaded)
└── NISAR_L2_..._002.h5
```

## Then run

From the repo root:

```bash
./analyze.sh        # macOS / Linux
analyze.bat         # Windows
```

It reads the granules here, **auto-detects the area** from them, builds the analysis
pack, and starts the app at <http://localhost:5173>. Your area appears in the top-bar
selector — open the **Analysis Report** for a plain-language summary.

## Short on disk space?

Granules are ~7 GB each. You can keep them on another drive and tell the app where in
`services/api/.env` (see `.env.example`):

```
GEOSAR_DATA_DIR=D:/Hackathon Files      # where your .h5 files are
GEOSAR_DATA_STORE=D:/geosar_packs       # where the analysed results are written
```

The app lists **only** areas you have analysed. Nothing is pre-loaded, cached in the
repo, or simulated: no data analysed = an empty screen telling you what to do.

## Notes

- Your `.h5` files are large and stay **only on your machine** — git ignores them, so
  they are never committed or uploaded.
- For a usable time series, use granules from the **same track/frame** across several
  dates; the pipeline automatically picks the longest same-track stack it finds.
- **Honest framing:** results are a radar-derived surface/canopy-water indication for
  field inspection — not a confirmed flood, depth, or damage claim. Hydroperiod is
  reported as *M of N valid NISAR observations*, never "days flooded".
