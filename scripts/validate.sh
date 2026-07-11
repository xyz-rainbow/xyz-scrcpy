#!/usr/bin/env bash
# Run the same checks as CI (see README "CI and local validation").
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[validate] pip install..."
pip install -r .requirements.txt ruff >/dev/null

echo "[validate] py_compile..."
python3 -m py_compile install_xyz.py repair_xyz.py \
  lib/xyz_scrcpy/_paths.py lib/xyz_scrcpy/_stub_loader.py lib/xyz_scrcpy/install_xyz.py \
  lib/xyz_scrcpy/win_path_shim.py lib/xyz_scrcpy/adb_resolve.py \
  lib/xyz_scrcpy/repair_xyz.py lib/xyz_scrcpy/setup_vendor.py lib/xyz_scrcpy/vendor_bootstrap.py \
  bin/menu.py bin/config_loader.py bin/monitor.py \
  bin/check_and_repair.py bin/launch_with_checks.py bin/install_tui.py \
  bin/terminal_open.py bin/adb_transport.py bin/device_tracker.py bin/alias_sync.py packaging/excludes.py

echo "[validate] unittest..."
python3 -m unittest discover -s tests -p "test_*.py"

echo "[validate] ruff..."
ruff check install_xyz.py repair_xyz.py lib/xyz_scrcpy bin/ tests/ packaging/

echo "[validate] bash -n..."
bash -n installer.sh launchers/unix/installer.sh launchers/unix/repair_xyz.sh \
  bin/monitor.sh bin/check_and_repair.sh bin/launch_with_checks.sh scripts/clean_dev.sh scripts/validate.sh

echo "[validate] OK"