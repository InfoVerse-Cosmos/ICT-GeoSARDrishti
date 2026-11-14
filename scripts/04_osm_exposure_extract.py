"""04 — OSM infrastructure exposure (SRS §5.5, §9 Phase 2).

Downloads OSM roads (highway=*) and settlements (place=village|hamlet|town) via
osmnx for the AOI (or reads a local GeoJSON/GPKG), samples the per-date wet
classes along every geometry, and exports features wet on M >= 3 acquisitions
as ground-inspection candidates (data_store/<aoi>/osm_exposure.geojson).

Owner: Sakshi (@sakshitayade)

These are INSPECTION CANDIDATES ONLY — never a damage or stranded-people claim.

Example:
    python scripts/04_osm_exposure_extract.py --aoi aoi_assam_majuli [--osm-file roads_villages.geojson]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline.common import AOI_BOUNDS, MIN_WET_OBSERVATIONS, data_store  # noqa: E402
from geosar_pipeline import exposure  # noqa: E402

DATA_STORE = data_store()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi", required=True, choices=list(AOI_BOUNDS))
    p.add_argument("--osm-file", help="offline OSM extract (GeoJSON/GPKG with highway/place columns)")
    p.add_argument("--min-wet", type=int, default=MIN_WET_OBSERVATIONS)
    p.add_argument("--data-store", help="override data_store dir")
    args = p.parse_args()
    exposure.run(args.aoi, data_store(args.data_store), osm_file=args.osm_file, min_wet=args.min_wet)


if __name__ == "__main__":
    main()
