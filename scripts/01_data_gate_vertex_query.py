"""01 — NISAR Data Gate (SRS §3, §5.1, §9 Phase 1).

Finds NISAR L2 GCOV granules for an AOI, selects the most complete SAME-TRACK
stack, records polarization / maturity / fallback plan, and locks the AOI
manifest timeline.

Owner: Himanshu (@lunar_node) + Pravin (@cosmosinfoverse)

Three input modes (pick one):
    --h5-dir DIR          index already-downloaded .h5 files (checks footprint vs AOI)
    --names-file FILE     a text file of granule names (one per line) — lock without the data
    --search              live earthaccess / CMR search (EARTHDATA_USERNAME/PASSWORD or ~/.netrc)
                          add --download DIR to fetch the selected stack

Examples:
    python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli --h5-dir D:/nisar
    python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli --names-file granules.txt --dry-run
    python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli --search --download D:/nisar

Coverage found on NASA CMR (14 Nov 2026), June-Nov 2026, dual-pol:
    aoi_assam_majuli  -> track/frame 040/015 (Ascending), 12 dates incl. 10 Jul, 22 Jul, 15 Aug
    aoi_nagpur_kanhan -> track/frame 156/012 (Ascending), 11 dates
    (tracks 063/135 frame 076 cover 23.5-26.2N, 69-74E = Gujarat/Rajasthan, NOT these AOIs)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline.common import AOI_BOUNDS, data_store  # noqa: E402
from geosar_pipeline.data_gate import (download, granules_from_dir, granules_from_earthaccess,  # noqa: E402
                                       granules_from_names, lock)

DATA_STORE = data_store()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi", required=True, choices=list(AOI_BOUNDS))
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--h5-dir")
    src.add_argument("--names-file")
    src.add_argument("--search", action="store_true")
    p.add_argument("--short-name", default=os.environ.get("NISAR_CMR_SHORT_NAME", "NISAR_L2_GCOV_PROVISIONAL_V1,NISAR_L2_GCOV_V1"),
                   help="comma-separated CMR collections (PROVISIONAL + VALIDATED by default)")
    p.add_argument("--track-frame", help="force a track/frame, e.g. 063/076")
    p.add_argument("--download", help="with --search: download the selected stack here")
    p.add_argument("--data-store", help="override data_store dir (default services/api/data_store)")
    p.add_argument("--dry-run", action="store_true", help="print the plan, do not write the manifest")
    args = p.parse_args()

    store = data_store(args.data_store)
    print(f"[01] Data gate for {args.aoi} bbox={AOI_BOUNDS[args.aoi]} store={store}")

    if args.h5_dir:
        granules = granules_from_dir(args.h5_dir, args.aoi)
    elif args.names_file:
        granules = granules_from_names(Path(args.names_file).read_text().splitlines())
    else:
        granules = granules_from_earthaccess(args.aoi, args.short_name)
    print(f"[01] {len(granules)} GCOV granules parsed")
    if not granules:
        sys.exit("[01] nothing found — check the folder / names / short_name (Plan D: switch AOI or frame)")

    report = lock(args.aoi, granules, store, args.track_frame, dry_run=args.dry_run)
    print(json.dumps({k: report[k] for k in ("selected_track_frame", "fallback_plan", "dual_pol",
                                             "tracks_found", "skipped")}, indent=2))
    for g in report["stack"]:
        print(f"   {g['date']}  {g['maturity']:<11}  {g['polarization']:<6}  {g['granule_id']}")
    if args.download and args.search:
        selected = {g["granule_id"] for g in report["stack"]}
        files = download([g for g in granules if g["granule_id"] in selected], args.download)
        print(f"[01] downloaded {len(files)} files to {args.download}")
    print("[01] dry run — manifest unchanged" if args.dry_run else f"[01] manifest locked for {args.aoi}")


if __name__ == "__main__":
    main()
