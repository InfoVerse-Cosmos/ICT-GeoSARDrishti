"""04 — OSM infrastructure exposure (SRS §5.5, §9 Phase 2).

Downloads OSM roads (highway=*) and settlements (place=village|hamlet|town) via
osmnx for the AOI, intersects them with the hydroperiod raster, and exports every
segment/settlement wet on M>=3 acquisitions as ground-inspection candidates.

Owner: Sakshi (@sakshitayade)

These are INSPECTION CANDIDATES ONLY — never a damage or stranded-people claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_STORE = Path(__file__).resolve().parent.parent / "services" / "api" / "data_store"

MIN_WET_OBSERVATIONS = 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", required=True)
    args = parser.parse_args()

    # TODO(Phase 2):
    #   import osmnx as ox, geopandas as gpd
    #   roads = ox.graph_to_gdfs(ox.graph_from_bbox(...))  # highway=*
    #   villages = ox.features_from_bbox(..., tags={"place": ["village","hamlet","town"]})
    #   sample hydroperiod raster along each geometry; count wet observations;
    #   keep features with wet_observations >= MIN_WET_OBSERVATIONS.
    out = {
        "type": "FeatureCollection",
        "features": [],
        "_note": f"SCAFFOLD: filled in Phase 2. Threshold M>={MIN_WET_OBSERVATIONS}. Inspection candidates only.",
    }
    out_path = DATA_STORE / args.aoi / "osm_exposure.geojson"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[04] SCAFFOLD: wrote empty exposure FeatureCollection to {out_path}")


if __name__ == "__main__":
    main()
