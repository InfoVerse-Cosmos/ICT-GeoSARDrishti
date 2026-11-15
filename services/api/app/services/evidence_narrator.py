"""Radar Evidence Card narrator (SRS §5, §7.3).

Primary path is a 100% deterministic physics template built strictly from the
computed telemetry numbers. An optional LLM narrator (grounded on the same JSON,
3s timeout) may reformat the text, but the deterministic card is always the
fallback so output is never free-form hallucination.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from ..config import get_settings

logger = logging.getLogger("geosar.evidence")


_SYSTEM_PROMPT = (
    "You explain NISAR L-band radar results to a non-expert (a floodplain manager, not a scientist). "
    "Rewrite the JSON evidence card as 3-4 short plain sentences. Use ONLY facts and numbers present in "
    "the JSON; never invent, round differently, or add any value, place, date or cause. Never claim a "
    "confirmed flood, water depth or damage. End with the card's caveat meaning: this is a radar-derived "
    "indication for field inspection, not a confirmed measurement. Prefer everyday words; mention technical terms (dB, HH, double-bounce) only when essential. No markdown, no bullet points."
)


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
    open_sig = bool(m_open and min_hh is not None and min_hh_date)
    if open_sig and delta_hh is not None and delta_hh < 3.0:
        # Water pixel: do not talk about a "change" that is really a darkening; just say why it is water.
        physics = ("HH stayed below the dry reference on every date, so no double-bounce surge."
                   if delta_hh < 0 else
                   "HH never rose above the dry reference by +3.0 dB or more, so no double-bounce surge.")
    elif delta_hh is not None and peak_date:
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
    parts = []
    if wc is not None:
        parts.append(f"Classified as {names.get(wc, 'Unclassified')} in ESA WorldCover (10 m).")
    else:
        parts.append("ESA WorldCover land cover is not loaded in this data pack.")
    if jrc is not None:
        parts.append(
            f"Optical JRC historical water occurrence is {jrc:.0f}%"
            + (" (low — optical sensors cannot penetrate canopy)." if jrc < 20 else ".")
        )
    return " ".join(parts)


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _ungrounded_numbers(text: str, card: dict) -> set[str]:
    """Numbers in the LLM text that do not occur in the deterministic card (the only allowed source)."""
    source = json.dumps(card, ensure_ascii=False)
    return {n for n in _NUM_RE.findall(text) if n not in source}


# Never spend tokens twice on the same card (cache), and
# after a 429 stop calling for a while so every click is not delayed by a doomed request.
_NARRATION_CACHE: dict[str, dict] = {}
_CACHE_MAX = 256
_COOLDOWN_S = 600.0
_cooldown_until: dict[str, float] = {}   # model -> monotonic time until which it is skipped (after a 429)


class _ModelFailed(Exception):
    """One model in the chain could not narrate; the next model (if any) is tried."""


async def _narrate_with(client, settings, model: str, base_card: dict) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(base_card, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }
    resp = None
    for attempt in range(2):  # one quick retry: providers answer 503 "overloaded" in bursts
        resp = await client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        if resp.status_code == 429:
            _cooldown_until[model] = time.monotonic() + _COOLDOWN_S
            raise _ModelFailed(f"{model}: quota/rate limit (429)")
        if resp.status_code != 503 or attempt == 1:
            break
        await asyncio.sleep(0.4)
    resp.raise_for_status()
    text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
    if not text:
        raise _ModelFailed(f"{model}: empty response")
    ungrounded = _ungrounded_numbers(text, base_card)
    if ungrounded:  # hallucination guard: every number must come from the computed card
        raise _ModelFailed(f"{model}: narration used numbers not in the card {sorted(ungrounded)}")
    return text


async def build_evidence_card(telemetry: dict, narrate: bool = True):
    """Returns (card, source_mode, fallback_active, warning). narrate=False -> instant deterministic card.

    Fallback ladder (each step is labelled in the card, never silent):
      1. primary model (default gpt-4o-mini) -> card["narration_model"] = that model
      2. fallback model(s), own rate limits -> card["narration_model"] = fallback model
      3. built-in physics template        -> mode "deterministic" (always works, same numbers)
    """
    settings = get_settings()
    base_card = deterministic_card(telemetry)

    if not narrate or not settings.llm_enabled:
        return base_card, "LOCAL_VERIFIED_CACHE", False, None

    cache_key = json.dumps(base_card, sort_keys=True, ensure_ascii=False)
    if cache_key in _NARRATION_CACHE:
        return dict(_NARRATION_CACHE[cache_key]), "LIVE_API", False, None

    models = [m for m in dict.fromkeys([settings.llm_model_name, *settings.llm_fallback_model_list])]
    now = time.monotonic()
    usable = [m for m in models if _cooldown_until.get(m, 0.0) <= now]
    if not usable:
        return base_card, "LOCAL_VERIFIED_CACHE", True, "LLM narrator paused (quota/rate limit); using built-in physics template."

    reasons: list[str] = []
    try:
        timeout = httpx.Timeout(settings.llm_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for model in usable[:3]:
                try:
                    text = await _narrate_with(client, settings, model, base_card)
                except (_ModelFailed, httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
                    reasons.append(f"{type(exc).__name__}: {exc}" if not isinstance(exc, _ModelFailed) else str(exc))
                    continue
                narrated = dict(base_card)
                narrated["mode"] = "llm_grounded"
                narrated["narration"] = text
                narrated["narration_model"] = model
                if len(_NARRATION_CACHE) >= _CACHE_MAX:
                    _NARRATION_CACHE.pop(next(iter(_NARRATION_CACHE)))
                _NARRATION_CACHE[cache_key] = narrated
                warn = f"Primary model unavailable, narrated by fallback {model}." if model != models[0] else None
                return narrated, "LIVE_API", False, warn
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"{type(exc).__name__}")
    logger.warning("LLM narrator failed (%s); using built-in physics template.", "; ".join(reasons))
    first = reasons[0].split(":")[0] if reasons else "error"
    return base_card, "LOCAL_VERIFIED_CACHE", True, f"LLM narrator unavailable ({first})."
