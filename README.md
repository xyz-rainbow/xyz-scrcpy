# XYZ-scrcpy

Interactive Android device launcher and monitor on top of `scrcpy`, built for users who want an auto-start background service plus a configurable terminal UI.

<p align="center">
  <img src="assets/current_app_2026-04-22-21-47-25.png" alt="Current real-world view of the app" width="360" />
</p>
<p align="center"><em>Current app appearance (real usage screenshot)</em></p>

## Who This Is For

- Linux desktop users who connect Android devices frequently.
- Users who want a background monitor service with popup control.
- Users who need a custom command alias and quick recovery flow.

## Requirements

- `python3` **3.10+** (runtime; see `pyproject.toml` / `.requirements.txt` for declared dependencies such as `psutil`).
- `adb`
- `scrcpy`
- `bash` (Linux/macOS: thin `*.sh` stubs that `exec` Python; checks and Windows flows do **not** require Git Bash).
- Linux desktop with `systemd --user` and any common terminal emulator for full auto-start UX
- macOS (Terminal app fallback via AppleScript)
- Windows: **`uv`** recommended to create `.venv` under the install directory during `install_xyz.py`; monitor runs via Task Scheduler.
- Bundled upstream `scrcpy` in `vendor/` is aligned to latest stable tag `v3.3.4` and is preferred at runtime (fallback: system `scrcpy` in `PATH`)

## Vendor directory and release packaging (Option A)

- **Development clone** may contain a full `vendor/` tree (including Windows `.exe` / DLLs) for convenience on a single checkout.
- **Linux release tarball** (`.tar.gz`): ship **without** Windows-only binaries (strip `*.exe`, `*.dll` from `vendor/` in the archive, or ship an empty `vendor/` and rely on system `scrcpy` / `adb`). Smaller download, matches typical Linux installs.
- **Windows release zip**: ship **with** `vendor/` Windows binaries (or document running `setup_vendor.py` after extract if you publish a “slim” zip).

## Installation summary by OS

| OS | Install command | Service / auto-start | Python deps |
|----|------------------|----------------------|-------------|
| Linux | `python3 install_xyz.py` | `systemctl --user` user unit → `bin/monitor.sh` → `bin/monitor.py` | `pip install --user` / venv for `psutil` per installer |
| Windows | `python install_xyz.py` (or `installer.bat` → repo setup + installer) | Task Scheduler `XYZScrcpyMonitor` → `bin/monitor.py` | `.venv` in install dir via **`uv`** |

### Windows: dev clone launcher and CLI on PATH

- **Repo dev launcher**: from a clone with `.venv` and `vendor\` populated, run `.\xyz-scrcpy.cmd` in PowerShell or CMD. It prepends `vendor` to `PATH` and runs `bin\launch_with_checks.py` with `.venv\Scripts\python.exe`. If the venv is missing, create it (e.g. run `install_xyz.py` or `uv venv` plus `pip install -r .requirements.txt`) before using the script.
- **Installed CLI**: a successful Windows install adds `%LOCALAPPDATA%\xyz-scrcpy\cli` to your **user** `PATH` and drops `<alias>.cmd` there so you can run your chosen alias from any terminal. Uninstall removes that segment and the shim files when possible.
- **Diagnostics**: `python install_xyz.py --action diagnose` (Windows only) prints HKCU `Path` keys, shim/marker paths, how many `Path` segments match the CLI shim, `TEMP`, Python resolution, and a Task Scheduler query for `XYZScrcpyMonitor`. Add `--clean-user-path` on the same command to strip orphan HKCU `Path` rows that still match the shim directory (then reinstall or run a full uninstall to refresh the marker). Use `python install_xyz.py --action install --yes --verbose` for more console and `config/install.log` detail during install; uninstall with `--verbose` logs `schtasks /end` and `/delete` exit codes when the install tree still exists.
- **Installer EXE**: Inno Setup script at `packaging/windows/setup.iss` (build with Inno Setup 6’s `ISCC.exe`). Unsigned builds may trigger **SmartScreen**; use “More info” → “Run anyway” if you trust the artifact. The wizard requires **Python 3.10+** (`py -3` or `python`) on `PATH` before files are staged.
- **Python**: avoid the embeddable distribution without `pip`; the installer checks for `import pip` when resolving the runtime.

## Architecture and Flows (SVG)

![Architecture diagram](docs/assets/architecture.svg)
*Main components and interactions.*

![Install flow diagram](docs/assets/install-flow.svg)
*Clean-install and post-install decision flow.*

![Launcher states diagram](docs/assets/launcher-states.svg)
*Launcher runtime states, including fail-open confirmation.*

## Install and Run

1. Clone repository:
   ```bash
   git clone https://github.com/xyz-rainbow/xyz-scrcpy.git
   cd xyz-scrcpy
   ```

2. Run installer:
   ```bash
   python3 install_xyz.py
   ```

3. Installer interactive flow:
   - Clean install (full uninstall first).
   - Prompt: `Enable service (Y/n)`.
   - Prompt: `Run tests and view log (Y/n)`.
   - Initial mini terminal launch at the end.
   - Fail-open confirmation if checks still fail after repair.

4. Launch command:
   - Use the alias you selected during install.
   - Default alias is typically `xyz-scrcpy` unless changed.

### Non-interactive examples

```bash
# Install with defaults
python3 install_xyz.py --action install --yes

