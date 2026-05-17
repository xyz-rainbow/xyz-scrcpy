#!/usr/bin/env python3
"""Dev bootstrap wrapper — delegates to vendor_bootstrap (all platforms)."""

from __future__ import annotations

import sys
from pathlib import Path

import vendor_bootstrap as vb


def main() -> int:
    project_root = Path(__file__).resolve().parent
    os_name = __import__("platform").system().lower()
    result = vb.ensure_android_tools(project_root, os_name, verbose=True)
    return 0 if result.adb_ok and result.scrcpy_ok else 1


if __name__ == "__main__":
    sys.exit(main())
