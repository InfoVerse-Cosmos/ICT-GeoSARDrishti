"""Serves georeferenced RGBA PNG overlays for MapLibre image sources (SRS §7.1).

If an overlay is missing, returns a clean transparent 1x1 placeholder PNG with a
warning header instead of a 404, so the map keeps rendering.
"""
from __future__ import annotations

import base64

from fastapi import APIRouter
from fastapi.responses import Response

from ..data_store import store

router = APIRouter(tags=["layers"])

# 1x1 fully transparent PNG.
_TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

ALLOWED_LAYERS = {"open_water", "flooded_veg", "hydroperiod", "gmm_regimes", "jrc_anomaly", "context_layers"}


@router.get("/layers/{aoi_id}/{layer_id}.png")
def layer_png(aoi_id: str, layer_id: str, date: str | None = None) -> Response:
    if layer_id not in ALLOWED_LAYERS:
        return Response(
            content=_TRANSPARENT_PNG,
            media_type="image/png",
            headers={"X-GeoSAR-Warning": f"unknown_layer:{layer_id}", "X-GeoSAR-Fallback": "true"},
        )

    aoi_dir = store.aoi_dir(aoi_id)
    filename = f"{layer_id}_{date}.png" if date else f"{layer_id}.png"
    overlay = aoi_dir / "overlays" / filename

    if overlay.exists():
        return Response(
            content=overlay.read_bytes(),
            media_type="image/png",
            headers={"X-GeoSAR-Fallback": "false", "Cache-Control": "public, max-age=3600"},
        )

    return Response(
        content=_TRANSPARENT_PNG,
        media_type="image/png",
        headers={
            "X-GeoSAR-Warning": f"overlay_not_found:{filename}",
            "X-GeoSAR-Fallback": "true",
        },
    )
