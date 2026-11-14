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

Easiest: drop your .h5 granules in the repo-root DATA/ folder and run ./analyze.sh
(it calls this script with sensible defaults). Or call it directly:

Examples
--------
  # Zero-config: read DATA/, auto-detect the area from the granule footprints
  python scripts/byod_build_aoi.py

  # Explicit id / name / area / folder (all optional)
  python scripts/byod_build_aoi.py \
      --aoi-id aoi_my_delta --name "My River Delta" \
      --bbox 68.95,23.44,74.1,26.18 --h5-dir ~/nisar_granules

  # With GMM regimes and a local OSM extract for the inspection log
  python scripts/byod_build_aoi.py --aoi-id aoi_my_delta --name "My Delta" \
      --with-regimes --osm-file ~/my_area_osm.geojson
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline import common, envcfg, process  # noqa: E402

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


def _footprint_bbox(path):
    """Granule boundingPolygon -> [west,south,east,north], or None.

    NISAR WKT is 3D ("POLYGON ((lon lat height, ...))"), so each vertex has three
    numbers; take the first two per vertex (lon, lat) and ignore the height.
    """
    import h5py

    from geosar_pipeline import gcov

    with h5py.File(path, "r") as f:
        ident = gcov.read_identification(f)
    wkt = (ident or {}).get("boundingPolygon", "") or ""
    if "((" not in wkt or "))" not in wkt:
        return None
    body = wkt[wkt.index("((") + 2:wkt.rindex("))")]
    lons, lats = [], []
    for vertex in body.split(","):
        parts = vertex.split()
        if len(parts) >= 2:
            try:
                lons.append(float(parts[0]))
                lats.append(float(parts[1]))
            except ValueError:
                continue
    if not lons:
        return None
    return [min(lons), min(lats), max(lons), max(lats)]


def autodetect_bbox(h5_files):
    """Union of the granule boundingPolygon footprints -> [west,south,east,north], or None."""
    boxes = []
    for path in h5_files:
        try:
            fp = _footprint_bbox(path)
        except Exception as exc:  # noqa: BLE001 - a bad granule should not abort auto-detection
            print(f"[byod] warning: could not read footprint of {path.name}: {exc}")
            fp = None
        if fp:
            boxes.append(fp)
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def default_name(aoi_id: str) -> str:
    base = aoi_id[4:] if aoi_id.startswith("aoi_") else aoi_id
    return base.replace("_", " ").title() or aoi_id


