# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-05-15

### Added

- `installer.sh`: Linux/macOS bash dev menu (`uv`, `.venv`, `install_xyz.py` actions) mirroring `installer.bat` UX; Bash 3.2-safe prompts; CI runs `bash -n installer.sh` on Ubuntu.
- `tests/test_installer_sh.py`: `bash -n` and content invariants for `installer.sh`.
- `docs/plan-linux-installer-parity.md`: parity matrix, verification checklist, post-Windows baseline notes.
- `docs/DEV_AUDIT_REPORT.md`: repository audit and follow-up task list after `installer.sh`.

### Changed

- `README.md`: Linux install summary, `./installer.sh` instructions, repository layout, feature map; WSL hint for dev clones using `installer.sh` / `.venv`.
- `installer.bat`: automatic VT/ANSI when possible, dynamic menu width, ASCII menu text, `[Y/n]` confirmations, resilient `install_xyz` flow messaging.
- `install_xyz.py`: Windows scheduled task creation (`schtasks`) soft-fail with warning so install can continue when policy blocks the task.
- `bin/menu.py`: terminal width margin aligned with integrated terminals (`columns - 3`).
- `.github/workflows/ci.yml`: include `installer.sh` in `bash -n` on Linux runners.
- `.gitattributes`: force LF line endings for `installer.sh`.
- `tests/test_installer.py`: portable copy check covers `installer.sh`.

## [1.0.0] - 2026-05-13

### Added

- `pyproject.toml` with runtime dependency `psutil` and `requires-python >= 3.10`.
- `bin/monitor.py` as the shared monitor implementation; `bin/monitor.sh` is a thin `exec python3` stub for Linux systemd compatibility.
- `bin/check_and_repair.py` and `bin/launch_with_checks.py` for portable checks and launcher flow (no Git Bash required on Windows).
- `repair_xyz.py` for cross-platform repair (process cleanup, syntax validation, service restart).
- GitHub Actions CI (Ubuntu + Windows) and a release workflow for `v*` tags (Linux `.tar.gz`, Windows `.zip`, `SHA256SUMS`).
- Documentation: vendor packaging policy, Linux launcher strategy, smoke checks from release archives.

### Changed

- Windows install path uses `uv` for a runtime `.venv`, Task Scheduler runs `monitor.py`, and desktop launchers call `launch_with_checks.py` without `bash`.
- `menu.py` RESTART stops scrcpy by device serial using `psutil` when available.

### Deprecated

- `patch_menu.py` is a no-op; do not rely on it for Windows patches.

[1.0.1]: https://github.com/xyz-rainbow/xyz-scrcpy/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/xyz-rainbow/xyz-scrcpy
