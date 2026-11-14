"""Dependency-free settings lookup: process env first, then services/api/.env, then repo-root .env.

Lets one `.env` file say where the heavy stuff lives (e.g. on a bigger drive):
    GEOSAR_DATA_DIR=D:/Hackathon Files      # where the NISAR .h5 granules are  (default: ./DATA)
    GEOSAR_DATA_STORE=D:/geosar_packs       # where analysed packs are written   (default: services/api/data_store)
"""
from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (_ROOT / "services" / "api" / ".env", _ROOT / ".env")


def get(name: str, default: str = "") -> str:
    val = os.environ.get(name)
    if val:
        return val
    for f in ENV_FILES:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                key, sep, v = line.partition("=")
                if sep and key.strip() == name:
                    v = v.split(" #")[0].strip().strip('"').strip("'")
                    if v:
                        return v
        except OSError:
            continue
    return default
