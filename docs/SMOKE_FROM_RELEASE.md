# Smoke checks (release archives)

Use this after extracting a **release** `.tar.gz` (Linux) or `.zip` (Windows), without `git clone`.

## Linux (`.tar.gz`)

1. Extract: `tar xzf xyz-scrcpy-X.Y.Z-linux.tar.gz && cd xyz-scrcpy-X.Y.Z` (top-level folder name matches the archive).
2. Ensure `adb` and a desktop terminal emulator are available; install system `scrcpy` if `vendor/` has no Linux binary (Option A strips Windows `.exe` / `.dll`).
3. Run `python3 install_xyz.py --action install --yes` (or interactive install).
4. `systemctl --user status` on the packaged unit name; connect a device and confirm the monitor opens the menu when expected.
5. From another terminal, run your launcher alias (e.g. `xyz-scrcpy`) and confirm `launch_with_checks` runs then `menu.py` starts.

## Windows (`.zip`)

1. Extract the zip to a short path (e.g. `%USERPROFILE%\Apps\xyz-scrcpy`) to avoid Task Scheduler command-line length limits.
2. Install [uv](https://github.com/astral-sh/uv), then in the folder run `installer.bat` **or** `uv venv .venv` + `uv pip install -r .requirements.txt` + `setup_vendor.py` as documented in the README.
3. Run `install_xyz.py --action install --yes` with the same Python that will own the venv under the install directory.
4. Task Scheduler: confirm task `XYZScrcpyMonitor` runs `monitor.py` and survives a logoff (user intent).
5. Run the installed desktop / Start Menu launcher or `start.bat` from a repo-style copy; menu should start with vendor `adb` on `PATH`.

## Linux regression (from `git clone`, optional)

For developers validating systemd contract without a release tarball:

1. `systemctl --user daemon-reload` after install if the unit changed.
2. `systemctl --user start` / `status` on `scrcpy-auto.service` (or the name your install uses).
3. USB connect/disconnect: monitor should respect pause / cooldown and avoid duplicate popups (see README).
4. Tail `config/monitor.log` (and `config/check.log` after a check run) for errors.

## Checksums

Verify downloads against `SHA256SUMS` from the GitHub release before extracting.
