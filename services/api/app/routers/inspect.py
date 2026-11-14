"""Pixel-click dB trajectory + Evidence Card endpoints (SRS §7.1, §7.3)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..data_store import store
from ..envelope import envelope
from ..services.evidence_narrator import build_evidence_card
from ..services.raster_sampler import sample_pixel

router = APIRouter(tags=["inspect"])


@router.get("/aois/{aoi_id}/inspect")
def inspect(aoi_id: str, lat: float, lon: float) -> dict:
    manifest = store.get(aoi_id)
    if manifest is None:
        return envelope(None, aoi_id=aoi_id, status="unknown_aoi", fallback_active=True,
                        warning=f"Unknown AOI '{aoi_id}'.")

    bounds = manifest.get("bounds")  # [west, south, east, north]
    if bounds and not (bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]):
        return envelope(
            {"lat": lat, "lon": lon},
            aoi_id=aoi_id,
            status="outside_aoi",
            warning=(
                "Clicked coordinate lies outside the pre-computed NISAR AOI footprint. "
                "Click inside the highlighted cyan telemetry boundary."
            ),
        )

    result = sample_pixel(aoi_id, lat, lon)
    return envelope(
        result["data"],
        aoi_id=aoi_id,
        status=result["status"],
        fallback_active=result["fallback_active"],
        warning=result["warning"],
    )


class EvidenceCardRequest(BaseModel):
    aoi_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    telemetry: dict = {}


@router.post("/evidence-card")
async def evidence_card(req: EvidenceCardRequest) -> dict:
    card, source_mode, fallback, warning = await build_evidence_card(req.telemetry)
    return envelope(
        {"card": card},
        aoi_id=req.aoi_id,
        source_mode=source_mode,
        fallback_active=fallback,
        warning=warning,
    )
