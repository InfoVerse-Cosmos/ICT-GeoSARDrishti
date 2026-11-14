"""Test helpers: fake httpx client + synthetic NISAR time-series cube builder."""
from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np

DATES = [
    "2026-06-14", "2026-06-26", "2026-07-10", "2026-07-22", "2026-08-15",
    "2026-09-08", "2026-10-02", "2026-10-26", "2026-11-07",
]


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://fake")
            raise httpx.HTTPStatusError(
                "fake error", request=req, response=httpx.Response(self.status_code, request=req)
            )

    def json(self) -> dict:
        return self._payload


def make_fake_async_client(*, response: FakeResponse | None = None, exc: Exception | None = None,
                           calls: list | None = None):
    """Returns a drop-in replacement for httpx.AsyncClient that records calls."""

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            if calls is not None:
                calls.append({"init": kwargs})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def _do(self, url, **kwargs):
            if calls is not None:
                calls.append({"url": url, **kwargs})
            if exc is not None:
                raise exc
            return response

        get = _do
        post = _do

    return FakeAsyncClient


def write_cube(root: Path, aoi_id: str, rows: int = 10, cols: int = 10, *, full: bool = True) -> Path:
    """Writes a synthetic time_series_cube.npz with known values at the corners.

    Pixel (0,0)   = NW corner: flooded-vegetation-like trajectory, 6/9 wet, regime idx 2.
    Pixel (-1,-1) = SE corner: dry upland, 0/9 wet, regime idx 4.
    """
    t = len(DATES)
    hh = np.full((t, rows, cols), -12.0, dtype=np.float32)
    hv = np.full((t, rows, cols), -18.0, dtype=np.float32)
    # NW pixel: dry baseline -11.8 dB, surge to -7.2 dB on 2026-07-22 (SRS §7.3 example).
    hh[:, 0, 0] = [-11.5, -10.0, -8.0, -7.2, -9.0, -9.5, -10.5, -11.6, -11.8]
    hv[:, 0, 0] = [-18.0, -18.2, -18.5, -18.4, -18.1, -18.0, -18.0, -18.1, -18.0]

    arrays = {"hh_db": hh}
    if full:
        m_open = np.zeros((rows, cols), dtype=np.int16)
        m_fveg = np.zeros((rows, cols), dtype=np.int16)
        n_valid = np.full((rows, cols), t, dtype=np.int16)
        m_open[0, 0], m_fveg[0, 0] = 2, 4
        gmm = np.full((rows, cols), 4, dtype=np.int8)
        gmm[0, 0] = 2
        jrc = np.full((rows, cols), 0.0, dtype=np.float32)
        jrc[0, 0] = 14.0
        worldcover = np.full((rows, cols), 40, dtype=np.int16)
        worldcover[0, 0] = 90
        arrays.update(
            hv_db=hv, m_open=m_open, m_fveg=m_fveg, n_valid=n_valid,
            gmm=gmm, jrc=jrc, worldcover=worldcover, dates=np.array(DATES),
        )

    out_dir = root / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "time_series_cube.npz"
    np.savez_compressed(path, **arrays)
    return path
