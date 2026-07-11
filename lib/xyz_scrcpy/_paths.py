"""Repository root resolution for package modules under lib/xyz_scrcpy/."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    """Parent of lib/ (repository root)."""
    return Path(__file__).resolve().parents[2]


def ensure_import_paths() -> Path:
    """Put repo root and lib/ on sys.path for packaging.* and xyz_scrcpy imports."""
    root = repo_root()
    lib = root / "lib"
    for entry in (str(root), str(lib)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return root