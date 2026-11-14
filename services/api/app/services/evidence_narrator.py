"""Radar Evidence Card narrator (SRS §5, §7.3).

Primary path is a 100% deterministic physics template built strictly from the
computed telemetry numbers. An optional LLM narrator (grounded on the same JSON,
3s timeout) may reformat the text, but the deterministic card is always the
fallback so output is never free-form hallucination.
"""
from __future__ import annotations

import logging

import httpx

from ..config import get_settings

logger = logging.getLogger("geosar.evidence")


def deterministic_card(t: dict) -> dict:
    """Builds the grounded card from telemetry numbers only."""
    lat = t.get("lat")
    lon = t.get("lon")
    hydro = t.get("hydroperiod", {}) or {}
    m, n = hydro.get("m"), hydro.get("n")
    pct = hydro.get("pct")
    regime = t.get("gmm_regime")
    jrc = t.get("jrc_occurrence_pct")
    wc = t.get("worldcover_class")
    delta_hh = t.get("delta_hh_db")
    peak_date = t.get("peak_date")
    maturity = t.get("peak_maturity", "PROVISIONAL")

    persistence = (
        f"Wet in {m} of {n} valid NISAR L-band observations"
        + (f" ({pct}%)." if pct is not None else ".")
        if m is not None and n
        else "Hydroperiod not available for this pixel."
    )

    physics = "No double-bounce surge recorded at this pixel."
    if delta_hh is not None and peak_date:
        physics = (
            f"During the {peak_date} acquisition ({maturity}), HH backscatter changed by "
            f"{delta_hh:+.1f} dB versus the dry baseline — "
            + ("consistent with L-band dihedral double-bounce scattering from water beneath vegetation."
               if delta_hh >= 3.0 else "below the +3.0 dB double-bounce threshold.")
        )

    confidence = "Low"
    if m and n and delta_hh is not None:
        if m / n >= 0.5 and delta_hh >= 3.0:
            confidence = "Moderate-High"
        elif m / n >= 0.3:
            confidence = "Moderate"

    return {
        "mode": "deterministic",
        "location": f"{lat}, {lon}" if lat is not None else None,
        "hydrological_regime": regime,
        "monsoon_persistence": persistence,
        "radar_physics_evidence": physics,
        "land_cover_context": _worldcover_text(wc, jrc),
        "confidence": confidence,
        "caveat": (
            "This is a radar-derived surface/canopy-water indication for field inspection, "
            "not a confirmed flood-depth measurement."
        ),
    }


def _worldcover_text(wc: int | None, jrc: float | None) -> str:
    names = {10: "Tree Cover", 30: "Grassland", 40: "Cropland",
             90: "Herbaceous Wetland", 95: "Mangroves", 80: "Permanent Water"}
    label = names.get(wc, "Unclassified") if wc is not None else "Unavailable"
    jrc_text = ""
    if jrc is not None:
        jrc_text = (
            f" Optical JRC historical water occurrence is {jrc:.0f}%"
            + (" (low — optical sensors cannot penetrate canopy)." if jrc < 20 else ".")
        )
    return f"Classified as {label} in ESA WorldCover (10 m).{jrc_text}"


async def build_evidence_card(telemetry: dict):
    """Returns (card, source_mode, fallback_active, warning)."""
    settings = get_settings()
    base_card = deterministic_card(telemetry)

    if not settings.llm_enabled:
        return base_card, "LOCAL_VERIFIED_CACHE", False, None

    try:
        prompt = (
            "Rewrite the following radar telemetry card in clear plain language. "
            "Use ONLY these numbers; do not invent any value. Keep the caveat verbatim.\n"
            f"{base_card}"
        )
        timeout = httpx.Timeout(min(settings.external_timeout_seconds, 3.0))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.llm_api_base}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            narrated = dict(base_card)
            narrated["mode"] = "llm_grounded"
            narrated["narration"] = text
            return narrated, "LIVE_API", False, None
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM narrator failed (%s); using deterministic card.", exc)
        return base_card, "LOCAL_VERIFIED_CACHE", True, f"LLM narrator unavailable ({type(exc).__name__})."