# Install with custom alias
python3 install_xyz.py --action install --alias scrcpy --yes

# Full uninstall
python3 install_xyz.py --action uninstall --yes
```

## Current App Features

### Interactive terminal UI

- Dynamic centered menu that redraws with terminal width changes.
- Arrow-key navigation (`UP/DOWN`) with `ENTER` to select.
- Keyboard shortcuts shown in UI: `[SPACE] [ENTER] [ESC]`.
- Live Android device list from `adb devices`.
- Device labels include model and serial (`Model (serial)`).
- `SETTINGS` and `EXIT` entries always available.

### Device launch behavior

- Launches `scrcpy` for selected device with software render driver (`--render-driver=software`).
- Audio mode is configurable as:
  - `output` (host audio enabled), or
  - `off` (launches with `--no-audio`).
- Menu lock prevents duplicate concurrent menu sessions (lock file under the system temp directory; on Linux historically `/tmp/xyz_menu.lock`).

### Settings currently implemented

- `Command alias`:
  - Editable inside settings.
  - Sanitized to safe command characters.
  - Synced automatically via installer `sync-alias` flow.
- `Audio target`: `HOST` / `DEVICE`.
- `Active Recall`: `ON` / `OFF` (captures microphone directly from Android via scrcpy when supported).
- `Microphone Bus`: `ON` / `OFF` (creates virtual input `xyz-mic-input`; Linux auto-setup via `pactl` without adding a dedicated extra output sink, Windows requires external virtual cable setup).
- `Auto-start`: enables/disables monitor auto-launch behavior.
- `Auto-Discover`: controls automatic reaction to device connection events.
- `Pause on EXIT`: toggle between paused and immediate-start behavior.
- `Pause duration (minutes)`: minimum 1 minute, adjustable in settings.
- `[Apply]` and `[Cancel]` actions in settings.
- `RESTART` action in main menu to re-apply current audio/microphone settings to active scrcpy flow.

### Audio and microphone rules

- `active_recall=ON` means Android microphone capture path (not host microphone capture).
- Android microphone capture is attempted with scrcpy microphone flag support (`--audio-source=mic`).
- If `active_recall=ON` and `audio_target=DEVICE`, config is normalized to `audio_target=HOST` for compatibility.
- If current scrcpy version does not support Android microphone capture, app falls back safely with warning (no crash).
- With `microphone_bus=ON`, app prioritizes virtual bus routing through `xyz-mic-input`.
  - Linux: creates a remapped source from the current default sink monitor (no dedicated extra virtual output sink), reuses existing `xyz-mic-input` if present, and avoids duplicate module/source creation.
  - macOS: detects existing `xyz-mic-input`; otherwise shows guided setup (virtual loopback driver such as BlackHole).
  - Windows: detects existing `xyz-mic-input`; otherwise shows guided setup (virtual cable such as VB-CABLE).

### Pause and reconnect contract

- When `Pause on EXIT` is enabled and user exits menu, monitor enters paused state.
- Pause stores:
  - `pause_active`,
  - `pause_wait_reconnect`,
  - `pause_seen_disconnect`,
  - `pause_until_epoch`.
- With `Auto-Discover = ON`, pause can be lifted by valid reconnect conditions:
  - a previously disconnected device reconnects, or
  - device serial set changes and at least one device is present.
- Pause is also lifted automatically when pause timeout is reached.
- With `Auto-Discover = OFF`, reconnect does not auto-resume the monitor loop.

### Background monitor service behavior

- Monitor loop runs in `bin/monitor.py` (invoked by `bin/monitor.sh` on Linux for compatibility).
- PID lock avoids multiple monitor instances (state under the system temp directory, e.g. `xyz_monitor.pid`).
- Tracks previous/current device serial snapshots (`xyz_monitor_serials.state` next to other monitor state files).
- Performs Python syntax validation (`menu.py` + `config_loader.py`) before opening terminal.
- Popup anti-spam protection:
  - does not open extra monitor terminal if one is already active,
  - does not open popup if any `scrcpy` process is already active.
- Terminal geometry policy:
  - base geometry includes extra height to avoid clipped header,
  - adds one extra row per additional connected device.

### Pre-launch checks and fail-open flow

- Alias launcher runs `bin/launch_with_checks.py` (Windows installed copy) or `bin/launch_with_checks.sh` (Linux/macOS), which run checks then start the menu.
- Checks include:
  - quick path on alias launch: syntax checks only (Python + shell scripts),
  - full unit test suite in background to avoid blocking startup.
- Timeouts protect all major check/repair commands.
- If checks fail:
  - automatic repair is executed (`repair_xyz.py`, or `repair_xyz.sh` on Unix if you use the wrapper),
  - checks are re-run.
- Auto-repair logs include start/end markers, elapsed time, and exit code.
- If still failing:
  - status becomes `FAIL_OPEN`,
  - optional prompt to open a prefilled GitHub issue page in the browser,
  - user is prompted `Open menu anyway despite errors? (Y/n)`.
- `config/check.log` is generated and includes GitHub Issues reporting guidance.
- `config/check.log` includes time log entries (start/end/elapsed seconds) for each check run.
- `config/full-check.log` stores background full-suite results.
- If GitHub issue creation is not possible (requires login), logs can be sent by email to `rainbow@rainbowtechnology.xyz`.

### Installer and uninstaller capabilities

- Multi-OS support path logic for Linux, macOS, and Windows.
- Semi-interactive startup with:
  - `Install now (Y/n)`,
  - confirmation prompt,
  - custom launcher alias prompt.
- Install flow supports:
  - clean install (calls uninstall first),
  - optional service enable (`Enable service (Y/n)`),
  - optional test/check run with log display,
  - opening initial mini terminal after install.
- Uninstall flow includes:
  - service/task stop first,
  - startup disable/removal second,
  - launcher cleanup (primary + managed orphan launchers),
  - optional installed files removal,
  - optional current repository removal with safety checks.
- `sync-alias` action updates stored alias and launcher script without reinstall.

## Runtime Behavior

- Manual alias launch remains available regardless of monitor auto behavior.
- Service mode uses monitor conditions to avoid terminal popup spam.
- Interactive menu is always opened through pre-check gate when launched via alias.

## CI and local validation

Same checks as [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (Linux runs `bash -n` on stubs; skip that step on Windows):

```bash
pip install -r .requirements.txt
python -m py_compile install_xyz.py win_path_shim.py repair_xyz.py \
  bin/menu.py bin/config_loader.py bin/monitor.py \
  bin/check_and_repair.py bin/launch_with_checks.py
