# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/xyz-rainbow/xyz-scrcpy
