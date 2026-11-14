"""OSM infrastructure exposure endpoint (SRS §5.5, §7.1).

Returns ranked ground-inspection candidates (roads/villages wet on M>=3 dates).
Never a damage claim — these are inspection candidates only.
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from ..data_store import store
from ..envelope import envelope

router = APIRouter(tags=["exposure"])


@router.get("/aois/{aoi_id}/exposure")
def exposure(aoi_id: str) -> dict:
    manifest = store.get(aoi_id)
    if manifest is None:
        return envelope(None, aoi_id=aoi_id, status="unknown_aoi", fallback_active=True,
                        warning=f"Unknown AOI '{aoi_id}'.")

    aoi_dir = store.aoi_dir(aoi_id)
    geojson_path = aoi_dir / "osm_exposure.geojson"

    if not geojson_path.exists():
        return envelope(
            {
                "geojson": {"type": "FeatureCollection", "features": []},
                "ranked": [],
                "note": "Ground-inspection candidates only, never a damage claim.",
            },
            aoi_id=aoi_id,
            fallback_active=True,
            warning="No exposure pack found yet (generated in Phase 2 via scripts/04).",
        )

    fc = json.loads(geojson_path.read_text())
    ranked = sorted(
        (
            {
                "id": f.get("id") or f["properties"].get("osm_id"),
                "kind": f["properties"].get("kind"),
                "name": f["properties"].get("name", "unnamed"),
                "wet_observations": f["properties"].get("wet_observations"),
                "total_observations": f["properties"].get("total_observations"),
            }
            for f in fc.get("features", [])
        ),
        key=lambda r: (r["wet_observations"] or 0),
        reverse=True,
    )
    return envelope(
        {
            "geojson": fc,
            "ranked": ranked,
            "note": "Ground-inspection candidates only, never a damage claim.",
        },
        aoi_id=aoi_id,
    )
