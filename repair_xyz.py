#!/usr/bin/env python3
"""Thin stub: delegates to lib/xyz_scrcpy/repair_xyz.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from xyz_scrcpy._stub_loader import expose_package_module

_impl = expose_package_module("repair_xyz")

if __name__ == "__main__":
    raise SystemExit(_impl.main())