def auto_res_m(bounds, floor_m=100.0, max_dim=1400, max_px=1_600_000):
    """Pick a grid resolution from the AOI size: fine (down to ~100 m) for small areas,
    coarser for large ones, so the pack stays light and the build stays fast for any AOI."""
    res = floor_m
    for _ in range(40):
        rows, cols, _, _ = common.aoi_grid(bounds, res)
        if rows <= max_dim and cols <= max_dim and rows * cols <= max_px:
            return float(round(res))
        res *= 1.5
    return float(round(res))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi-id", default=None,
                   help="pack id, lowercase a-z0-9_ (default: one pack per track/frame, ids chosen automatically)")
    p.add_argument("--name", help="human-readable AOI name shown in the app selector (default: from --aoi-id)")
    p.add_argument("--bbox", type=parse_bbox,
                   help="west,south,east,north (WGS84); default: auto-detected from the granule footprints")
    p.add_argument("--h5-dir", default=envcfg.get("GEOSAR_DATA_DIR") or str(common.REPO_ROOT / "DATA"),
                   help="folder holding your NISAR GCOV .h5 granules (default: GEOSAR_DATA_DIR from .env, else the repo-root DATA/ folder)")
    p.add_argument("--track-frame", help="force a track/frame (default: longest same-track stack)")
    p.add_argument("--ref-date", help="dry reference date YYYY-MM-DD (default: latest acquisition)")
    p.add_argument("--res-m", type=float, default=None,
                   help="output grid resolution in metres (default: auto — finer for small areas, "
                        "coarser for large, to keep the pack light)")
    p.add_argument("--default-zoom", type=int, default=8, help="initial map zoom for this AOI")
    p.add_argument("--worldcover", help="ESA WorldCover GeoTIFF (vegetation mask + paddy sub-label)")
    p.add_argument("--dem", help="Copernicus DEM GeoTIFF (slope > 5 deg mask)")
    p.add_argument("--with-regimes", action="store_true", help="also run stage 03 GMM regimes (needs scikit-learn)")
    p.add_argument("--jrc", help="JRC Global Surface Water occurrence GeoTIFF (stage 03)")
    p.add_argument("--dswx", help="OPERA DSWx GeoTIFF for inter-sensor agreement (stage 03)")
    p.add_argument("--dswx-date", help="DSWx acquisition date to compare against")
    p.add_argument("--osm-file", help="local OSM extract (GeoJSON/GPKG) for stage 04 exposure, offline-safe")
    p.add_argument("--with-osm", action="store_true", help="fetch OSM live via osmnx for stage 04 exposure")
    p.add_argument("--min-wet", type=int, default=None,
                   help="min wet observations for an inspection candidate (default: 2 for short stacks of <6 dates, else 3)")
    p.add_argument("--data-store", help="override data_store dir (default services/api/data_store)")
    args = p.parse_args()

    if args.aoi_id and not AOI_ID_RE.match(args.aoi_id):
        p.error("--aoi-id must contain only lowercase letters, digits and underscores")

    store = common.data_store(args.data_store)
    h5_dir = Path(args.h5_dir).expanduser()
    if not h5_dir.is_dir():
        p.error(
            f"granule folder not found: {h5_dir}\n"
            "       Put your NISAR L2 GCOV .h5 granules in the repo-root DATA/ folder "
            "(or set GEOSAR_DATA_DIR in services/api/.env, or pass --h5-dir). See DATA/README.md."
        )
    h5_files = sorted(h5_dir.glob("*.h5"))
    if not h5_files:
        p.error(
            f"no NISAR .h5 granules found in {h5_dir}\n"
            "       Download NISAR L2 GCOV granules for your area from NASA Earthdata/ASF or "
            "ISRO Bhoonidhi (your responsibility), drop the .h5 files into DATA/, and run again."
        )

    # One folder may hold several areas (different track/frame). Without an explicit --aoi-id /
    # --track-frame we build ONE pack per track/frame stack, so areas are never mixed together.
    by_tf = {}
    for f in h5_files:
        g = common.parse_granule_name(f.name)
        if g:
            by_tf.setdefault(g["track_frame"], []).append(f)
    if not by_tf:
        p.error(f"none of the .h5 files in {h5_dir} look like NISAR L2 GCOV products")
    if args.aoi_id or args.track_frame:
        jobs = [(args.aoi_id or "aoi_my_data", args.name, args.bbox, args.track_frame, h5_files)]
    else:
        jobs = []
        for tf, files in sorted(by_tf.items()):
            fp = autodetect_bbox(files)
            known = common.match_known_area(fp) if fp else None
            if known:
                aoi_id, name = known, common.KNOWN_AREAS[known]["name"]
                bbox = args.bbox or common.KNOWN_AREAS[known]["bounds"]
            else:
                aoi_id, name, bbox = auto_identity(tf, fp), None, args.bbox or fp
            jobs.append((aoi_id, args.name if len(by_tf) == 1 and args.name else name, bbox, tf, files))
        print(f"[byod] {len(h5_files)} granule(s), {len(jobs)} area(s) found: "
              + ", ".join(f"{j[0]} (track/frame {j[3]}, {len(j[4])} files)" for j in jobs))

    failures = 0
    for aoi_id, name, bbox, tf, files in jobs:
        try:
            build_pack(args, store, h5_dir, files, aoi_id, name, bbox, tf)
        except Exception as exc:  # noqa: BLE001 - one bad area must not stop the others
            failures += 1
            print(f"[byod] ERROR building {aoi_id}: {exc}")

    try:
        from geosar_pipeline import mirror
        mirror.run(store)  # offline mirror lists only the AOIs really analysed here
    except Exception as exc:  # noqa: BLE001 - the mirror is a convenience, never fatal
        print(f"[byod] offline mirror not refreshed: {exc}")
    print("\n[byod] done. Results are a radar-derived surface/canopy-water indication for inspection, "
          "not a confirmed flood or damage claim.")
    return 1 if failures == len(jobs) else 0


