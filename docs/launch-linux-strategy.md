# Linux launcher strategy

## Decision

- **Monitor (systemd)**: the user unit continues to use `bin/monitor.sh` as `ExecStart` so existing installs stay stable. That script is a one-line stub that runs `python3` on `bin/monitor.py`.
- **Interactive launcher (alias / desktop)**: `bin/launch_with_checks.sh` remains the conventional entry on Linux and macOS. It only delegates to `bin/launch_with_checks.py`, same behavior as calling the Python file directly.
- **Windows**: launchers and Task Scheduler invoke `*.py` directly (no `bash`).

## Rationale

- Avoid churn for Linux users who already have `ExecStart=.../monitor.sh` in their systemd unit.
- Keep a familiar shell script name in `PATH` for humans and docs while sharing one Python implementation across OSes.
- Optional future step: ship only `launch_with_checks.py` in documentation if we want one documented command everywhere; the `.sh` wrapper would remain for backward compatibility.

## Verification

- `bash -n bin/launch_with_checks.sh bin/monitor.sh`
- `python3 bin/launch_with_checks.py` with `XYZ_TEST_MODE=1` (see tests).
