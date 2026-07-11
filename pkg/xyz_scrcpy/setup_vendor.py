"""Thin entry point: python -m xyz_scrcpy.setup_vendor."""

from __future__ import annotations

from xyz_scrcpy._paths import repo_root
from xyz_scrcpy.vendor_bootstrap import detect_environment, ensure_android_tools

if __name__ == "__main__":
    ensure_android_tools(repo_root(), detect_environment().os_name, verbose=True)