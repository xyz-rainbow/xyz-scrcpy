"""Ensure repo root and lib/ are on sys.path for xyz_scrcpy imports in tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _package_lib_dir() -> Path:
    for name in ("lib", "pkg"):
        candidate = ROOT / name
        if (candidate / "xyz_scrcpy" / "__init__.py").is_file():
            return candidate
    return ROOT / "lib"


LIB = _package_lib_dir()

for entry in (str(ROOT), str(LIB)):
    if entry not in sys.path:
        sys.path.insert(0, entry)