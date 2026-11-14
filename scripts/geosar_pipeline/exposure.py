"""Stage 04 — OSM roads/settlements x hydroperiod -> ground-inspection candidates (SRS §5.5).

INSPECTION CANDIDATES ONLY — never a damage claim.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .common import MIN_WET_OBSERVATIONS, load_manifest, now_iso, save_manifest
from .physics import FLOODED_VEG, OPEN_WATER

SKIP_HIGHWAYS = {"footway", "path", "steps", "cycleway", "pedestrian", "corridor", "bridleway", "elevator"}


def fetch_osm(bounds: list[float]):
    """Roads (highway=*) + settlements (place=village|hamlet|town) via osmnx -> GeoDataFrame."""
    import osmnx as ox
    import pandas as pd

    from .common import WORK_DIR
    ox.settings.cache_folder = str(WORK_DIR / "osm_cache")   # keep HTTP cache out of the repo root

    import time

    west, south, east, north = bounds
    # The public Overpass servers are often at capacity (HTTP 502/429): retry with backoff and
    # fall back to mirror servers instead of failing the whole stage.
    endpoints = [None, "https://overpass.kumi.systems/api", "https://overpass.private.coffee/api"]
    default_url = ox.settings.overpass_url

    def query(tags):
        last = None
        for endpoint in endpoints:
            ox.settings.overpass_url = endpoint or default_url
            for attempt in range(3):
                try:
                    try:
                        return ox.features_from_bbox(bbox=(west, south, east, north), tags=tags)  # osmnx >= 2
                    except TypeError:
                        return ox.features_from_bbox(north, south, east, west, tags=tags)       # osmnx 1.x
                except Exception as exc:  # noqa: BLE001 - network / server errors
                    last = exc
                    wait = 5 * (2 ** attempt)
                    print(f"[04] Overpass {ox.settings.overpass_url} failed ({type(exc).__name__}); retry in {wait}s")
                    time.sleep(wait)
        raise RuntimeError(f"all Overpass endpoints failed: {last}")

    frames = [query(tags).reset_index() for tags in ({"highway": True}, {"place": ["village", "hamlet", "town"]})]
    ox.settings.overpass_url = default_url
    return pd.concat(frames, ignore_index=True)


SETTLEMENT_BUFFER_M = 200   # a settlement point is "exposed" if a wet pixel lies within this distance


def _sample_points(geom, step_deg: float):
    import math

    gt = geom.geom_type
    if gt == "Point":
        # OSM settlements are single points that almost never fall exactly on a wet 100 m pixel,
        # so also test a ring around the point (centre + 8 points at SETTLEMENT_BUFFER_M).
        dlat = SETTLEMENT_BUFFER_M / 111_320
        dlon = dlat / max(math.cos(math.radians(geom.y)), 0.2)
        ring = [(geom.x + dlon * math.cos(a * math.pi / 4), geom.y + dlat * math.sin(a * math.pi / 4)) for a in range(8)]
        return [(geom.x, geom.y), *ring]
    if gt in ("LineString", "LinearRing"):
        n = max(2, int(geom.length / step_deg) + 1)
        return [geom.interpolate(i / (n - 1), normalized=True).coords[0] for i in range(n)]
    if gt == "Polygon":
        return _sample_points(geom.exterior, step_deg) + [geom.representative_point().coords[0]]
    if gt.startswith("Multi") or gt == "GeometryCollection":
        return [p for g in geom.geoms for p in _sample_points(g, step_deg)]
    return []


def _round_coords(obj, nd=5):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(v), nd) for v in obj]
        return [_round_coords(o, nd) for o in obj]
    return obj


def run(aoi_id: str, store: Path, *, osm_file: str | None = None, min_wet: int = MIN_WET_OBSERVATIONS,
        log=print) -> dict:
    from shapely.geometry import mapping

    manifest = load_manifest(aoi_id, store)
    bounds = manifest["bounds"]
    with np.load(store / aoi_id / "time_series_cube.npz") as z:
        cls = z["cls"]
        dates = [str(d) for d in z["dates"]]
    wet = (cls == OPEN_WATER) | (cls == FLOODED_VEG)          # (T,R,C)
    T, rows, cols = cls.shape
    west, south, east, north = bounds
    step = min((east - west) / cols, (north - south) / rows) / 2

    threshold = min(min_wet, T)
    note = (f"Wet on >= {threshold} of {T} NISAR observations (settlements: wet pixel within {SETTLEMENT_BUFFER_M} m). "
            "Inspection candidates only — never a damage claim.")
    if threshold < min_wet:
        note += f" Threshold lowered from {min_wet} because only {T} same-track dates exist (Plan C)."

    if osm_file:
        import geopandas as gpd
        gdf = gpd.read_file(osm_file)
        source = f"local file {Path(osm_file).name}"
    else:
        gdf = fetch_osm(bounds)
        source = "OpenStreetMap via osmnx (live)"
    log(f"[04] {len(gdf)} OSM features from {source}")

    features = []
    settlements_checked = 0
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        highway = row.get("highway") if "highway" in row else None
        place = row.get("place") if "place" in row else None
        if isinstance(highway, str) and (highway in SKIP_HIGHWAYS or geom.geom_type == "Point"):
            continue    # footpaths etc.; also highway *nodes* (bus stops, crossings, signals) are not roads
        kind = "road" if isinstance(highway, str) else (place if isinstance(place, str) else None)
        if kind is None:
            continue
        pts = _sample_points(geom, step)
        rc = set()
        for x, y in pts:
            if west <= x <= east and south <= y <= north:
                c = min(cols - 1, int((x - west) / (east - west) * cols))
                r = min(rows - 1, int((north - y) / (north - south) * rows))
                rc.add((r, c))
        if not rc:
            continue
        rr, cc = zip(*rc)
        wet_any = wet[:, rr, cc].any(axis=1)                # per date: did the feature touch wet pixels?
        valid_any = (cls[:, rr, cc] != 255).any(axis=1)
        m = int(wet_any.sum())
        if kind != "road":
            settlements_checked += 1
        if m < threshold:
            continue
        osm_id = row.get("osmid", row.get("id", row.get("osm_id")))
        el = row.get("element", row.get("element_type", ""))
        if isinstance(row.get("name"), str):
            name = row.get("name")
        elif isinstance(row.get("ref"), str):
            name = row.get("ref")
        elif kind == "road":
            name = f"{highway.replace('_', ' ')} road (unnamed)"
        else:
            name = f"{kind} (unnamed)"
        geom_s = geom.simplify(step / 2) if geom.geom_type != "Point" else geom
        features.append({
            "type": "Feature",
            "id": f"{el}/{osm_id}" if el else str(osm_id),
            "geometry": {**mapping(geom_s), "coordinates": _round_coords(mapping(geom_s)["coordinates"])},
            "properties": {
                "osm_id": str(osm_id), "kind": kind, "name": name,
                "highway": highway if isinstance(highway, str) else None,
                "wet_observations": m, "total_observations": int(valid_any.sum()),
                "wet_dates": [d for d, w in zip(dates, wet_any) if w],
            },
        })
    rank = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}
    features.sort(key=lambda f: (-f["properties"]["wet_observations"],
                                 rank.get(f["properties"].get("highway"), 9),
                                 "(unnamed)" in f["properties"]["name"]))   # important + named roads first
    flagged = sum(1 for f in features if f["properties"]["kind"] != "road")
    note += f" OSM settlements inside the area: {settlements_checked}, flagged: {flagged}."
    fc = {"type": "FeatureCollection", "features": features,
          "_meta": {"source": source, "generated_at": now_iso(), "threshold": threshold, "note": note,
                    "attribution": "© OpenStreetMap contributors"}}
    out = store / aoi_id / "osm_exposure.geojson"
    out.write_text(json.dumps(fc), encoding="utf-8")
    manifest.setdefault("provenance", {})["exposure"] = {"candidates": len(features), "threshold": threshold,
                                                         "source": source, "note": note}
    save_manifest(aoi_id, store, manifest)
    log(f"[04] {len(features)} inspection candidates -> {out}")
    return fc
