"""Pytest configuration and sys.path setup for AI-Office test suite."""
from __future__ import annotations

import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent
APP_DIR = ROOT / "app"
SCRIPTS_DIR = ROOT / "scripts"

# Add app/ and scripts subdirs to sys.path so tests can import app modules
# and scripts that may have been relocated to subdirs
_paths_to_add = [
    str(APP_DIR),
    str(SCRIPTS_DIR),
    str(SCRIPTS_DIR / "benchmarks"),
    str(SCRIPTS_DIR / "experiments"),
    str(SCRIPTS_DIR / "tools"),
    str(SCRIPTS_DIR / "qa"),
]
for _p in _paths_to_add:
    if _p not in sys.path:
        sys.path.insert(0, _p)