def auto_identity(track_frame, fp):
    """Stable id for an unknown area from its footprint centre, e.g. aoi_n26_9_e94_1."""
    if not fp:
        return "aoi_t" + (track_frame or "x").replace("/", "_")
    lat, lon = (fp[1] + fp[3]) / 2, (fp[0] + fp[2]) / 2
    return "aoi_%s%d_%d_%s%d_%d" % ("n" if lat >= 0 else "s", abs(lat), int(abs(lat) % 1 * 10),
                                    "e" if lon >= 0 else "w", abs(lon), int(abs(lon) % 1 * 10))


def build_pack(args, store, h5_dir, h5_files, aoi_id, name, bbox, track_frame):
    """Build one area's pack (stages 02-04) from the given granule stack."""
    if bbox is None:
        bbox = autodetect_bbox(h5_files)
    if bbox is None:
        raise RuntimeError("could not auto-detect an AOI from the granule footprints; "
                           "pass one explicitly with --bbox west,south,east,north")
    known = common.KNOWN_AREAS.get(aoi_id, {})
    name = name or known.get("name") or default_name(aoi_id)
    print(f"[byod] ===== {aoi_id} '{name}' bbox={bbox} track/frame={track_frame or 'auto'}")

    res_m = args.res_m if args.res_m else (100.0 if known else auto_res_m(bbox))
    print(f"[byod] grid resolution: {res_m:.0f} m")

    # Register the AOI bounds so the pipeline's footprint gate (which keys on AOI_BOUNDS)
    # accepts this bring-your-own AOI, then seed the manifest the pipeline reads.
    common.AOI_BOUNDS[aoi_id] = bbox
    manifest = common.load_manifest(aoi_id, store)
    manifest.update({
        "aoi_id": aoi_id,
        "name": name,
        "bounds": bbox,
        "default_zoom": known.get("zoom", args.default_zoom),
    })
    if known.get("role"):
        manifest["role"] = known["role"]
    common.save_manifest(aoi_id, store, manifest)

    # ---- stage 02: classify + hydroperiod (required) --------------------------------
    manifest = process.run(aoi_id, h5_dir, store, track_frame=track_frame or args.track_frame,
                           ref_date=args.ref_date, res_m=res_m, worldcover=args.worldcover, dem=args.dem)
    print(f"[byod] stage 02 done - plan {manifest.get('fallback_plan')} - "
          f"{len(manifest.get('timeline', []))} dates - track {manifest.get('track_frame')}")
    for t in manifest.get("timeline", []):
        mt = t.get("metrics", {})
        print(f"        {t['date']} {t.get('maturity','?'):<11} "
              f"open={mt.get('open_water_km2','?')} km2  fveg={mt.get('flooded_veg_km2','?')} km2")

    # ---- stage 03: GMM regimes (+ optional JRC / DSWx) ------------------------------
    if args.with_regimes or args.jrc or args.dswx:
        try:
            from geosar_pipeline import regimes
            regimes.run(aoi_id, store, jrc=args.jrc, dswx=args.dswx, dswx_date=args.dswx_date)
            print("[byod] stage 03 done - GMM regimes written")
        except ImportError as exc:
            print(f"[byod] stage 03 skipped (install scikit-learn/rasterio): {exc}")

    # ---- stage 04: OSM exposure (optional) ------------------------------------------
    if args.osm_file or args.with_osm:
        try:
            from geosar_pipeline import exposure
            n_dates = len(manifest.get("timeline", []))
            min_wet = args.min_wet or (2 if n_dates < 6 else common.MIN_WET_OBSERVATIONS)
            exposure.run(aoi_id, store, osm_file=args.osm_file, min_wet=min_wet)
            print("[byod] stage 04 done - OSM inspection candidates written")
        except Exception as exc:  # noqa: BLE001 - offline / Overpass busy must not lose the water maps
            print(f"[byod] stage 04 skipped (needs geopandas/osmnx + internet, or --osm-file): {exc}")
    else:
        print("[byod] stage 04 skipped (no --osm-file / --with-osm) - inspection log left empty")
    print(f"[byod] pack ready: {store / aoi_id}")


if __name__ == "__main__":
    raise SystemExit(main())
