"""Constants, AOI grid, granule-name parsing, manifest I/O and a dependency-free PNG writer."""
from __future__ import annotations

import json
import math
import os
import re
import struct
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_STORE = REPO_ROOT / "services" / "api" / "data_store"
WORK_DIR = REPO_ROOT / "scripts" / "_work"

AOI_BOUNDS = {  # [west, south, east, north] WGS84 (SRS §3.1)
    "aoi_assam_majuli": [93.90, 26.75, 94.30, 27.05],
    "aoi_nagpur_kanhan": [78.95, 21.15, 79.35, 21.45],
}

# --- SRS physics constants (§2, §5.2, §5.5) ---------------------------------
MIN_DELTA_HH_DB = 3.0
MIN_DELTA_RATIO_DB = 1.5
# Calibrated on the real NISAR scenes (14 Nov 2026): the raw whole-scene Otsu lands at about -12 dB
# (biased up by the huge land mode) and in Nagpur there is no water mode at all, so the SRS range
# [-22, -13] let the threshold settle on the darkest LAND. The upper bounds are therefore capped at the
# SRS §2 "typical open water" level (HH < -16 dB; HV < -22 dB, noise floor is ~ -25 dB), and Otsu is
# run on the dark tail only (HH < -10 dB, HV < -16 dB) so it separates water from the intermediate mode.
OTSU_HH_RANGE_DB = (-22.0, -16.0)
OTSU_HV_RANGE_DB = (-30.0, -22.0)
OTSU_TAIL_HH_DB = -10.0
OTSU_TAIL_HV_DB = -16.0
LINEAR_FLOOR = 1e-5
MIN_WET_OBSERVATIONS = 3
JRC_UNUSUAL_PCT = 20.0
MAX_SLOPE_DEG = 5.0

# PROVISIONAL -> VALIDATED transition window is 21-23 Oct 2026 (SRS §3.2).
VALIDATED_FROM = os.environ.get("GEOSAR_VALIDATED_FROM", "2026-10-23")
ACQUISITION_GAP = ("2026-07-27", "2026-08-10")

# ESA WorldCover classes (SRS §5.2)
WC_CROPLAND = 40
WC_VEGETATION = {10, 20, 30, 40, 90, 95}

REGIME_NAMES = [
    "Permanent River / Deep Channel",
    "Seasonal Open Floodplain / Beel",
    "Seasonally Flooded Canopy / Tall Grassland",
    "Seasonal Paddy-Like Inundation Cycle",
    "Stable Dry Upland / Levee",
]


def data_store(override: str | Path | None = None) -> Path:
    return Path(override or os.environ.get("GEOSAR_DATA_STORE") or DEFAULT_DATA_STORE)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- granule names ------------------------------------------------------------
GRANULE_RE = re.compile(
    r"NISAR_(?P<level>L\d)_(?P<ptype>[A-Z]{2})_(?P<product>GCOV)_"
    r"(?P<cycle>\d{3})_(?P<track>\d{3})_(?P<direction>[AD])_(?P<frame>\d{3})_"
    r"(?P<mode>\d{4})_(?P<pol>[A-Z]{4})_(?P<obs>[A-Z])_"
    r"(?P<start>\d{8}T\d{6})_(?P<end>\d{8}T\d{6})_"
    r"(?P<crid>[A-Z]\d{5})_(?P<acc>[A-Z])_(?P<cov>[A-Z])_(?P<loc>[A-Z])_(?P<ctr>\d{3})"
)


def maturity_for_date(date: str) -> str:
    return "VALIDATED" if date >= VALIDATED_FROM else "PROVISIONAL"


def parse_granule_name(name: str) -> dict | None:
    """Parses a NISAR L2 GCOV product name. Returns None if it is not one."""
    m = GRANULE_RE.search(Path(name).name)
    if not m:
        return None
    g = m.groupdict()
    start = datetime.strptime(g["start"], "%Y%m%dT%H%M%S")
    date = start.strftime("%Y-%m-%d")
    granule_id = m.group(0)
    return {
        "granule_id": granule_id,
        "date": date,
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cycle": int(g["cycle"]),
        "track": int(g["track"]),
        "frame": int(g["frame"]),
        "direction": "DESCENDING" if g["direction"] == "D" else "ASCENDING",
        "track_frame": f"{int(g['track']):03d}/{int(g['frame']):03d}",
        "mode": g["mode"],
        "pol_code": g["pol"],
        # D?=dual-pol (HH+HV for DH), S?=single-pol, Q?=quad-pol; first 2 chars = frequency A.
        "polarization": {"DH": "HH+HV", "SH": "HH", "QP": "HH+HV", "DV": "VV+VH", "SV": "VV"}.get(
            g["pol"][:2], g["pol"][:2]),
        "crid": g["crid"],
        "maturity": maturity_for_date(date),
    }


