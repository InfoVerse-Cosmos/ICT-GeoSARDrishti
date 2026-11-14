"""Live NASA Earthdata CMR connectivity endpoint (SRS §7.1)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..envelope import envelope
from ..services.earthdata_client import earthdata_live_search

router = APIRouter(tags=["nisar"])


@router.get("/nisar/earthdata-live")
async def earthdata_live(
    bbox: str = Query("93.90,26.75,94.30,27.05", description="west,south,east,north"),
    short_name: str = Query("NISAR_L2_GCOV_V1", description="CMR collection short_name"),
) -> dict:
    """Proves live NASA Earthdata connectivity; falls back to a cached CMR response."""
    result, source_mode, fallback, warning = await earthdata_live_search(bbox, short_name)
    return envelope(result, source_mode=source_mode, fallback_active=fallback, warning=warning)
