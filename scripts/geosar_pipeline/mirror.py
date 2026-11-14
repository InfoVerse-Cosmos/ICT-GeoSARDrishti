"""Stage 05 — build the frontend offline mirror from the AOI manifests (SRS §7.2 rule 3)."""
from __future__ import annotations

import json
from pathlib import Path

from .common import REPO_ROOT, load_manifest, now_iso

MIRROR = REPO_ROOT / "apps" / "web" / "public" / "fallback_data" / "manifest.json"
KEEP = ("aoi_id", "name", "role", "bounds", "default_zoom", "layers", "polarization", "track_frame",
        "fallback_plan", "acquisition_gaps", "reference_date", "single_pol_mode", "synthetic_test_data",
        "season_summary")


def run(store: Path, out: Path = MIRROR) -> dict:
    aois = []
    # Only AOIs that were really analysed on this machine (manifest + cube) go in the mirror.
    pack_ids = sorted(d.name for d in store.iterdir()
                      if d.is_dir() and (d / "manifest.json").is_file() and (d / "time_series_cube.npz").is_file())         if store.is_dir() else []
    for aoi_id in pack_ids:
        m = load_manifest(aoi_id, store)
        entry = {k: m[k] for k in KEEP if k in m}
        entry["timeline"] = m.get("timeline", [])
        entry["limitations"] = m.get("provenance", {}).get("limitations", [])
        aois.append(entry)
    mirror = {"_note": "Offline mirror (SRS §7.2 rule 3) of the AOIs analysed on this machine. Generated, git-ignored.",
              "generated_at": now_iso(), "aois": aois}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(mirror, indent=2), encoding="utf-8")
    return mirror
