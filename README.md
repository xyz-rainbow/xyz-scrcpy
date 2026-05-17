# XYZ-scrcpy

Interactive Android device launcher and monitor on top of `scrcpy`, built for users who want an auto-start background service plus a configurable terminal UI.

<p align="center">
  <img src="vendor/icon.png" alt="XYZ-scrcpy project icon" width="200" />
</p>
<p align="center"><em>Project icon (bundled under <code>vendor/icon.png</code>)</em></p>

## Who This Is For

- Linux desktop users who connect Android devices frequently.
- Users who want a background monitor service with popup control.
- Users who need a custom command alias and quick recovery flow.

## Requirements

- `python3` **3.10+** (runtime; see `pyproject.toml` / `.requirements.txt` for declared dependencies such as `psutil`).
- `adb` (Android platform-tools). On Windows, if `adb` is not on `PATH`, this project prefers `vendor/adb.exe` when present, then optional SDK discovery (see **Android device connectivity** below). You can point to any `platform-tools` directory with `XYZ_ANDROID_PLATFORM_TOOLS`.
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
| Linux | `python3 install_xyz.py` or **`./installer.sh`** (bash menu: `uv`, `.venv`, `[Y/n]`, `install_xyz.py` actions; [4] diagnose is Windows-only in Python) | `systemctl --user` user unit → `bin/monitor.sh` → `bin/monitor.py` | `pip install --user` / venv for `psutil` per installer |
| Windows | `python install_xyz.py` or **`installer.bat`** (CMD menu: uv, `.venv`, auto-VT colors, install/uninstall/diagnose/sync-alias) | Task Scheduler `XYZScrcpyMonitor` → `bin/monitor.py` | `.venv` in install dir via **`uv`** |

### Windows: dev clone launcher and CLI on PATH

