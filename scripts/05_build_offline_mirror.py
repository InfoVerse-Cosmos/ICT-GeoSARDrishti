"""05 — Build the frontend offline mirror (SRS §7.2 rule 3).

Copies a trimmed copy of both AOI manifests (incl. timelines) into
apps/web/public/fallback_data/manifest.json so the map + time slider keep
working if the venue loses internet. Run after scripts 01-04.

    python scripts/05_build_offline_mirror.py [--data-store DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geosar_pipeline.common import data_store  # noqa: E402
from geosar_pipeline import mirror  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-store")
    p.add_argument("--out", default=str(mirror.MIRROR))
    args = p.parse_args()
    m = mirror.run(data_store(args.data_store), Path(args.out))
    print(f"[05] wrote offline mirror with {len(m['aois'])} AOIs -> {args.out}")


if __name__ == "__main__":
    main()
