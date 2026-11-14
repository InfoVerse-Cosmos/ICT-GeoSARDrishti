"""BYOD — build a GeoSAR Drishti data pack from YOUR OWN NISAR GCOV granules.

One command wraps the team's offline pipeline (scripts/geosar_pipeline, the same
code that produced the Gujarat pack) so anyone can clone the repo, point it at a
folder of NISAR L2 GCOV .h5 granules and an AOI bounding box, and get a pack the
web app serves end-to-end.

Stages it runs (SRS §5):
  02  subset + speckle filter + dB + dynamic Otsu + 3-class classifier + M-of-N
      hydroperiod  -> time_series_cube.npz, overlays/*.png, manifest.json
  03  (optional) unsupervised GMM hydrological regimes (+ JRC / OPERA DSWx if GeoTIFFs given)
  04  (optional) OSM roads/settlements x hydroperiod -> ground-inspection candidates

The pack is written to  services/api/data_store/<aoi-id>/  (override with --data-store).
Restart the backend (or it reloads on next request) and the AOI shows up in the app.

Honest framing (project rule): every output is a radar-derived surface/canopy-water
indication for inspection — not a confirmed flood, depth, or damage claim. Hydroperiod
is "M of N valid NISAR observations", never "days flooded".

Prerequisites:  pip install -r scripts/requirements.txt   (needs numpy, h5py, pyproj;
GMM needs scikit-learn; OSM exposure needs geopandas/osmnx/shapely).

Examples
--------
  # Minimal: classify + hydroperiod only
  python scripts/byod_build_aoi.py \
      --aoi-id aoi_my_delta --name "My River Delta" \
      --bbox 68.95,23.44,74.1,26.18 --h5-dir ~/nisar_granules

  # With GMM regimes and a local OSM extract for the inspection log
  python scripts/byod_build_aoi.py --aoi-id aoi_my_delta --name "My Delta" \
      --bbox 68.95,23.44,74.1,26.18 --h5-dir ~/nisar_granules \
      --with-regimes --osm-file ~/my_area_osm.geojson
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline import common, process  # noqa: E402

AOI_ID_RE = re.compile(r"^[a-z0-9_]+$")  # must match services/api layers router _AOI_RE


def parse_bbox(text: str) -> list[float]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--bbox must be 'west,south,east,north'")
    try:
        w, s, e, n = (float(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--bbox values must be numbers: {exc}")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise argparse.ArgumentTypeError("--bbox must satisfy west<east, south<north and be valid WGS84")
    return [w, s, e, n]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi-id", required=True, help="pack id, lowercase a-z0-9_ (e.g. aoi_my_delta)")
    p.add_argument("--name", help="human-readable AOI name (shown in the app selector)")
    p.add_argument("--bbox", required=True, type=parse_bbox, help="west,south,east,north (WGS84)")
    p.add_argument("--h5-dir", required=True, help="folder holding your NISAR GCOV .h5 granules")
    p.add_argument("--track-frame", help="force a track/frame (default: longest same-track stack)")
    p.add_argument("--ref-date", help="dry reference date YYYY-MM-DD (default: latest acquisition)")
    p.add_argument("--res-m", type=float, default=100.0, help="output grid resolution in metres (default 100)")
    p.add_argument("--default-zoom", type=int, default=8, help="initial map zoom for this AOI")
    p.add_argument("--worldcover", help="ESA WorldCover GeoTIFF (vegetation mask + paddy sub-label)")
    p.add_argument("--dem", help="Copernicus DEM GeoTIFF (slope > 5 deg mask)")
    p.add_argument("--with-regimes", action="store_true", help="also run stage 03 GMM regimes (needs scikit-learn)")
    p.add_argument("--jrc", help="JRC Global Surface Water occurrence GeoTIFF (stage 03)")
    p.add_argument("--dswx", help="OPERA DSWx GeoTIFF for inter-sensor agreement (stage 03)")
    p.add_argument("--dswx-date", help="DSWx acquisition date to compare against")
    p.add_argument("--osm-file", help="local OSM extract (GeoJSON/GPKG) for stage 04 exposure, offline-safe")
    p.add_argument("--with-osm", action="store_true", help="fetch OSM live via osmnx for stage 04 exposure")
    p.add_argument("--min-wet", type=int, default=common.MIN_WET_OBSERVATIONS,
                   help="minimum wet observations for an inspection candidate (default 3)")
    p.add_argument("--data-store", help="override data_store dir (default services/api/data_store)")
    args = p.parse_args()

    aoi_id = args.aoi_id
    if not AOI_ID_RE.match(aoi_id):
        p.error("--aoi-id must contain only lowercase letters, digits and underscores")

    store = common.data_store(args.data_store)
    h5_dir = Path(args.h5_dir).expanduser()
    if not h5_dir.is_dir():
        p.error(f"--h5-dir not found: {h5_dir}")

    # Register the AOI bounds so the pipeline's footprint gate (which keys on AOI_BOUNDS)
    # accepts this bring-your-own AOI, then seed the manifest the pipeline reads.
    common.AOI_BOUNDS[aoi_id] = args.bbox
    manifest = common.load_manifest(aoi_id, store)
    manifest.update({
        "aoi_id": aoi_id,
        "name": args.name or aoi_id,
        "bounds": args.bbox,
        "default_zoom": args.default_zoom,
    })
    common.save_manifest(aoi_id, store, manifest)

    print(f"[byod] AOI {aoi_id} '{manifest['name']}' bbox={args.bbox} -> {store}")

    # ---- stage 02: classify + hydroperiod (required) --------------------------------
    manifest = process.run(aoi_id, h5_dir, store, track_frame=args.track_frame, ref_date=args.ref_date,
                           res_m=args.res_m, worldcover=args.worldcover, dem=args.dem)
    print(f"[byod] stage 02 done · plan {manifest.get('fallback_plan')} · "
          f"{len(manifest.get('timeline', []))} dates · track {manifest.get('track_frame')}")
    for t in manifest.get("timeline", []):
        mt = t.get("metrics", {})
        print(f"        {t['date']} {t.get('maturity','?'):<11} "
              f"open={mt.get('open_water_km2','?')} km²  fveg={mt.get('flooded_veg_km2','?')} km²")

    # ---- stage 03: GMM regimes (+ optional JRC / DSWx) ------------------------------
    if args.with_regimes or args.jrc or args.dswx:
        try:
            from geosar_pipeline import regimes
            regimes.run(aoi_id, store, jrc=args.jrc, dswx=args.dswx, dswx_date=args.dswx_date)
            print("[byod] stage 03 done · GMM regimes written")
        except ImportError as exc:
            print(f"[byod] stage 03 skipped (install scikit-learn/rasterio): {exc}")

    # ---- stage 04: OSM exposure (optional) ------------------------------------------
    if args.osm_file or args.with_osm:
        try:
            from geosar_pipeline import exposure
            exposure.run(aoi_id, store, osm_file=args.osm_file, min_wet=args.min_wet)
            print("[byod] stage 04 done · OSM inspection candidates written")
        except ImportError as exc:
            print(f"[byod] stage 04 skipped (install geopandas/osmnx/shapely): {exc}")
    else:
        print("[byod] stage 04 skipped (no --osm-file / --with-osm) — inspection log left empty")

    print(f"\n[byod] pack ready: {store / aoi_id}")
    print("[byod] next: restart the API (uvicorn) or let it reload — the AOI appears in the app selector,")
    print("[byod] and the one-click Analysis Report will summarise it. Results are a radar-derived")
    print("[byod] surface/canopy-water indication for inspection, not a confirmed flood or damage claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