- **Repo dev launcher**: from a clone with `.venv` and `vendor\` populated, run `.\xyz-scrcpy.cmd` in PowerShell or CMD. It prepends `vendor` to `PATH` and runs `bin\launch_with_checks.py` with `.venv\Scripts\python.exe`. If the venv is missing, create it (e.g. run `install_xyz.py` or `uv venv` plus `pip install -r .requirements.txt`) before using the script.
- **`installer.bat`** (repo root, CMD): interactive **menu** (not full-screen TUI). **ANSI/VT**: enabled automatically when `scripts/enable_conhost_vt.ps1` succeeds; `ESC` is set via PowerShell so colors work under **PowerShell** hosts. **Confirmations** use `[Y/n]` (`set /p`; Enter = Yes) for uv, `.venv` bootstrap, **[1]** refresh, and **[2]–[5]** before `install_xyz.py`. **`install_xyz.py`** runs **without** `--yes`, so Python may ask again. If **`schtasks /create`** fails (policy/elevation), install **continues** and still configures the **CLI shim** and user `PATH`; the logon task can be added manually. Open a **new** terminal after install for `xyz-scrcpy` on `PATH`. Full-screen TUI: `python install_xyz.py --tui`.
- **TUI installer**: same full-screen style as the main app — `python install_xyz.py --tui` (or `python bin/install_tui.py` from repo root with `PYTHONPATH` set). Use arrow keys and Enter like the device menu.
- **PowerShell and bare `xyz-scrcpy`**: There is **no** extensionless `xyz-scrcpy` in the repo—only `xyz-scrcpy.cmd`. From the clone directory you must use **`.\xyz-scrcpy.cmd`**; PowerShell will not pick up a command in the current directory without the `.\` prefix. After a full Windows **install**, the default alias adds `%LOCALAPPDATA%\xyz-scrcpy\cli` to your user `PATH` with **`xyz-scrcpy.cmd`** and **`xyz-scrcpy.bat`**; then `xyz-scrcpy` may work from any directory in a **new** terminal (PATH is read at session start). If it still fails, run `where.exe xyz-scrcpy` or `Get-Command xyz-scrcpy*` and `python install_xyz.py --action diagnose`.
- **Installed CLI**: a successful Windows install adds `%LOCALAPPDATA%\xyz-scrcpy\cli` to your **user** `PATH` and drops **`<alias>.cmd` and `<alias>.bat`** there (same payload; some shells / `PATHEXT` resolve `.bat` more predictably than `.cmd`). Uninstall removes that segment and the shim files when possible.
- **Diagnostics**: `python install_xyz.py --action diagnose` (Windows only) prints HKCU `Path` keys, shim/marker paths, how many `Path` segments match the CLI shim, `TEMP`, Python resolution, a Task Scheduler query for `XYZScrcpyMonitor`, and an **adb** block: resolved executable (PATH vs `vendor/adb.exe` vs SDK-style locations), `adb version` when runnable, plus `adb devices` (or a short hint when the list is empty). Add `--clean-user-path` on the same command to strip orphan HKCU `Path` rows that still match the shim directory (then reinstall or run a full uninstall to refresh the marker). Use `python install_xyz.py --action install --yes --verbose` for more console and `config/install.log` detail during install; uninstall with `--verbose` logs `schtasks /end` and `/delete` exit codes when the install tree still exists. If **`schtasks /create`** fails during install, the CLI shim and PATH are still applied when the rest of the install succeeds; check the console `[WARN]` line.
- **Installer EXE**: Inno Setup script at `packaging/windows/setup.iss` (build with Inno Setup 6’s `ISCC.exe`). Unsigned builds may trigger **SmartScreen**; use “More info” → “Run anyway” if you trust the artifact. The wizard requires **Python 3.10+** (`py -3` or `python`) on `PATH` before files are staged.
- **Python**: avoid the embeddable distribution without `pip`; the installer checks for `import pip` when resolving the runtime. When several runtimes exist, resolution prefers **`py -3.10`**, then **`py -3.11` … `py -3.19`**, then **`py -3`**, then **`python`** so a generic `py -3` does not accidentally bind to 3.9 before a pinned 3.10+ is tried.

#### Windows risks (Defender, Sandbox, Server Core)

- **Microsoft Defender** or other AV may flag unsigned `.cmd` / `.bat` / `python.exe` invocations from `%LOCALAPPDATA%` or from the Inno extract folder under `%LOCALAPPDATA%\Programs\XYZ-scrcpy`. Allow-list the shim directory and your clone path if installs fail silently or “Access denied” appears.
- **Windows Sandbox** and locked-down VMs may block `schtasks`, ignore `WM_SETTINGCHANGE`, or restrict registry edits to `HKCU\Environment`. Use `install_xyz.py --action diagnose` to see what failed; the installer skips task creation (with a warning) if `schtasks.exe` is missing (e.g. some **Server Core** images), or if **`schtasks /create`** returns access denied (install still completes shim + PATH when possible).

### Linux / macOS dev installer (`installer.sh`)

- **`./installer.sh`** (repo root, bash): interactive **menu** (not full-screen TUI). **Colours** when stdout is a TTY and `tput colors` is at least 8; dynamic `=` border width (margin like `bin/menu.py`). **Confirmations** use `[Y/n]` (Enter = yes) for `uv`, `.venv` bootstrap, **[1]** refresh, and **[2]/[3]/[5]** before `install_xyz.py`. **`install_xyz.py`** runs **without** `--yes`, so Python may ask again. Menu **[4]** explains that `install_xyz.py --action diagnose` is **Windows-only** today. Syntax stays compatible with **macOS `/bin/bash` 3.2`** (no Bash 4-only `${var,,}`). Feature matrix and optional follow-ups: [docs/plan-linux-installer-parity.md](docs/plan-linux-installer-parity.md).
- **WSL + dev menu:** For `./installer.sh` and the same repo-local **`.venv`** layout as on native Linux, prefer a clone on the **Linux filesystem** (e.g. `~/src/xyz-scrcpy`) instead of `/mnt/c/...` (fewer metadata/IO surprises with `uv` and file locks). USB/adb from WSL still follows the general WSL notes in the troubleshooting section below.

## Android device connectivity (troubleshooting)

Short checklist when `adb devices` is empty or the phone never leaves `unauthorized` / `offline`:

- **USB debugging**: enable *Developer options* → *USB debugging* on the device; unlock the screen when plugging in; accept the RSA fingerprint prompt.
- **Xiaomi / MIUI**: some builds also require *USB debugging (Security settings)* (allows ADB through the stricter security layer).
- **Cable and port**: charge-only cables and flaky USB controllers are common; try another cable, a rear motherboard port, or USB 2.0 instead of a front-panel hub.
- **Hubs and Windows USB power**: unpowered hubs or aggressive **USB selective suspend** can delay enumeration enough that Windows reports **Device Descriptor Request Failed** even with a good phone. Prefer a direct motherboard port; in **Power Options** → advanced settings, try disabling **USB selective suspend**; in **Device Manager** → *Universal Serial Bus controllers*, uncheck **Allow the computer to turn off this device to save power** on the **USB Root Hub** (and on intermediate hubs if present). Severe USB host faults can mimic the same symptoms—rule out hardware if errors persist on every port.
- **WSL**: Linux inside WSL does **not** see your PC’s USB devices by default, so `adb devices` there is often empty. Use **ADB on Windows** (host `cmd` / PowerShell, `vendor\adb.exe`, or `XYZ_ANDROID_PLATFORM_TOOLS`). If you intentionally need USB inside WSL, install **[usbipd-win](https://github.com/dorssel/usbipd-win)** on Windows and follow Microsoft’s guide to attach devices to WSL ([Connect USB devices](https://learn.microsoft.com/windows/wsl/connect-usb)); that is **optional** and **not** required for the normal native Windows install path.
- **Windows / PnP errors**: if Device Manager shows failed “Android” or composite USB descriptors, fix the driver stack (OEM USB driver, Intel/AMD chipset/USB3 drivers) before expecting a stable ADB session.
- **Custom `platform-tools` location**: set environment variable `XYZ_ANDROID_PLATFORM_TOOLS` to the **directory** that contains `adb.exe` (for example a folder literally named `platform-tools`, even when the full path contains spaces or brackets).
- **spacedesk** is a separate product (often used for a second-screen or USB tethering style link). It does **not** replace ADB for this launcher. If spacedesk is running, it is unrelated to whether `adb devices` lists the phone; still use proper USB debugging and drivers for `adb`/`scrcpy`.

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

2. Run installer (pick one):
   ```bash
   python3 install_xyz.py
   ```
   Dev clone menu (installs **`uv`**, creates **`.venv`**, then same Python prompts): `chmod +x installer.sh` once if needed, then `./installer.sh`.
   Optional **full-screen TUI** (same look as the main menu): `python3 install_xyz.py --tui`

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

# CI / SSH / headless: skip post-install GUI window
python3 install_xyz.py --action install --yes --no-open-terminal
```

### Post-install troubleshooting

| Symptom | What to do |
|---------|------------|
| Install prints *Opening initial mini terminal…* but no window appears | Install a terminal emulator (`sudo apt install gnome-terminal` on Debian/Ubuntu) or run `xyz-scrcpy` manually in your current shell. The installer lists emulators it tried. |
| `No module named pip` during install | Install `python3-venv` and `python3-pip`, or install [uv](https://github.com/astral-sh/uv) so the installer can create `~/.local/share/xyz-scrcpy/.venv`. |
| `Missing dependencies: adb, scrcpy` | `sudo apt install adb scrcpy` (Linux) or add platform-tools / scrcpy to PATH (Windows). |
| Monitor service does not start | `systemctl --user status scrcpy-auto.service` — user systemd must be available (not all SSH/WSL setups). Install still completes with a warning. |
| Fail-open / check errors on Linux | Ensure unit tests pass (`python3 -m unittest discover -s tests`). Windows-only registry tests must not import `winreg` on Linux (fixed in `win_path_shim.py`). |

After install, open a **new** terminal if `xyz-scrcpy` is not found (PATH refresh).

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

Same checks as [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (Linux runs `bash -n` on shell scripts; skip that step on Windows):

```bash
pip install -r .requirements.txt
python -m py_compile install_xyz.py win_path_shim.py adb_resolve.py repair_xyz.py \
  bin/menu.py bin/config_loader.py bin/monitor.py \
  bin/check_and_repair.py bin/launch_with_checks.py bin/install_tui.py
python -m unittest discover -s tests -p "test_*.py"
bash -n installer.sh bin/monitor.sh bin/check_and_repair.sh bin/launch_with_checks.sh scripts/clean_dev.sh
```

### Development cleanup

Remove regenerable caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`) before a clean build or commit review:

- **Windows**: `powershell -NoProfile -File scripts\clean_dev.ps1` — add `-IncludeDist` to delete `dist\`, `-IncludeVenv` to delete `.venv\` (recreate with `uv venv` / installer after).
- **Linux / macOS**: `bash scripts/clean_dev.sh` — set `CLEAN_DIST=1` and/or `CLEAN_VENV=1` to also remove `dist/` or `.venv/`.

The Windows Inno installer excludes `scripts\` from the shipped tree (dev-only helpers).

### Release / Inno (Windows EXE)

- Install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then from the repository root run:  
  `"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\setup.iss`  
  (adjust the path if your `ISCC.exe` lives elsewhere.) Output falls under `dist/` as configured in the script.
- **Icon**: the installer script expects [`packaging/windows/app.ico`](packaging/windows/app.ico) next to `setup.iss` (wizard icon, uninstall entry, optional desktop shortcut). Regenerate from `vendor/icon.png` if you change branding, for example:  
  `pip install pillow` then  
  `python -c "from PIL import Image; Image.open('vendor/icon.png').convert('RGBA').save('packaging/windows/app.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"`.