def group_by_track(granules: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for g in granules:
        groups[g["track_frame"]].append(g)
    for v in groups.values():
        v.sort(key=lambda g: g["start_utc"])
    return dict(groups)


def group_by_track_number(granules: list[dict]) -> dict[int, list[dict]]:
    """Group granules by track NUMBER only (ignoring frame); each list sorted by start_utc.

    Used by the multi-frame mosaic path to gather adjacent frames of the same track so they
    can be composited per date. group_by_track / select_best_track are left untouched.
    """
    groups: dict[int, list[dict]] = defaultdict(list)
    for g in granules:
        groups[g["track"]].append(g)
    for v in groups.values():
        v.sort(key=lambda g: g["start_utc"])
    return dict(groups)


def select_best_track(granules: list[dict], track_frame: str | None = None) -> tuple[str, list[dict]]:
    """Same-track stack with the most dates (ties -> latest start). SRS §3.2."""
    groups = group_by_track(granules)
    if not groups:
        raise ValueError("no NISAR GCOV granules found")
    if track_frame:
        if track_frame not in groups:
            raise ValueError(f"track/frame {track_frame} not in {sorted(groups)}")
        return track_frame, groups[track_frame]
    best = max(groups, key=lambda k: (len({g['date'] for g in groups[k]}), groups[k][-1]["start_utc"]))
    # one granule per date
    seen, stack = set(), []
    for g in groups[best]:
        if g["date"] not in seen:
            seen.add(g["date"])
            stack.append(g)
    return best, stack


def fallback_plan(n_dates: int, dual_pol: bool) -> str:
    """SRS §3.3 ladder: A full season, B single-pol/noisy, C 2-3(5) dates, D no usable stack."""
    if n_dates < 2:
        return "D"
    if n_dates < 6:
        return "C"
    return "A" if dual_pol else "B"


# --- AOI grid -------------------------------------------------------------------
def aoi_grid(bounds: list[float], res_m: float = 100.0):
    """Regular lat/lon grid over the AOI. Returns rows, cols, lat centres (N->S), lon centres (W->E)."""
    west, south, east, north = bounds
    lat_c = (south + north) / 2
    rows = max(2, int(round((north - south) * 111_320 / res_m)))
    cols = max(2, int(round((east - west) * 111_320 * math.cos(math.radians(lat_c)) / res_m)))
    lats = north - (np.arange(rows) + 0.5) * (north - south) / rows
    lons = west + (np.arange(cols) + 0.5) * (east - west) / cols
    return rows, cols, lats, lons


def pixel_area_km2(bounds: list[float], rows: int, cols: int) -> float:
    west, south, east, north = bounds
    h = (north - south) * 111.32 / rows
    w = (east - west) * 111.32 * math.cos(math.radians((south + north) / 2)) / cols
    return h * w


# --- manifest -------------------------------------------------------------------
def manifest_path(aoi_id: str, store: Path) -> Path:
    return store / aoi_id / "manifest.json"


def load_manifest(aoi_id: str, store: Path) -> dict:
    p = manifest_path(aoi_id, store)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"aoi_id": aoi_id, "bounds": AOI_BOUNDS.get(aoi_id), "default_zoom": 9,
            "acquisition_gaps": [f"{ACQUISITION_GAP[0]}/{ACQUISITION_GAP[1]}"], "timeline": [],
            "provenance": {}}


def save_manifest(aoi_id: str, store: Path, manifest: dict) -> Path:
    p = manifest_path(aoi_id, store)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, default=_json_default), encoding="utf-8")
    return p


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


# --- PNG (no Pillow needed) -------------------------------------------------------
def encode_png_rgba(rgba: np.ndarray) -> bytes:
    rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
    h, w, c = rgba.shape
    assert c == 4
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def write_png(path: Path, rgba: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_png_rgba(rgba))


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mask_to_rgba(layers: list[tuple[np.ndarray, str, int]], shape) -> np.ndarray:
    """layers: [(bool_mask, '#RRGGBB', alpha)], later layers paint over earlier ones."""
    out = np.zeros((*shape, 4), dtype=np.uint8)
    for mask, colour, alpha in layers:
        r, g, b = hex_to_rgb(colour)
        out[mask] = (r, g, b, alpha)
    return out


# --- optional GeoTIFF sampling (WorldCover / JRC / DSWx / DEM) ---------------------
def sample_geotiff(path: str | Path, lats: np.ndarray, lons: np.ndarray, band: int = 1) -> np.ndarray:
    """Nearest-neighbour sample of a GeoTIFF onto the AOI lat/lon grid (needs rasterio)."""
    import rasterio
    from rasterio.warp import transform as warp_transform

    LON, LAT = np.meshgrid(lons, lats)
    with rasterio.open(path) as ds:
        if ds.crs and ds.crs.to_epsg() != 4326:
            xs, ys = warp_transform("EPSG:4326", ds.crs, LON.ravel().tolist(), LAT.ravel().tolist())
            X, Y = np.asarray(xs).reshape(LON.shape), np.asarray(ys).reshape(LAT.shape)
        else:
            X, Y = LON, LAT
        inv = ~ds.transform
        cols, rows = inv * (X, Y)
        rows, cols = np.floor(rows).astype(int), np.floor(cols).astype(int)
        r0, r1 = max(rows.min(), 0), min(rows.max() + 1, ds.height)
        c0, c1 = max(cols.min(), 0), min(cols.max() + 1, ds.width)
        out = np.full(LAT.shape, np.nan, dtype="float32")
        if r1 <= r0 or c1 <= c0:
            return out
        block = ds.read(band, window=((r0, r1), (c0, c1))).astype("float32")
        nodata = ds.nodata
        inside = (rows >= r0) & (rows < r1) & (cols >= c0) & (cols < c1)
        out[inside] = block[rows[inside] - r0, cols[inside] - c0]
        if nodata is not None:
            out[out == nodata] = np.nan
        return out
