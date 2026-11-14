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

    m_open = hydro.get("m_open") or 0
    baseline, peak_hh = t.get("hh_baseline_db"), t.get("hh_peak_db")
    d_ratio = t.get("delta_ratio_db")
    min_hh, min_hh_date = t.get("min_hh_db"), t.get("min_hh_date")
    ow_thresh = t.get("open_water_threshold_db")
    single_pol = bool(t.get("single_pol_mode"))

    persistence = (
        f"Wet in {m} of {n} valid NISAR L-band observations"
        + (f" ({pct}%)." if pct is not None else ".")
        if m is not None and n
        else "Hydroperiod not available for this pixel."
    )

    physics = "No double-bounce surge recorded at this pixel."
    if delta_hh is not None and peak_date:
        detail = ""
        if baseline is not None and peak_hh is not None:
            detail = f" (from {baseline:.1f} dB dry baseline to {peak_hh:.1f} dB)"
        ratio_txt = ""
        if d_ratio is not None and not single_pol:
            ratio_txt = f" with a {d_ratio:+.1f} dB change in HH−HV difference"
        physics = (
            f"During the {peak_date} acquisition ({maturity or 'PROVISIONAL'}), HH backscatter changed by "
            f"{delta_hh:+.1f} dB{detail}{ratio_txt} versus the dry baseline — "
            + ("consistent with L-band dihedral double-bounce scattering from water beneath vegetation."
               if delta_hh >= 3.0 else "below the +3.0 dB double-bounce threshold.")
        )
    if m_open and min_hh is not None and min_hh_date:
        thr = f" (scene open-water threshold {ow_thresh:.1f} dB)" if ow_thresh is not None else ""
        physics += (f" Open-water signature: HH fell to {min_hh:.1f} dB on {min_hh_date}{thr} — "
                    f"specular reflection from a smooth water surface, dark in {m_open} of {n} observations.")
    if single_pol:
        physics += " Single-Pol HH mode: HV unavailable, so the HH−HV ratio test was not applied."

    confidence = "Low"
    if m and n:
        surge = delta_hh is not None and delta_hh >= 3.0
        persistent_open = m_open / n >= 0.5
        if m / n >= 0.5 and (surge or persistent_open):
            confidence = "Moderate-High"
        elif m / n >= 0.3 and (delta_hh is not None or m_open):
            confidence = "Moderate"

    regime_txt = regime
    if t.get("flooded_veg_sublabel") and regime:
        regime_txt = f"{regime} ({t['flooded_veg_sublabel']})"
    elif t.get("flooded_veg_sublabel"):
        regime_txt = t["flooded_veg_sublabel"]

    return {
        "mode": "deterministic",
        "location": f"{lat}, {lon}" if lat is not None else None,
        "hydrological_regime": regime_txt,
        "monsoon_persistence": persistence,
        "radar_physics_evidence": physics,
        "land_cover_context": _worldcover_text(wc, jrc),
        "confidence": confidence,
        "caveat": (
            "This is a radar-derived surface/canopy-water indication for field inspection, "
            "not a confirmed flood-depth measurement."
        ),
        **({"data_notice": "SYNTHETIC TEST DATA — not a NISAR observation."}
           if t.get("synthetic_test_data") else {}),
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
