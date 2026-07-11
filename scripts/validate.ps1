# Run the same checks as CI (see README "CI and local validation").
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

Write-Host "[validate] pip install..."
pip install -r .requirements.txt ruff | Out-Null

Write-Host "[validate] py_compile..."
python -m py_compile install_xyz.py repair_xyz.py `
  lib/xyz_scrcpy/_paths.py lib/xyz_scrcpy/_stub_loader.py lib/xyz_scrcpy/install_xyz.py `
  lib/xyz_scrcpy/win_path_shim.py lib/xyz_scrcpy/adb_resolve.py `
  lib/xyz_scrcpy/repair_xyz.py lib/xyz_scrcpy/setup_vendor.py lib/xyz_scrcpy/vendor_bootstrap.py `
  bin/menu.py bin/config_loader.py bin/monitor.py `
  bin/check_and_repair.py bin/launch_with_checks.py bin/install_tui.py `
  bin/terminal_open.py bin/adb_transport.py bin/device_tracker.py bin/alias_sync.py packaging/excludes.py

Write-Host "[validate] unittest..."
python -m unittest discover -s tests -p "test_*.py"

Write-Host "[validate] ruff..."
ruff check install_xyz.py repair_xyz.py lib/xyz_scrcpy bin/ tests/ packaging/

Write-Host "[validate] OK (bash -n skipped on Windows; run validate.sh on Linux/macOS)"