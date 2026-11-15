"""Stream only the AOI window of NISAR L2 GCOV granules from NASA Earthdata Cloud (no 7 GB downloads).

Flow:  CMR search (bbox + dates)  ->  pick the same-track stack with the most dates
       ->  for every date read ONLY the AOI window over HTTPS range requests
       ->  save it as a small local GCOV-shaped HDF5 (same dataset paths, same file name)
The rest of the pipeline then reads these mini granules exactly like full ones, so every result
(thresholds, hydroperiod, GMM, OSM exposure) is computed by the same code on the same pixels.

Needs an Earthdata token: EARTHDATA_TOKEN in services/api/.env  (urs.earthdata.nasa.gov -> Generate Token).
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import envcfg
from .common import parse_granule_name, select_best_track

GRID = "/science/LSAR/GCOV/grids/frequencyA"
IDENT = "/science/LSAR/identification"
COLLECTIONS = ("NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_V1")
PAD_PX = 80          # padding around the AOI window (multilook + edge safety)


def _login():
    token = envcfg.get("EARTHDATA_TOKEN")
    if not token:
        raise RuntimeError("EARTHDATA_TOKEN missing: add it to services/api/.env "
                           "(urs.earthdata.nasa.gov -> Generate Token).")
    os.environ["EARTHDATA_TOKEN"] = token
    import earthaccess
    earthaccess.login(strategy="environment")
    return earthaccess


def search(bbox, start: str, end: str, log=print) -> list[dict]:
    """CMR search -> parsed granule dicts (+ 'url', 'collection'), one entry per granule."""
    ea = _login()
    out = []
    for sn in COLLECTIONS:
        results = ea.search_data(short_name=sn, bounding_box=tuple(bbox), temporal=(start, end), count=500)
        for r in results:
            ur = (r.get("umm", {}) or {}).get("GranuleUR") or ""
            g = parse_granule_name(ur)
            if not g:
                continue
            links = r.data_links(access="external")
            url = next((u for u in links if u.endswith(".h5")), None)
            if not url:
                continue
            g.update({"url": url, "collection": sn,
                      "maturity": "PROVISIONAL" if "PROVISIONAL" in sn else "VALIDATED"})
            out.append(g)
    log(f"[stream] CMR: {len(out)} NISAR GCOV granule(s) over the area between {start} and {end}")
    return out


def pick_stack(granules: list[dict], track_frame: str | None = None):
    """Same-track/frame stack with the most dates (SRS 3.2). Returns (track_frame, [granule per date])."""
    return select_best_track(granules, track_frame)


def window_for_bbox(x, y, epsg: int, bbox, pad: int = PAD_PX):
    """(r0, r1, c0, c1) pixel window covering bbox [w,s,e,n] (+pad) in the granule's projected grid."""
    from pyproj import Transformer
    w, s, e, n = bbox
    xs = np.linspace(w, e, 9)
    ys = np.linspace(s, n, 9)
    lon, lat = np.meshgrid(xs, ys)
    X, Y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon.ravel(), lat.ravel())
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    ci = np.rint((np.asarray(X) - x[0]) / dx).astype(int)
    ri = np.rint((np.asarray(Y) - y[0]) / dy).astype(int)
    r0, r1 = max(int(ri.min()) - pad, 0), min(int(ri.max()) + pad + 1, len(y))
    c0, c1 = max(int(ci.min()) - pad, 0), min(int(ci.max()) + pad + 1, len(x))
    if r1 <= r0 or c1 <= c0:          # AOI entirely outside this granule: empty window
        return 0, 0, 0, 0
    return r0, r1, c0, c1


def _scalar(v):
    if isinstance(v, np.ndarray) and v.size == 1:
        v = v.item()
    if isinstance(v, str):
        v = v.encode()
    return v


