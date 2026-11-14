"""Loader for AOI data packs built from the user's own NISAR granules (SRS §6.1).

Only AOIs that were actually analysed on this machine (a manifest.json AND a
time_series_cube.npz in the data store) are listed. Nothing is shipped, mocked or
injected as a default: an empty store simply means "drop NISAR .h5 files in DATA/
and run analyze". The directory is re-scanned when packs change, so a freshly built
AOI appears without restarting the API.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DATA_STORE


def _pack_ready(aoi_dir: Path) -> bool:
    return (aoi_dir / "manifest.json").is_file() and (aoi_dir / "time_series_cube.npz").is_file()


class DataStore:
    def __init__(self) -> None:
        self._manifests: dict[str, dict[str, Any]] = {}
        self._signature: tuple | None = None

    # -- discovery ---------------------------------------------------------------
    def _scan_signature(self) -> tuple:
        """Cheap fingerprint (pack names + manifest/cube mtimes) used to detect new or rebuilt packs."""
        if not DATA_STORE.is_dir():
            return ()
        sig = []
        for d in sorted(p for p in DATA_STORE.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            try:
                if _pack_ready(d):
                    sig.append((d.name, (d / "manifest.json").stat().st_mtime_ns,
                                (d / "time_series_cube.npz").stat().st_mtime_ns))
            except OSError:
                continue
        return tuple(sig)

    def load(self) -> None:
        self._manifests = {}
        if DATA_STORE.is_dir():
            for aoi_dir in sorted(p for p in DATA_STORE.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
                if not _pack_ready(aoi_dir):
                    continue
                try:
                    manifest = json.loads((aoi_dir / "manifest.json").read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue  # corrupt pack -> not listed (never replaced by made-up data)
                # The folder name is the single source of truth for an AOI's identity. Forcing
                # aoi_id to match the folder keeps /health, get(), aoi_dir() and the UI in sync,
                # so renaming or deleting a folder cleanly renames/removes the AOI instead of
                # leaving the stale aoi_id baked into manifest.json on disk.
                manifest["aoi_id"] = aoi_dir.name
                self._manifests[aoi_dir.name] = manifest
        self._signature = self._scan_signature()

    def refresh(self) -> None:
        """Re-scan only if packs were added/removed/rebuilt since the last load."""
        if self._signature is None or self._scan_signature() != self._signature:
            self.load()

    @property
    def using_fallback(self) -> bool:
        """True when no analysed AOI exists yet (nothing to show)."""
        return not self._manifests

    @property
    def data_dir(self) -> Path:
        return DATA_STORE

    def list_aois(self) -> list[dict[str, Any]]:
        self.refresh()
        return list(self._manifests.values())

    def get(self, aoi_id: str) -> dict[str, Any] | None:
        self.refresh()
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
