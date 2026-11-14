"""Standardized response envelope (SRS §7.2).

Every endpoint returns this shape so the React client never reads `undefined`.
"""
from __future__ import annotations

from typing import Any


def envelope(
    data: Any,
    *,
    aoi_id: str | None = None,
    status: str = "ok",
    source_mode: str = "LOCAL_VERIFIED_CACHE",
    fallback_active: bool = False,
    warning: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "aoi_id": aoi_id,
        "source_mode": source_mode,
        "fallback_active": fallback_active,
        "warning": warning,
        "data": data,
    }
