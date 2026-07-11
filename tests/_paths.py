"""Ensure repo root and lib/ are on sys.path for xyz_scrcpy imports in tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"

for entry in (str(ROOT), str(LIB)):
    if entry not in sys.path:
        sys.path.insert(0, entry)