"""GeoSAR Drishti offline processing pipeline (SRS §5).

Shared, importable logic behind scripts/01-05 so it can be unit-tested.
"""
import sys

# Windows consoles default to cp1252 and crash on '→', '°', '²' in log lines.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
