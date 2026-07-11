"""Repository root resolution for package modules under lib/xyz_scrcpy/."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    """Parent of lib/ or pkg/ (repository root)."""
    return Path(__file__).resolve().parents[2]


def package_lib_dir(root: Path | None = None) -> Path:
    """Return lib/ or pkg/ when lib/ is unavailable on the filesystem."""
    root = root or repo_root()
    for name in ("lib", "pkg"):
        candidate = root / name
        if (candidate / "xyz_scrcpy" / "__init__.py").is_file():
            return candidate
    return root / "lib"


def ensure_import_paths() -> Path:
    """Put repo root and package lib dir on sys.path for xyz_scrcpy imports."""
    root = repo_root()
    lib = package_lib_dir(root)
    for entry in (str(root), str(lib)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return root