def subset_one(url: str, out_path: str, bbox, name: str) -> dict:
    """Worker: open ONE remote granule, copy the AOI window of HHHH/HVHV/mask into a mini GCOV file."""
    import h5py
    t0 = time.time()
    out_path = Path(out_path)
    if out_path.exists():
        try:
            with h5py.File(out_path, "r") as f:
                if f.attrs.get("GEOSAR_STREAM_COMPLETE", 0) == 1:
                    return {"name": name, "cached": True, "seconds": 0.0, "mb": out_path.stat().st_size / 1e6}
        except Exception:  # noqa: BLE001 - half-written file from an interrupted run: redo
            pass
    ea = _login()
    remote = ea.open([url])[0]
    tmp = out_path.with_suffix(".part")
    with h5py.File(remote, "r") as h, h5py.File(tmp, "w") as o:
        g = h[GRID]
        x, y = g["xCoordinates"][()], g["yCoordinates"][()]
        proj = g["projection"]
        epsg = int(np.asarray(proj.attrs["epsg_code"]).item()) if "epsg_code" in proj.attrs else int(proj[()])
        r0, r1, c0, c1 = window_for_bbox(x, y, epsg, bbox)
        if r1 - r0 < 2 or c1 - c0 < 2:
            raise RuntimeError(f"{name}: AOI is outside this granule")
        og = o.create_group(GRID)
        og.create_dataset("xCoordinates", data=x[c0:c1])
        og.create_dataset("yCoordinates", data=y[r0:r1])
        pd = og.create_dataset("projection", data=np.int32(epsg))
        pd.attrs["epsg_code"] = np.int32(epsg)
        if "listOfPolarizations" in g:
            og.create_dataset("listOfPolarizations", data=g["listOfPolarizations"][()])
        for ds_name in ("HHHH", "HVHV", "mask"):
            if ds_name in g:
                block = g[ds_name][r0:r1, c0:c1]
                og.create_dataset(ds_name, data=block, chunks=(min(512, block.shape[0]), min(512, block.shape[1])),
                                  compression="gzip", compression_opts=1)
        oi = o.create_group(IDENT)
        if IDENT in h:
            for key, ds in h[IDENT].items():
                if isinstance(ds, h5py.Dataset):
                    try:
                        v = _scalar(ds[()])
                        if isinstance(v, (bytes, int, float, np.generic)) or (isinstance(v, np.ndarray) and v.size < 64):
                            oi.create_dataset(key, data=v)
                    except Exception:  # noqa: BLE001 - non-essential metadata
                        pass
        o.attrs["GEOSAR_STREAM_COMPLETE"] = 1
        o.attrs["GEOSAR_STREAM_WINDOW"] = np.array([r0, r1, c0, c1])
    tmp.replace(out_path)
    return {"name": name, "cached": False, "seconds": round(time.time() - t0, 1),
            "mb": round(out_path.stat().st_size / 1e6, 1), "window": [r1 - r0, c1 - c0]}


def subset_with_retry(url: str, out_path: str, bbox, name: str, attempts: int = 4) -> dict:
    """subset_one with retries: a dropped connection / Wi-Fi switch must not lose a whole date."""
    last = None
    for i in range(attempts):
        try:
            return subset_one(url, out_path, bbox, name)
        except Exception as exc:  # noqa: BLE001 - network errors surface as many different exception types
            last = exc
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{name}: failed after {attempts} attempts ({type(last).__name__}: {str(last)[:120]})")


def fetch_stack(stack: list[dict], bbox, cache_dir: Path, workers: int = 3, log=print) -> list[Path]:
    """Stream the AOI window of every granule in the stack (parallel processes), return the mini-file paths.

    Already-streamed dates are reused from the cache. A date that still fails after retries is skipped with a
    warning; the analysis continues if at least 2 dates succeeded (a same-track change comparison needs 2)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    jobs = {}
    ok_paths, failed = [], []
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(stack)))) as ex:
        for g in stack:
            out = cache_dir / f"{g['granule_id']}.h5"
            jobs[ex.submit(subset_with_retry, g["url"], str(out), list(bbox), g["granule_id"])] = (g, out)
        for fut in as_completed(jobs):
            g, out = jobs[fut]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                failed.append(g["date"])
                log(f"[stream] {g['date']} {g['track_frame']}: FAILED, skipped ({exc})")
                continue
            ok_paths.append(out)
            tag = "cached" if res.get("cached") else f"{res['mb']} MB in {res['seconds']} s (window {res.get('window')})"
            log(f"[stream] {g['date']} {g['track_frame']}: {tag}")
    if len(ok_paths) < 2:
        raise RuntimeError(f"only {len(ok_paths)} date(s) could be streamed ({len(failed)} failed): check the network and retry")
    if failed:
        log(f"[stream] WARNING: continuing without {sorted(failed)}; rerun to retry them (finished dates are cached)")
    return sorted(ok_paths)
