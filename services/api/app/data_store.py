"""In-memory loader for committed AOI data packs (SRS §6.1).

Manifests are loaded once at startup for <20ms responses. Missing packs
degrade to a static default dictionary rather than raising.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DATA_STORE

# Static default used when a manifest file is missing entirely (SRS §7.1 fallbacks).
_DEFAULT_AOIS: dict[str, dict[str, Any]] = {
    "aoi_assam_majuli": {
        "aoi_id": "aoi_assam_majuli",
        "name": "Majuli-Kaziranga Floodplain, Brahmaputra Valley, Assam",
        "role": "Primary CH-06 Monsoon Time-Series Showcase",
        "bounds": [93.90, 26.75, 94.30, 27.05],
        "default_zoom": 9,
        "layers": ["open_water", "flooded_veg", "hydroperiod", "gmm_regimes", "jrc_anomaly"],
        "fallback_plan": "A",
        "timeline": [],
    },
    "aoi_nagpur_kanhan": {
        "aoi_id": "aoi_nagpur_kanhan",
        "name": "Kanhan-Pench / Wainganga Corridor, Nagpur District, Maharashtra",
        "role": "Local Watershed & Multi-Source Context Showcase",
        "bounds": [78.95, 21.15, 79.35, 21.45],
        "default_zoom": 9,
        "layers": ["open_water", "hydroperiod", "context_layers"],
        "fallback_plan": "A",
        "timeline": [],
    },
}


class DataStore:
    def __init__(self) -> None:
        self._manifests: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> None:
        self._manifests = {}
        if DATA_STORE.exists():
            for aoi_dir in sorted(p for p in DATA_STORE.iterdir() if p.is_dir()):
                manifest = aoi_dir / "manifest.json"
                if manifest.exists():
                    try:
                        self._manifests[aoi_dir.name] = json.loads(manifest.read_text())
                    except json.JSONDecodeError:
                        # Corrupt pack -> fall back to default entry if we have one.
                        if aoi_dir.name in _DEFAULT_AOIS:
                            self._manifests[aoi_dir.name] = _DEFAULT_AOIS[aoi_dir.name]
        # Ensure the two shipped AOIs always exist, even with no packs on disk.
        for aoi_id, default in _DEFAULT_AOIS.items():
            self._manifests.setdefault(aoi_id, default)
        self._loaded = True

    @property
    def using_fallback(self) -> bool:
        """True when no real manifest.json files were found on disk."""
        return not DATA_STORE.exists() or not any(
            (DATA_STORE / aoi / "manifest.json").exists() for aoi in self._manifests
        )

    def list_aois(self) -> list[dict[str, Any]]:
        return list(self._manifests.values())

    def get(self, aoi_id: str) -> dict[str, Any] | None:
        return self._manifests.get(aoi_id)

    def aoi_dir(self, aoi_id: str) -> Path:
        return DATA_STORE / aoi_id

    def has_cube(self, aoi_id: str) -> bool:
        return (self.aoi_dir(aoi_id) / "time_series_cube.npz").is_file()

    def pack_status(self, aoi_id: str) -> dict[str, Any]:
        """What the offline pipeline has produced for this AOI (shown in /health)."""
        d = self.aoi_dir(aoi_id)
        m = self._manifests.get(aoi_id, {})
        overlays = sorted(p.name for p in (d / "overlays").glob("*.png")) if (d / "overlays").is_dir() else []
        locked = [t for t in m.get("timeline", []) if t.get("granule_id") not in (None, "TBD")]
        return {
            "granules_locked": len(locked),
            "timeline_dates": len(m.get("timeline", [])),
            "cube": self.has_cube(aoi_id),
            "overlays": len(overlays),
            "exposure": (d / "osm_exposure.geojson").is_file(),
            "context_layers": (d / "context_layers.geojson").is_file(),
            "fallback_plan": m.get("fallback_plan"),
            "synthetic_test_data": bool(m.get("synthetic_test_data", False)),
        }


store = DataStore()
