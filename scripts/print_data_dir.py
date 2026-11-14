"""Print the folder that holds the user's NISAR .h5 granules (GEOSAR_DATA_DIR from env/.env, else ./DATA)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geosar_pipeline import envcfg  # noqa: E402

print(Path(envcfg.get("GEOSAR_DATA_DIR") or Path(__file__).resolve().parents[1] / "DATA").expanduser())