python -m unittest discover -s tests -p "test_*.py"
bash -n bin/monitor.sh bin/check_and_repair.sh bin/launch_with_checks.sh
```

### Release / Inno (Windows EXE)

- Install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then from the repository root run:  
  `"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\setup.iss`  
  (adjust the path if your `ISCC.exe` lives elsewhere.) Output falls under `dist/` as configured in the script.
- Keep `packaging/windows/setup.iss` `#define MyAppVersion` aligned with `pyproject.toml` `[project].version`.
- **CI**: the default GitHub Actions workflow does **not** compile the `.iss` (Inno is not preinstalled on `windows-latest`). Build the EXE on a release machine or add an optional workflow job if you install Inno on the runner.

## Repository Layout

- `pyproject.toml` / `.requirements.txt` — declared Python dependency versions (`psutil`).
- `CHANGELOG.md` — published version history.
- `install_xyz.py` — multi-OS installer and uninstaller.
- `win_path_shim.py` — Windows user `PATH` shim, `%LOCALAPPDATA%\xyz-scrcpy\cli` `.cmd` launcher, backup/marker helpers.
- `xyz-scrcpy.cmd` — Windows **development** entry from repo root (requires local `.venv`).
- `packaging/windows/setup.iss` — Inno Setup 6 definition for a low-privilege staging installer that runs `install_xyz.py` / uninstall.
- `bin/menu.py` — interactive terminal UI.
- `bin/monitor.py` — background monitor loop (shared implementation).
- `bin/monitor.sh` — thin stub that invokes `monitor.py` (keeps systemd `ExecStart` stable).
- `bin/launch_with_checks.py` / `bin/launch_with_checks.sh` — launcher with pre-check gate.
- `bin/check_and_repair.py` / `bin/check_and_repair.sh` — checks + repair + fail-open status.
- `bin/config_loader.py` — config defaults and persistence.
- `tests/` — installer, monitor, and shell flow tests.
- `systemd/scrcpy-auto.service` — service template/reference.
- `config/` — runtime config and logs.
- `docs/launch-linux-strategy.md` — why `monitor.sh` / `launch_with_checks.sh` remain on Linux.
- `docs/SMOKE_FROM_RELEASE.md` — smoke checks from `.tar.gz` / `.zip` without `git clone`.
- `docs/audio-mic-restart-risks-walkthrough.md` — risks and operational walkthrough for audio/mic/restart behavior.
- `docs/implementation-phases.md` — phased implementation checklist (multi-OS monitor, `uv`, CI, releases); keep in sync with the Cursor implementation plan when iterating.

