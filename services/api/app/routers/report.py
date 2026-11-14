"""One-click analysis report endpoint (SRS §4.2, §7.1).

Aggregates the already-computed pack numbers (hydroperiod cube, GMM regimes,
per-scene thresholds, OSM exposure, provenance) into a single plain-language
payload the UI renders in-place. Grounded strictly in computed data — no
invented numbers — with the mandatory honest caveat attached.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..envelope import envelope
from ..services.report_builder import build_report

router = APIRouter(tags=["report"])


@router.get("/aois/{aoi_id}/report")
def report(aoi_id: str) -> dict:
    data = build_report(aoi_id)
    if data is None:
        return envelope(None, aoi_id=aoi_id, status="unknown_aoi", fallback_active=True,
                        warning=f"Unknown AOI '{aoi_id}'.")
    return envelope(
        data,
        aoi_id=aoi_id,
        fallback_active=not data.get("data_pack_ready", False),
        warning=data.get("message"),
    )
