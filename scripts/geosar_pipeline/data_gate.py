"""Stage 01 — data gate: find GCOV granules, pick the same-track stack, lock the manifest (SRS §3, §9 P1)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .common import (AOI_BOUNDS, WORK_DIR, fallback_plan, load_manifest, now_iso, parse_granule_name,
                     save_manifest, select_best_track, group_by_track)


def granules_from_names(names: list[str]) -> list[dict]:
    out = []
    for n in names:
        g = parse_granule_name(n.strip())
        if g:
            out.append(g)
    return out


def granules_from_dir(h5_dir: str | Path, aoi_id: str | None = None, check_footprint: bool = True) -> list[dict]:
    """Index downloaded .h5 files; optionally drop granules whose footprint misses the AOI."""
    paths = sorted(Path(h5_dir).glob("*.h5"))
    out = []
    for p in paths:
        g = parse_granule_name(p.name)
        if not g:
            continue
        g["path"] = str(p)
        if check_footprint and aoi_id:
            try:
                from .gcov import bbox_intersects, granule_footprint
            except ImportError:
                granule_footprint = None
            if granule_footprint is not None:
                try:
                    fp = granule_footprint(p)
                except Exception as exc:  # noqa: BLE001 - truncated/corrupt/unreadable .h5 must not abort the gate
                    print(f"[01] warning: skipping {p.name} — cannot read it "
                          f"({type(exc).__name__}). Re-download it if the file is truncated.")
                    g["skipped"] = "unreadable or truncated granule"
                else:
                    g["footprint_bbox"] = fp
                    if fp and not bbox_intersects(fp, AOI_BOUNDS[aoi_id]):
                        g["skipped"] = "footprint does not intersect AOI"
        out.append(g)
    return out


def granules_from_dirs(dirs, aoi_id: str | None = None, check_footprint: bool = True) -> list[dict]:
    """Union of granules_from_dir over several folders, de-duplicated by resolved path and
    granule_id (so the repo-root DATA/ and an extra-frames subfolder can be fed together
    without double-counting). granules_from_dir and lock are unchanged."""
    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    out: list[dict] = []
    for d in dirs:
        for g in granules_from_dir(d, aoi_id, check_footprint):
            rp = str(Path(g["path"]).resolve()) if g.get("path") else None
            gid = g.get("granule_id")
            if (rp is not None and rp in seen_paths) or (gid is not None and gid in seen_ids):
                continue
            if rp is not None:
                seen_paths.add(rp)
            if gid is not None:
                seen_ids.add(gid)
            out.append(g)
    return out


def granules_from_earthaccess(aoi_id: str, short_name: str, temporal=("2026-06-01", "2026-11-30")) -> list[dict]:
    """Live CMR search via earthaccess (needs EARTHDATA_USERNAME/PASSWORD or ~/.netrc)."""
    import earthaccess

    earthaccess.login(strategy="environment" if os.environ.get("EARTHDATA_USERNAME") else "netrc")
    out = []
    for name_ in [n.strip() for n in short_name.split(",") if n.strip()]:
        results = earthaccess.search_data(short_name=name_, bounding_box=tuple(AOI_BOUNDS[aoi_id]),
                                          temporal=temporal, count=500)
        for r in results:
            g = parse_granule_name(r.get("umm", {}).get("GranuleUR") or "")
            if g:
                # ASF keeps maturity levels in separate collections -> authoritative maturity.
                g["maturity"] = "PROVISIONAL" if "PROVISIONAL" in name_.upper() else "VALIDATED"
                g["collection"] = name_
                g["data_links"] = r.data_links()
                out.append(g)
    return out


def download(granules: list[dict], dest: str | Path) -> list[str]:
    import earthaccess
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    links = [l for g in granules for l in g.get("data_links", []) if l.endswith(".h5")]
    return [str(p) for p in earthaccess.download(links, str(dest))]


def lock(aoi_id: str, granules: list[dict], store: Path, track_frame: str | None = None,
         dry_run: bool = False) -> dict:
    """Select the best same-track stack and write it into the AOI manifest timeline."""
    usable = [g for g in granules if not g.get("skipped")]
    tf, stack = select_best_track(usable, track_frame)
    dual_pol = all(g["polarization"] == "HH+HV" for g in stack)
    plan = fallback_plan(len(stack), dual_pol)

    report = {
        "aoi_id": aoi_id,
        "generated_at": now_iso(),
        "selected_track_frame": tf,
        "fallback_plan": plan,
        "dual_pol": dual_pol,
        "tracks_found": {k: [g["date"] for g in v] for k, v in group_by_track(usable).items()},
        "skipped": [{"granule_id": g["granule_id"], "reason": g["skipped"]} for g in granules if g.get("skipped")],
        "stack": [{k: g[k] for k in ("granule_id", "date", "track_frame", "polarization", "maturity", "crid",
                                     "cycle", "direction")} for g in stack],
    }

    if not dry_run:
        m = load_manifest(aoi_id, store)
        m["track_frame"] = tf
        m["polarization"] = "HH+HV" if dual_pol else "HH"
        m["fallback_plan"] = plan
        m["timeline"] = [{"date": g["date"], "granule_id": g["granule_id"], "track_frame": tf,
                          "polarization": g["polarization"], "maturity": g["maturity"], "crid": g["crid"]}
                         for g in stack]
        prov = m.setdefault("provenance", {})
        prov["granules"] = [g["granule_id"] for g in stack]
        prov["data_gate"] = {k: report[k] for k in ("generated_at", "selected_track_frame", "tracks_found",
                                                     "skipped")}
        m.pop("_note", None)
        save_manifest(aoi_id, store, m)

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    (WORK_DIR / f"{aoi_id}_data_gate.json").write_text(json.dumps(report, indent=2))
    return report
