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

    west, south, east, north = bounds
    frames = []
    for tags in ({"highway": True}, {"place": ["village", "hamlet", "town"]}):
        try:
            gdf = ox.features_from_bbox(bbox=(west, south, east, north), tags=tags)  # osmnx >= 2
        except TypeError:
            gdf = ox.features_from_bbox(north, south, east, west, tags=tags)       # osmnx 1.x
        frames.append(gdf.reset_index())
    return pd.concat(frames, ignore_index=True)


def _sample_points(geom, step_deg: float):
    gt = geom.geom_type
    if gt == "Point":
        return [(geom.x, geom.y)]
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
    note = f"Wet on >= {threshold} of {T} NISAR observations. Inspection candidates only — never a damage claim."
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
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        highway = row.get("highway") if "highway" in row else None
        place = row.get("place") if "place" in row else None
        if isinstance(highway, str) and highway in SKIP_HIGHWAYS:
            continue
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
        if m < threshold:
            continue
        osm_id = row.get("osmid", row.get("id", row.get("osm_id")))
        el = row.get("element", row.get("element_type", ""))
        name = row.get("name") if isinstance(row.get("name"), str) else "unnamed"
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
    features.sort(key=lambda f: -f["properties"]["wet_observations"])
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
