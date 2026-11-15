"""GeoSAR Drishti FastAPI application entrypoint (SRS §6, §7).

Boots with CORS, loads AOI packs into memory, mounts all routers, and installs
global exception handlers so no request ever returns a raw 500 to the client.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import get_settings
from .data_store import store
from .envelope import envelope
from .routers import analyze, aois, exposure, inspect, layers, nisar, report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("geosar")

settings = get_settings()

app = FastAPI(
    title="GeoSAR Drishti API",
    description="NASA-ISRO NISAR L-band monsoon water intelligence (CH-06).",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    store.load()
    logger.info("Loaded %d analysed AOI pack(s) from %s", len(store.list_aois()), store.data_dir)
    if store.using_fallback:
        logger.warning("No analysed data in %s - put NISAR .h5 files in DATA/ and run analyze.", store.data_dir)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Never leak a raw 500: wrap in the standard envelope (SRS §7.2)."""
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=200,
        content=envelope(
            None,
            status="error",
            fallback_active=True,
            warning=f"Server handled an internal error gracefully: {type(exc).__name__}",
        ),
    )


@app.get("/api/v1/health")
def health() -> dict:
    return envelope(
        {
            "service": "geosar-drishti-api",
            "version": __version__,
            "aoi_packs": [a["aoi_id"] for a in store.list_aois()],
            "earthdata_token_configured": settings.earthdata_enabled,
            "llm_narrator_enabled": settings.llm_enabled,
            "data_store_fallback": store.using_fallback,
            "data_dir": str(store.data_dir),
            "data_packs": {a["aoi_id"]: store.pack_status(a["aoi_id"]) for a in store.list_aois()},
        },
        source_mode="LIVE_API",
    )


app.include_router(aois.router, prefix="/api/v1")
app.include_router(nisar.router, prefix="/api/v1")
app.include_router(layers.router, prefix="/api/v1")
app.include_router(inspect.router, prefix="/api/v1")
app.include_router(exposure.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")
app.include_router(analyze.router, prefix="/api/v1")


@app.get("/")
def root() -> dict:
    return envelope({"message": "GeoSAR Drishti API. See /docs and /api/v1/health."})