- **Payload size / hygiene**: `setup.iss` lists `[Files]` `Excludes` with **comma** separators (Inno’s documented format). A mis-separated list can accidentally ship `.git`, `.venv`, `.pytest_cache`, and local logs—rebuild after fixing the script. For the smallest artifact, compile from a clean export or ensure those paths are absent.
- **Installer UX** (Inno script): per-user extract under `%LOCALAPPDATA%\Programs\XYZ-scrcpy`, wizard `SetupIconFile`, optional **desktop** `.lnk` (with icon) created **after** `install_xyz.py` via [`packaging/windows/create-desktop-shortcut.ps1`](packaging/windows/create-desktop-shortcut.ps1) (Inno installs `[Icons]` before `[Run]`, so do not point Inno shortcuts at the Start Menu `.cmd` until that file exists), and a **finish-page** “Launch” checkbox that starts the Start Menu `.cmd` (default alias `xyz-scrcpy`; keep `#define MyAppAlias` in `setup.iss` aligned with `install_xyz.DEFAULT_ALIAS` if you change it).
- Keep `packaging/windows/setup.iss` `#define MyAppVersion` aligned with `pyproject.toml` `[project].version`.
- **CI**: the default GitHub Actions workflow does **not** compile the `.iss` (Inno is not preinstalled on `windows-latest`). Build the EXE on a release machine, use the smoke script locally, or add a self-hosted / Inno-equipped job. Optional workflow [`.github/workflows/inno-smoke.yml`](.github/workflows/inno-smoke.yml) (`workflow_dispatch`) runs the smoke script on GitHub’s Windows runner (skips compile when Inno is absent).

## Repository Layout

- `pyproject.toml` / `.requirements.txt` — declared Python dependency versions (`psutil`).
- `CHANGELOG.md` — published version history.
- `scripts/clean_dev.ps1` / `scripts/clean_dev.sh` — optional dev cleanup (not bundled in the Inno EXE).
- `scripts/enable_conhost_vt.ps1` — enables process-local VT mode for the current Windows console; used automatically by `installer.bat` when possible (dev clone).
- `install_xyz.py` — multi-OS installer and uninstaller.
- `installer.bat` — Windows **CMD** interactive menu (uv, `.venv`, auto-VT ANSI when possible, `install_xyz.py` actions); dev clone convenience.
- `installer.sh` — Linux/macOS **bash** interactive menu (`uv`, `.venv`, ANSI when TTY supports it, `install_xyz.py` actions); dev clone convenience.
- `docs/plan-linux-installer-parity.md` — parity matrix, verification checklist, optional Linux `install_service` hardening.
- `adb_resolve.py` — resolve `adb` / `adb.exe` (PATH, `vendor/`, `XYZ_ANDROID_PLATFORM_TOOLS`, standard SDK env paths); used by `bin/menu.py`, `bin/monitor.py`, installer diagnostics.
- `win_path_shim.py` — Windows user `PATH` shim, `%LOCALAPPDATA%\xyz-scrcpy\cli` `.cmd` launcher, backup/marker helpers.
- `xyz-scrcpy.cmd` — Windows **development** entry from repo root (requires local `.venv`).
- `packaging/windows/setup.iss` — Inno Setup 6: per-user extract dir, `install_xyz.py` install/uninstall, optional desktop `.lnk` via `create-desktop-shortcut.ps1` (after `[Run]`), guarded `[UninstallRun]`, finish-page launch.
- `bin/install_tui.py` — full-screen interactive installer (reuses `menu.py` widgets); also available as `python install_xyz.py --tui`.
- `bin/menu.py` — interactive terminal UI (device list, settings, launch).
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
| Device discovery and labels | `bin/menu.py` | Uses `adb devices` + model lookup (`adb_resolve.py` picks adb on Windows when PATH is missing) |
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
| TUI interactive installer | `bin/install_tui.py` / `install_xyz.py --tui` | List navigation and colors shared with `menu.py` |
| Windows CMD dev menu | `installer.bat` | uv, `.venv`, auto-VT, dynamic border width, `[Y/n]` + `install_xyz.py` actions |
| Unix bash dev menu | `installer.sh` | uv, `.venv`, TTY colours + width, `[Y/n]` + `install_xyz.py` actions; diagnose entry is informational (Python diagnose remains Windows-only) |
| Installer interactive flow | `install_xyz.py` | Line-based prompts; `--yes` / `--action` for automation |
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
