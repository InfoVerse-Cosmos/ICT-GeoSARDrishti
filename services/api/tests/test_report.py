"""One-click analysis report endpoint (SRS §4.2, §7.1).

The report must be grounded strictly in computed pack numbers, carry the honest
caveat, and compute before/after change WITHIN a single track/frame.
"""
from __future__ import annotations

import numpy as np

from conftest import AOI_IDS, assert_envelope


# ---------------------------------------------------------------- endpoint shape
def test_report_returns_envelope_for_every_aoi(client):
    for aoi_id in AOI_IDS:
        res = client.get(f"/api/v1/aois/{aoi_id}/report")
        assert res.status_code == 200
        assert_envelope(res.json())


def test_report_unknown_aoi(client):
    body = client.get("/api/v1/aois/nope/report").json()
    assert body["status"] == "unknown_aoi"
    assert body["data"] is None
    assert body["fallback_active"] is True


def test_report_without_cube_degrades_gracefully(client):
    """Seed AOIs ship no cube — the report still opens with the caveat, flagged not-ready."""
    data = client.get("/api/v1/aois/aoi_assam_majuli/report").json()["data"]
    assert data["data_pack_ready"] is False
    assert "not a confirmed flood" in data["caveat"].lower()
    assert data["hydroperiod"] is None


# ---------------------------------------------------------------- grounded numbers
def test_report_is_grounded_and_honest(monkeypatch, tmp_path):
    from app.data_store import store
    from app.services import report_builder as rb

    manifest = {
        "aoi_id": "aoi_test", "name": "Test AOI", "bounds": [70.0, 23.0, 70.2, 23.2],
        "track_frame": "T10/F20", "polarization": "HH+HV",
        "timeline": [
            {"date": "2026-10-04", "track_frame": "T10/F20", "maturity": "PROVISIONAL"},
            {"date": "2026-10-16", "track_frame": "T10/F20", "maturity": "PROVISIONAL"},
            {"date": "2026-10-09", "track_frame": "T99/F20", "maturity": "PROVISIONAL"},
        ],
        "provenance": {
            "otsu_thresholds": {
                "2026-10-04": {"otsu_hh_db": -16.0, "hv_thresh_db": -18.0},
                "2026-10-16": {"otsu_hh_db": -16.0, "hv_thresh_db": -18.0},
                "2026-10-09": {"otsu_hh_db": -16.0, "hv_thresh_db": -18.0},
            },
            "granules": ["NISAR_G1", "NISAR_G2", "NISAR_G3"],
            "limitations": [
                "Radar-derived surface-water indication for inspection, not confirmed flood depth.",
                "OPERA agreement is inter-sensor agreement, not ground-truth accuracy.",
                "Hydroperiod expressed as M of N valid NISAR observations, not days flooded.",
            ],
        },
    }
    rows = cols = 4
    hh = np.full((3, rows, cols), -10.0, dtype=np.float32)   # dry everywhere
    hv = np.full((3, rows, cols), -10.0, dtype=np.float32)
    hh[0, 0, 0] = hh[1, 0, 0] = -20.0                        # open water at (0,0) on both T10 dates
    hv[0, 0, 0] = hv[1, 0, 0] = -25.0
    hh[1, 0, 1] = -20.0                                      # extra open px only on the later T10 date
    hv[1, 0, 1] = -25.0
    m_open = np.zeros((rows, cols), np.int16)
    m_open[0, 0] = 2
    cube = {
        "hh_db": hh, "hv_db": hv, "m_open": m_open,
        "m_fveg": np.zeros((rows, cols), np.int16),
        "n_valid": np.full((rows, cols), 3, np.int16),
        "gmm": np.full((rows, cols), 4, np.int8),
        "dates": np.array(["2026-10-04", "2026-10-16", "2026-10-09"]),
    }

    monkeypatch.setattr(store, "get", lambda a: manifest)
    monkeypatch.setattr(rb, "_load_cube", lambda a: cube)
    monkeypatch.setattr(store, "aoi_dir", lambda a: tmp_path)

    r = rb.build_report("aoi_test")
    assert r["data_pack_ready"] is True

    # Hydroperiod grounded in m_open / n_valid (not fabricated).
    assert r["hydroperiod"]["ever_open_water_km2"] > 0
    assert r["hydroperiod"]["n_max"] == 3

    # Per-date open water recomputed from the cube with the scene's own threshold.
    per_date = {d["date"]: d for d in r["classes"]["per_date"]}
    assert per_date["2026-10-16"]["open_water_km2"] > per_date["2026-10-04"]["open_water_km2"] > 0

    # Before/after is computed WITHIN one track and flags the multi-track geometry.
    assert r["change"]["multi_track"] is True
    assert r["change"]["primary"]["track_frame"] == "T10/F20"
    assert r["change"]["primary"]["before_date"] == "2026-10-04"
    assert r["change"]["primary"]["after_date"] == "2026-10-16"

    # Honest framing is mandatory.
    assert "not a confirmed flood" in r["caveat"].lower()
    assert "inter-sensor agreement" in " ".join(r["limitations"]).lower()
    assert r["provenance"]["granules"] == ["NISAR_G1", "NISAR_G2", "NISAR_G3"]
