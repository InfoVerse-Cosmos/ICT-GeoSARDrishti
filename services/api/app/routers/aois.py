"""AOI metadata + timeline + provenance + regional context endpoints (SRS §3.1, §7.1)."""
from __future__ import annotations

import json

from fastapi import APIRouter

from ..data_store import store
from ..envelope import envelope

router = APIRouter(tags=["aois"])


@router.get("/aois")
def list_aois() -> dict:
    aois = [
        {
            "aoi_id": a["aoi_id"],
            "name": a.get("name"),
            "role": a.get("role"),
            "bounds": a.get("bounds"),
            "default_zoom": a.get("default_zoom", 9),
            "layers": a.get("layers", []),
        }
        for a in store.list_aois()
    ]
    return envelope(
        {"aois": aois},
        fallback_active=store.using_fallback,
        warning="Serving default AOI directory (no data packs found)." if store.using_fallback else None,
    )


@router.get("/aois/{aoi_id}/timeline")
def timeline(aoi_id: str) -> dict:
    manifest = store.get(aoi_id)
    if manifest is None:
        return envelope(
            None,
            aoi_id=aoi_id,
            status="unknown_aoi",
            fallback_active=True,
            warning=f"Unknown AOI '{aoi_id}'. Use /api/v1/aois to list available AOIs.",
        )
    return envelope(
        {
            "aoi_id": aoi_id,
            "polarization": manifest.get("polarization", "HH+HV"),
            "single_pol_mode": bool(manifest.get("single_pol_mode", False)),
            "track_frame": manifest.get("track_frame"),
            "fallback_plan": manifest.get("fallback_plan", "A"),
            "reference_date": manifest.get("reference_date"),
            "acquisition_gaps": manifest.get("acquisition_gaps", ["2026-07-27/2026-08-10"]),
            "synthetic_test_data": bool(manifest.get("synthetic_test_data", False)),
            "season_summary": manifest.get("season_summary"),
            "data_pack_ready": store.has_cube(aoi_id),
            "timeline": manifest.get("timeline", []),
        },
        aoi_id=aoi_id,
        fallback_active=store.using_fallback,
        warning="Cached baseline timeline." if store.using_fallback else None,
    )


@router.get("/aois/{aoi_id}/provenance")
def provenance(aoi_id: str) -> dict:
    manifest = store.get(aoi_id)
    if manifest is None:
        return envelope(None, aoi_id=aoi_id, status="unknown_aoi", fallback_active=True,
                        warning=f"Unknown AOI '{aoi_id}'.")
    prov = manifest.get("provenance", {})
    return envelope(
        {
            "aoi_id": aoi_id,
            "track_frame": manifest.get("track_frame"),
            "fallback_plan": manifest.get("fallback_plan"),
            "reference_date": prov.get("reference_date") or manifest.get("reference_date"),
            "synthetic_test_data": bool(manifest.get("synthetic_test_data", False)),
            "calibration_check": prov.get("calibration_check"),
            "masks": prov.get("masks"),
            "gmm": prov.get("gmm"),
            "jrc": prov.get("jrc"),
            "opera_dswx": prov.get("opera_dswx"),
            "exposure": prov.get("exposure"),
            "processing": prov.get("processing"),
            "context_sources": prov.get("context_sources", []),
            "granules": prov.get("granules", []),
            "otsu_thresholds": prov.get("otsu_thresholds", {}),
            "delta_hh_params": prov.get("delta_hh_params", {"min_delta_hh_db": 3.0, "min_delta_ratio_db": 1.5}),
            "opera_dswx_agreement_pct": prov.get("opera_dswx_agreement_pct"),
            "software": prov.get("software", {}),
            "limitations": prov.get(
                "limitations",
                [
                    "Radar-derived surface/canopy-water indication for inspection, not confirmed flood depth.",
                    "OPERA agreement is inter-sensor agreement, not ground-truth accuracy.",
                    "Hydroperiod expressed as M of N valid NISAR observations, not days flooded.",
                ],
            ),
        },
        aoi_id=aoi_id,
    )


@router.get("/aois/{aoi_id}/context")
def context_layers(aoi_id: str) -> dict:
    """Official regional context (e.g. GSDA/CGWB watersheds & aquifers for Nagpur, SRS §3.1).

    Context only — groundwater is NEVER presented as a direct SAR detection.
    """
    manifest = store.get(aoi_id)
    if manifest is None:
        return envelope(None, aoi_id=aoi_id, status="unknown_aoi", fallback_active=True,
                        warning=f"Unknown AOI '{aoi_id}'.")
    note = "Official hydrogeological / watershed context — not a SAR detection."
    path = store.aoi_dir(aoi_id) / "context_layers.geojson"
    sources = manifest.get("provenance", {}).get("context_sources", [])
    if not path.is_file():
        return envelope(
            {"geojson": {"type": "FeatureCollection", "features": []}, "sources": sources, "note": note},
            aoi_id=aoi_id, fallback_active=True,
            warning="No context_layers.geojson in this AOI pack (export GSDA/CGWB layers to add it).",
        )
    try:
        fc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return envelope(
            {"geojson": {"type": "FeatureCollection", "features": []}, "sources": sources, "note": note},
            aoi_id=aoi_id, fallback_active=True, warning="context_layers.geojson is not valid JSON.",
        )
    return envelope({"geojson": fc, "sources": sources, "note": note}, aoi_id=aoi_id)
