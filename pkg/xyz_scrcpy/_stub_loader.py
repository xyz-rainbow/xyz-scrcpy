"""Load lib/xyz_scrcpy modules into root-level stub files (test patch compatibility)."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

from xyz_scrcpy._paths import ensure_import_paths, repo_root


def expose_package_module(short_name: str) -> ModuleType:
    """Import xyz_scrcpy.<short_name> and mirror its public API into sys.modules[short_name]."""
    ensure_import_paths()
    root = repo_root()
    pkg_mod = importlib.import_module(f"xyz_scrcpy.{short_name}")
    stub = sys.modules.get(short_name)
    if stub is None:
        stub = ModuleType(short_name)
        stub.__file__ = str(root / f"{short_name}.py")
        sys.modules[short_name] = stub
    for key, value in pkg_mod.__dict__.items():
        if key.startswith("_"):
            continue
        setattr(stub, key, value)
    return pkg_mod