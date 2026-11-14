"""Synthetic NISAR L2 GCOV generator — for PIPELINE TESTING ONLY.

Writes small HDF5 files with the real GCOV layout (science/LSAR/GCOV/grids/
frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection,listOfPolarizations},
science/LSAR/identification/*) covering an AOI in UTM, using the team's real
granule NAMES so the data gate / same-track logic is exercised exactly.

Every file is stamped GEOSAR_SYNTHETIC_TEST_DATA=1 and the pipeline propagates
that flag to the manifest + UI badge, so synthetic output can never be mistaken
for real NISAR observations.

Scene (Assam-like): a permanent river channel, a seasonal beel that shrinks
through October, a flooded tall-grass belt (double-bounce, drying by Nov) and a
paddy block, on a dry upland background.

    python scripts/make_synthetic_gcov.py --out scripts/_work/synthetic_h5 [--aoi aoi_assam_majuli]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline.common import AOI_BOUNDS, parse_granule_name  # noqa: E402

REAL_NAMES = [
    "NISAR_L2_PR_GCOV_032_063_D_076_2005_DHDH_M_20261004T135735_20261004T135809_P05023_N_F_J_001.h5",
    "NISAR_L2_PR_GCOV_032_135_D_076_2005_DHDH_M_20261009T134915_20261009T134950_P05023_N_F_J_001.h5",
    "NISAR_L2_PR_GCOV_033_063_D_076_2005_DHDH_M_20261016T135735_20261016T135809_P05023_N_F_J_001.h5",
    "NISAR_L2_PR_GCOV_034_135_D_076_2005_DHDH_M_20261102T134916_20261102T134950_P05036_N_F_J_001.h5",
]

# per-date wetness state (0 = dry reference ... 1 = peak)
WETNESS = {"2026-10-04": 1.0, "2026-10-09": 0.8, "2026-10-16": 0.6, "2026-11-02": 0.0}


def utm_epsg(lon: float, lat: float) -> int:
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def make_scene(lon, lat, bounds, wet, rng, single_pol=False):
    """Returns linear γ0 HH, HV for a scene with given wetness."""
    west, south, east, north = bounds
    u = (lon - west) / (east - west)            # 0..1 west->east
    v = (lat - south) / (north - south)         # 0..1 south->north
    hh_db = np.full(lon.shape, -9.0)            # dry upland
    hv_db = np.full(lon.shape, -15.0)

    river_centre = 0.45 + 0.08 * np.sin(u * 6.0)
    river = np.abs(v - river_centre) < 0.05
    beel = ((u - 0.25) ** 2 + (v - 0.75) ** 2) < (0.06 + 0.06 * wet) ** 2
    grass = (np.abs(v - river_centre - 0.13) < 0.04) & (u > 0.3) & (u < 0.8)
    paddy = (u > 0.65) & (u < 0.9) & (v > 0.12) & (v < 0.3)

    hh_db[grass] = -11.8 + 4.6 * wet            # double-bounce surge when flooded
    hv_db[grass] = -17.0 + 0.3 * wet
    hh_db[paddy] = -12.5 + 3.8 * wet
    hv_db[paddy] = -19.0 + 0.2 * wet
    hh_db[beel] = -21.0
    hv_db[beel] = -28.0
    hh_db[river] = -23.0
    hv_db[river] = -30.0

    # multiplicative speckle (gamma, 4 looks)
    sp = rng.gamma(4.0, 1 / 4.0, size=(2, *lon.shape))
    hh = 10 ** (hh_db / 10) * sp[0]
    hv = 10 ** (hv_db / 10) * sp[1]
    return hh.astype("float32"), (None if single_pol else hv.astype("float32"))


def write_granule(path: Path, name: str, bounds, spacing_m=30.0, seed=0, single_pol=False):
    import h5py
    from pyproj import Transformer

    g = parse_granule_name(name)
    west, south, east, north = bounds
    pad = 0.05
    epsg = utm_epsg((west + east) / 2, (south + north) / 2)
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = tr.transform([west - pad, east + pad, west - pad, east + pad],
                          [south - pad, south - pad, north + pad, north + pad])
    x = np.arange(min(xs), max(xs), spacing_m)
    y = np.arange(max(ys), min(ys), -spacing_m)       # north-up
    X, Y = np.meshgrid(x, y)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)
    LON, LAT = inv.transform(X, Y)
    wet = WETNESS.get(g["date"], 0.5)
    hh, hv = make_scene(LON, LAT, bounds, wet, np.random.default_rng(seed), single_pol)

    with h5py.File(path, "w") as f:
        f.attrs["GEOSAR_SYNTHETIC_TEST_DATA"] = 1
        grid = f.create_group("/science/LSAR/GCOV/grids/frequencyA")
        grid.create_dataset("HHHH", data=hh, chunks=True, compression="gzip")
        if hv is not None:
            grid.create_dataset("HVHV", data=hv, chunks=True, compression="gzip")
        grid.create_dataset("xCoordinates", data=x)
        grid.create_dataset("yCoordinates", data=y)
        proj = grid.create_dataset("projection", data=np.uint32(epsg))
        proj.attrs["epsg_code"] = epsg
        pols = [b"HH"] if hv is None else [b"HH", b"HV"]
        grid.create_dataset("listOfPolarizations", data=np.array(pols, dtype="S2"))
        ident = f.create_group("/science/LSAR/identification")
        ident.create_dataset("trackNumber", data=np.uint32(g["track"]))
        ident.create_dataset("frameNumber", data=np.uint16(g["frame"]))
        ident.create_dataset("orbitPassDirection", data=np.bytes_(g["direction"].title()))
        ident.create_dataset("zeroDopplerStartTime", data=np.bytes_(g["start_utc"].replace("Z", ".000000")))
        poly = (f"POLYGON(({west - pad} {south - pad}, {east + pad} {south - pad}, {east + pad} {north + pad}, "
                f"{west - pad} {north + pad}, {west - pad} {south - pad}))")
        ident.create_dataset("boundingPolygon", data=np.bytes_(poly))
        ident.create_dataset("productVersion", data=np.bytes_(g["crid"]))


def write_ancillary(out: Path, bounds, res_deg: float = 0.0009):
    """Synthetic WorldCover / JRC occurrence / OPERA DSWx WTR GeoTIFFs (EPSG:4326) matching the scene."""
    import rasterio
    from rasterio.transform import from_origin

    west, south, east, north = bounds
    pad = 0.02
    w, n = west - pad, north + pad
    cols = int((east - west + 2 * pad) / res_deg)
    rows = int((north - south + 2 * pad) / res_deg)
    lon = w + (np.arange(cols) + 0.5) * res_deg
    lat = n - (np.arange(rows) + 0.5) * res_deg
    LON, LAT = np.meshgrid(lon, lat)
    u, v = (LON - west) / (east - west), (LAT - south) / (north - south)
    rc = 0.45 + 0.08 * np.sin(u * 6.0)
    river = np.abs(v - rc) < 0.05
    beel = ((u - 0.25) ** 2 + (v - 0.75) ** 2) < 0.12 ** 2
    grass = (np.abs(v - rc - 0.13) < 0.04) & (u > 0.3) & (u < 0.8)
    paddy = (u > 0.65) & (u < 0.9) & (v > 0.12) & (v < 0.3)

    wc = np.full(LON.shape, 30, np.uint8)             # grassland background
    wc[paddy] = 40
    wc[grass] = 90
    wc[river] = 80
    jrc = np.zeros(LON.shape, np.uint8)
    jrc[river] = 95
    jrc[beel & ~river] = 10                           # beel rarely seen as water optically -> "unusual"
    dswx = np.zeros(LON.shape, np.uint8)              # DSWx WTR: 0 not water, 1 open water
    dswx[river | beel] = 1
    dswx[(u < 0.05)] = 255                            # a no-data strip

    tr = from_origin(w, n, res_deg, res_deg)
    for name, arr, nodata in (("worldcover.tif", wc, 0), ("jrc_occurrence.tif", jrc, None), ("dswx_wtr.tif", dswx, 255)):
        with rasterio.open(out / name, "w", driver="GTiff", height=rows, width=cols, count=1, dtype=arr.dtype,
                           crs="EPSG:4326", transform=tr, nodata=nodata) as ds:
            ds.write(arr, 1)
        print(f"[synthetic] {name}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--aoi", default="aoi_assam_majuli", choices=list(AOI_BOUNDS))
    p.add_argument("--spacing-m", type=float, default=30.0)
    p.add_argument("--single-pol", action="store_true", help="omit HVHV to exercise Single-Pol HH mode")
    p.add_argument("--ancillary", action="store_true",
                   help="also write synthetic worldcover.tif / jrc_occurrence.tif / dswx_wtr.tif (needs rasterio)")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(REAL_NAMES):
        write_granule(out / name, name, AOI_BOUNDS[args.aoi], args.spacing_m, seed=i, single_pol=args.single_pol)
        print(f"[synthetic] {name}")
    if args.ancillary:
        write_ancillary(out, AOI_BOUNDS[args.aoi])


if __name__ == "__main__":
    main()
