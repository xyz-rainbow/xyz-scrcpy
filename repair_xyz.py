#!/usr/bin/env python3
"""Thin stub: delegates to lib/xyz_scrcpy/repair_xyz.py."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
for _lib_name in ("lib", "pkg"):
    _lib = _root / _lib_name
    if (_lib / "xyz_scrcpy" / "__init__.py").is_file():
        sys.path.insert(0, str(_lib))
        break
else:
    sys.path.insert(0, str(_root / "lib"))

from xyz_scrcpy._stub_loader import expose_package_module

_impl = expose_package_module("repair_xyz")

if __name__ == "__main__":
    raise SystemExit(_impl.main())