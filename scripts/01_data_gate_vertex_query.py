"""01 — NISAR Data Gate (SRS §3, §5.1, §9 Phase 1).

Queries ASF Vertex / NASA CMR via `earthaccess` for same-track NISAR L2 GCOV
granules over each AOI, verifies HH/HV availability, and writes a locked granule
timeline into each AOI's manifest.json.

Owner: Himanshu (@lunar_node) + Pravin (@cosmosinfoverse)

Usage:
    python scripts/01_data_gate_vertex_query.py --aoi aoi_assam_majuli
    EARTHDATA_USERNAME / EARTHDATA_PASSWORD (or ~/.netrc) required by earthaccess.

This is a scaffold: the TODOs mark where Phase 1 fills in real logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_STORE = Path(__file__).resolve().parent.parent / "services" / "api" / "data_store"

AOI_BOUNDS = {
    "aoi_assam_majuli": [93.90, 26.75, 94.30, 27.05],
    "aoi_nagpur_kanhan": [78.95, 21.15, 79.35, 21.45],
}


def query_granules(aoi_id: str, bounds: list[float]) -> list[dict]:
    """TODO(Phase 1): use earthaccess.search_data(short_name='NISAR_L2_GCOV_*',
    bounding_box=tuple(bounds), temporal=('2026-06-01','2026-11-30')).
    Group by track/frame, keep the most complete same-track series, and read
    polarization + maturity (PROVISIONAL/VALIDATED) from granule metadata verbatim.
    """
    raise NotImplementedError("Phase 1: implement earthaccess query + same-track selection.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", required=True, choices=list(AOI_BOUNDS))
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing manifest.")
    args = parser.parse_args()

    bounds = AOI_BOUNDS[args.aoi]
    print(f"[01] Data gate for {args.aoi} bbox={bounds}")

    try:
        granules = query_granules(args.aoi, bounds)
    except NotImplementedError as exc:
        print(f"[01] SCAFFOLD: {exc}")
        return

    manifest_path = DATA_STORE / args.aoi / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["timeline"] = granules
    if not args.dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"[01] Wrote {len(granules)} granules to {manifest_path}")


if __name__ == "__main__":
    main()
