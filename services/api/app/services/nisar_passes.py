"""NASA CMR catalogue search: which NISAR GCOV passes exist over an area and period (metadata only, no download)."""
from __future__ import annotations

import re
from collections import defaultdict

import httpx

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
COLLECTIONS = ("NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_V1")
_NAME = re.compile(r"NISAR_L2_PR_GCOV_(?P<cycle>\d{3})_(?P<track>\d{3})_[AD]_(?P<frame>\d{3})_\w+?_(?P<start>\d{8})T\d{6}_")


def find_passes(bbox: list[float], start: str, end: str, timeout: float = 20.0) -> dict:
    """Group the passes by track/frame (only same-track passes can be compared). Recommended = most dates."""
    w, s, e, n = bbox
    seen: dict[tuple[str, str], dict] = {}
    for short in COLLECTIONS:
        r = httpx.get(CMR, params={"short_name": short, "bounding_box": f"{w},{s},{e},{n}",
                                   "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "page_size": 200},
                      timeout=timeout)
        r.raise_for_status()
        for entry in r.json().get("feed", {}).get("entry", []):
            ur = entry.get("producer_granule_id") or entry.get("title") or ""
            m = _NAME.search(ur)
            if not m:
                continue
            d = m["start"]
            date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            tf = f"{m['track']}/{m['frame']}"
            maturity = "PROVISIONAL" if "PROVISIONAL" in short else "VALIDATED"
            seen.setdefault((tf, date), {"date": date, "maturity": maturity, "granule_id": ur.removesuffix(".h5")})
    groups: dict[str, list] = defaultdict(list)
    for (tf, _), p in seen.items():
        groups[tf].append(p)
    out = [{"track_frame": tf, "passes": sorted(ps, key=lambda x: x["date"])} for tf, ps in groups.items()]
    out.sort(key=lambda g: (-len(g["passes"]), g["passes"][-1]["date"]), reverse=False)
    out.sort(key=lambda g: (len(g["passes"]), g["passes"][-1]["date"]), reverse=True)
    return {"groups": out, "recommended": out[0]["track_frame"] if out else None}