"""Live NASA CMR / Earthdata connector with strict timeout + verified-manifest fallback.

SRS §6.1, §7.1, §7.2: proves live NASA catalogue integration, but any network
hiccup or timeout falls back to the granules locked in the local AOI manifest
(written by scripts/01), clearly labelled, so the demo never crashes.
"""
from __future__ import annotations

import logging

import httpx

from ..config import get_settings
from ..data_store import store

logger = logging.getLogger("geosar.earthdata")

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"


def _bbox_list(bbox: str) -> list[float] | None:
    try:
        vals = [float(v) for v in bbox.split(",")]
        return vals if len(vals) == 4 else None
    except ValueError:
        return None


def _intersects(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def cached_response(bbox: str, short_name: str, aoi_id: str | None = None) -> dict:
    """Granules locked in local manifests (verified by the Phase 1 data gate)."""
    box = _bbox_list(bbox)
    granules, aois = [], []
    for m in store.list_aois():
        if aoi_id and m.get("aoi_id") != aoi_id:
            continue
        if not aoi_id and box and m.get("bounds") and not _intersects(box, m["bounds"]):
            continue
        aois.append(m.get("aoi_id"))
        for t in m.get("timeline", []):
            gid = t.get("granule_id")
            if gid and gid != "TBD":
                granules.append({"id": gid, "date": t.get("date"), "maturity": t.get("maturity"),
                                 "track_frame": t.get("track_frame")})
    return {
        "query_echo": {"short_name": short_name, "bounding_box": bbox},
        "granule_count": len(granules),
        "granules": granules,
        "aois": aois,
        "note": ("Verified local manifest (granules locked by scripts/01) — labelled, not a live pull."
                 if granules else "No granules locked in local manifests yet (run scripts/01)."),
    }


async def earthdata_live_search(bbox: str, short_name: str | None = None, aoi_id: str | None = None):
    """Returns (data, source_mode, fallback_active, warning)."""
    settings = get_settings()
    short_name = short_name or settings.nisar_cmr_short_name
    headers = {}
    if settings.earthdata_token:
        headers["Authorization"] = f"Bearer {settings.earthdata_token}"

    names = [n.strip() for n in short_name.split(",") if n.strip()]
    params = {
        "short_name": names[0] if len(names) == 1 else names,
        "bounding_box": bbox,
        "page_size": 20,
        "sort_key": "-start_date",
    }

    try:
        timeout = httpx.Timeout(settings.external_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(CMR_GRANULES_URL, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
            entries = payload.get("feed", {}).get("entry", [])
            granules = [
                {
                    "id": e.get("producer_granule_id") or e.get("title") or e.get("id"),
                    "date": (e.get("time_start") or "")[:10],
                    "maturity": _maturity_from_entry(e, settings.validated_from),
                }
                for e in entries
            ]
            return (
                {"query_echo": params, "granule_count": len(granules), "granules": granules},
                "LIVE_API",
                False,
                None if granules else f"Live CMR reachable but returned 0 granules for '{short_name}'.",
            )
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all fallback
        logger.warning("Earthdata live query failed (%s); serving verified manifest.", exc)
        return (
            cached_response(bbox, short_name, aoi_id),
            "LOCAL_VERIFIED_CACHE",
            True,
            f"Live NASA CMR unavailable ({type(exc).__name__}); showing verified local granule list.",
        )


def _maturity_from_entry(entry: dict, validated_from: str = "2026-10-23") -> str:
    """Maturity from the CMR collection (dataset_id 'NISAR Provisional …' / 'NISAR Validated …');
    otherwise derive from the acquisition date (from the 21-23 Oct 2026 transition, SRS §3.2)."""
    text = " ".join(str(entry.get(k) or "") for k in ("dataset_id", "collection_concept_id", "title")).upper()
    if "PROVISIONAL" in text:
        return "PROVISIONAL"
    if "VALIDATED" in text:
        return "VALIDATED"
    date = (entry.get("time_start") or "")[:10]
    if date and date >= validated_from:
        return "VALIDATED"
    return "PROVISIONAL"