## Feature to File Map

| Feature | Main file/script | Notes |
|---|---|---|
| Interactive menu rendering and navigation | `bin/menu.py` | Dynamic width, centered layout, key handling |
| Device discovery and labels | `bin/menu.py` | Uses `adb devices` + model lookup |
| Device launch with audio target | `bin/menu.py` | Starts `scrcpy` with `--no-audio` when target is `DEVICE` |
| Microphone forwarding capability check | `bin/menu.py` | Adds mic flag only when detected as supported by current `scrcpy` |
| scrcpy binary resolution | `bin/menu.py` | Uses `vendor/scrcpy` when executable, else falls back to `scrcpy` from `PATH` |
| Virtual microphone bus (`xyz-mic-input`) | `bin/menu.py` | Linux auto-setup via `pactl` with duplicate-safe reuse, plus macOS/Windows existing-device detection and guided fallback |
| Settings editing (`Apply`/`Cancel`) | `bin/menu.py` | Includes alias, audio/mic, auto flags, and pause options |
| Restart-to-apply audio/mic settings | `bin/menu.py` | `RESTART` button highlights when pending changes exist |
| Pause activation on exit | `bin/menu.py` | Persists pause state/timer in config |
| Config defaults and normalization | `bin/config_loader.py` | Backward compatibility and type coercion |
| Config persistence (`config.json`) | `bin/config_loader.py` | Atomic save via temp file replace |
| Auto monitor loop | `bin/monitor.py` | Invoked via `bin/monitor.sh` on Linux for systemd compatibility |
| Popup anti-spam guard | `bin/monitor.py` | Detects active monitor terminal or `scrcpy` process |
| Reconnect-aware pause resume | `bin/monitor.py` | Uses serial snapshots and pause flags |
| Pre-launch check gate | `bin/launch_with_checks.py` | `.sh` is a thin stub on Linux/macOS |
| Checks + auto-repair pipeline | `bin/check_and_repair.py` | `.sh` delegates here; `repair_xyz.py` for repair |
| Installer interactive flow | `install_xyz.py` | Install/uninstall/sync-alias/diagnose, prompts and cleanup |
| Windows PATH CLI shim | `win_path_shim.py` | User `PATH` segment, `%LOCALAPPDATA%\xyz-scrcpy\cli` shims, backup/marker |
| Service install/enable/disable/stop | `install_xyz.py` | OS-specific handling (Linux/macOS/Windows) |
| Alias creation and synchronization | `install_xyz.py` | Launcher generation + managed launcher cleanup |
| Runtime logs and diagnostics | `config/check.log`, `config/scrcpy.log` | Check pipeline and service output |
| Unit/integration behavior coverage | `tests/` | Installer, monitor, launcher/check shell flows |

## Operations

```bash
# Restart service
systemctl --user restart scrcpy-auto.service

# Check service status
systemctl --user status scrcpy-auto.service --no-pager -n 20

# Manual repair workflow
python3 repair_xyz.py
```

## Past Visual Versions

These screenshots are kept as legacy visual references from earlier UI iterations:

<table>
  <tr>
    <td align="center">
      <img src="assets/actual_app-status.png" alt="Legacy former top screenshot" width="260" />
      <br />
      <em>Legacy former top screenshot</em>
    </td>
    <td align="center">
      <img src="assets/terminal_main.png" alt="Legacy terminal view" width="260" />
      <br />
      <em>Legacy terminal view</em>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="assets/terminal_monitor.png" alt="Legacy monitor view" width="260" />
      <br />
      <em>Legacy monitor view</em>
    </td>
    <td align="center">
      <img src="assets/rainbow_tech.png" alt="Legacy branding preview" width="260" />
      <br />
      <em>Legacy branding preview</em>
    </td>
  </tr>
</table>

## Credits

Developed by xyz-rainbow / Rainbowtechnology [XYZ]  
GitHub https://github.com/xyz-rainbow

#xyz-rainbowtechnology #i-love-you #xyz-rainbow
