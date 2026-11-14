"""NISAR L2 GCOV HDF5 reader: AOI subset + multilook onto the AOI lat/lon grid (SRS §3.2, §5.1).

Reads only the HDF5 window covering the AOI, so 1-5 GB granules stay cheap.
Needs: h5py, pyproj.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np

from .physics import box_nanmean

GRID = "/science/LSAR/GCOV/grids/frequencyA"
IDENT = "/science/LSAR/identification"


def _val(ds):
    v = ds[()]
    if isinstance(v, bytes):
        return v.decode(errors="ignore")
    if isinstance(v, np.ndarray):
        if v.dtype.kind in "SO":
            return [x.decode(errors="ignore") if isinstance(x, bytes) else str(x) for x in v.ravel()]
        if v.size == 1:
            return v.item()
    if isinstance(v, np.generic):
        return v.item()
    return v


def read_identification(f) -> dict:
    out = {}
    if IDENT not in f:
        return out
    ident = f[IDENT]
    for key in ("trackNumber", "frameNumber", "orbitPassDirection", "zeroDopplerStartTime",
                "zeroDopplerEndTime", "boundingPolygon", "productVersion", "absoluteOrbitNumber",
                "processingType"):
        if key in ident:
            try:
                out[key] = _val(ident[key])
            except Exception:  # noqa: BLE001
                pass
    return out


def polygon_bbox(wkt: str):
    """bbox [w, s, e, n] of a WKT POLYGON. Real NISAR polygons have 3 numbers per vertex
    (lon lat height), synthetic/other ones 2 — so parse vertex by vertex (comma separated)."""
    lons, lats = [], []
    for vertex in str(wkt).replace("(", " ").replace(")", " ").split(","):
        nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", vertex)
        if len(nums) >= 2:
            lons.append(float(nums[0]))
            lats.append(float(nums[1]))
    if len(lons) < 3:
        return None
    return [min(lons), min(lats), max(lons), max(lats)]


def bbox_intersects(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def grid_epsg(grid) -> int:
    if "projection" in grid:
        proj = grid["projection"]
        for attr in ("epsg_code", "epsg"):
            if attr in proj.attrs:
                return int(np.asarray(proj.attrs[attr]).item())
        try:
            return int(_val(proj))
        except Exception:  # noqa: BLE001
            pass
    raise ValueError("could not determine EPSG of GCOV grid (frequencyA/projection)")


def list_polarizations(grid) -> list[str]:
    if "listOfPolarizations" in grid:
        pols = _val(grid["listOfPolarizations"])
        return [pols] if isinstance(pols, str) else list(pols)
    return [p[:2] for p in ("HHHH", "HVHV", "VVVV", "VHVH") if p in grid]


def granule_footprint(path: str | Path):
    import h5py
    with h5py.File(path, "r") as f:
        ident = read_identification(f)
    return polygon_bbox(ident.get("boundingPolygon", "")) if ident else None


def read_subset(path: str | Path, lats: np.ndarray, lons: np.ndarray, res_m: float) -> dict:
    """Returns {'hh','hv' (linear γ0 on AOI grid, NaN outside), 'coverage_pct', 'epsg',
    'native_spacing_m', 'identification', 'polarizations', 'synthetic'}."""
    import h5py
    from pyproj import Transformer

    with h5py.File(path, "r") as f:
        if GRID not in f:
            raise ValueError(f"{Path(path).name}: {GRID} missing — not an L2 GCOV product?")
        grid = f[GRID]
        epsg = grid_epsg(grid)
        x = grid["xCoordinates"][()]
        y = grid["yCoordinates"][()]
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])

        LON, LAT = np.meshgrid(lons, lats)
        tr = Transformer.from_crs(4326, epsg, always_xy=True)
        X, Y = tr.transform(LON, LAT)
        ci = np.rint((X - x[0]) / dx).astype(int)
        ri = np.rint((Y - y[0]) / dy).astype(int)
        inside = (ci >= 0) & (ci < len(x)) & (ri >= 0) & (ri < len(y))
        result = {
            "epsg": epsg,
            "native_spacing_m": abs(dx),
            "identification": read_identification(f),
            "polarizations": list_polarizations(grid),
            "synthetic": bool(f.attrs.get("GEOSAR_SYNTHETIC_TEST_DATA", 0)),
            "coverage_pct": round(100.0 * inside.mean(), 1),
            "hh": None, "hv": None,
        }
        if not inside.any():
            return result

        look = max(1, int(round(res_m / abs(dx))))
        pad = look
        r0 = max(int(ri[inside].min()) - pad, 0)
        r1 = min(int(ri[inside].max()) + pad + 1, len(y))
        c0 = max(int(ci[inside].min()) - pad, 0)
        c1 = min(int(ci[inside].max()) + pad + 1, len(x))

        fill_mask = None
        if "mask" in grid:
            m = grid["mask"][r0:r1, c0:c1]
            # NISAR GCOV `mask` = sub-swath number of valid samples: 0 = not fully focused (invalid),
            # 255 = outside the acquisition extent (fill); 1..n = valid.
            fill_mask = (m == 0) | (m == 255)

        for key, ds_name in (("hh", "HHHH"), ("hv", "HVHV")):
            if ds_name not in grid:
                continue
            block = grid[ds_name][r0:r1, c0:c1].astype("float64")
            block[~np.isfinite(block) | (block <= 0)] = np.nan
            if fill_mask is not None:
                block[fill_mask] = np.nan
            block = box_nanmean(block, look)
            arr = np.full(LAT.shape, np.nan, dtype="float64")
            arr[inside] = block[ri[inside] - r0, ci[inside] - c0]
            result[key] = arr
        return result


def mosaic_subsets(subsets: list[dict]) -> dict:
    """Composite several read_subset() results for ONE date (already on the common AOI grid).

    Merges 'hh' and 'hv' in LINEAR power with a NaN-aware mean across frames: the union of
    coverage is kept and pixels seen by more than one frame are averaged. A None channel is
    treated as absent (a channel merges to None only when every frame lacks it). Returns the
    same dict shape as read_subset (so the pipeline feeds it straight into median3/to_db) with
    coverage_pct = 100 * finite-fraction of the merged hh, epsg = sorted set of input EPSGs,
    native_spacing_m = the smallest input spacing, polarizations = sorted union, synthetic =
    any input synthetic, identification = the first input's, plus a per-frame 'frames' list.
    read_subset and all other functions are left untouched.
    """
    if not subsets:
        raise ValueError("mosaic_subsets: need at least one subset to composite")
    merged: dict = {}
    for key in ("hh", "hv"):
        arrs = [np.asarray(s[key], dtype="float64") for s in subsets if s.get(key) is not None]
        if arrs:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns -> NaN (expected)
                merged[key] = np.nanmean(np.stack(arrs), axis=0)
        else:
            merged[key] = None

    base = merged["hh"] if merged["hh"] is not None else merged["hv"]
    coverage = round(100.0 * float(np.isfinite(base).mean()), 1) if base is not None else 0.0
    epsgs = sorted({s["epsg"] for s in subsets if s.get("epsg") is not None})
    spacings = [s["native_spacing_m"] for s in subsets if s.get("native_spacing_m") is not None]
    pols = sorted({p for s in subsets for p in (s.get("polarizations") or [])})
    merged.update({
        "epsg": epsgs,
        "native_spacing_m": min(spacings) if spacings else None,
        "identification": subsets[0].get("identification"),
        "polarizations": pols,
        "synthetic": any(bool(s.get("synthetic")) for s in subsets),
        "coverage_pct": coverage,
        "frames": [{"coverage_pct": s.get("coverage_pct"), "epsg": s.get("epsg"),
                    "polarizations": s.get("polarizations")} for s in subsets],
    })
    return merged
