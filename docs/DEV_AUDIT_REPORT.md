# XYZ-scrcpy — dev audit after `installer.sh` (2026-05-14)

This document captures an inventory-style review of the repository, test results after adding the Linux/macOS dev installer script, and prioritized follow-ups. It mixes **objective** facts (files, commands, counts) with **subjective** engineering opinions.

---

## 1. Test execution (objective)

| Command | Result |
|---------|--------|
| `python -m unittest discover -s tests -p "test_*.py"` | **75 tests**, ~61 s, **OK** (Windows runner; includes TUI/menu tests with heavy stdout) |
| `tests.test_installer_sh` | **2 tests**, **OK** (`bash -n installer.sh` with `cwd=repo`; content invariants) |
| CI (expected) | Linux job runs `bash -n installer.sh` after workflow change |

**Note:** Full discovery emits ANSI from curses/UI tests; exit code 0 confirms no failures.

---

## 2. What changed in this session (objective)

| Artifact | Role |
|----------|------|
| [`installer.sh`](../installer.sh) | Bash menu: `uv` bootstrap, `.venv`, `setup_vendor.py`, framed menu, `[Y/n]` confirms, `install_xyz.py` for install/uninstall/sync-alias; **[4]** explains Windows-only `diagnose`. Uses `tr` for case-fold so **macOS `/bin/bash` 3.2** works. |
| [`tests/test_installer_sh.py`](../tests/test_installer_sh.py) | `bash -n` + static content checks (shebang, `REPO_ROOT`, `curl` URL, no U+2014). |
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | `bash -n` includes `installer.sh`. |
| [`.gitattributes`](../.gitattributes) | `installer.sh text eol=lf`. |
| [`README.md`](../README.md) | Linux table, Install and Run step, layout map, feature table row for `installer.sh`. |
| [`docs/plan-linux-installer-parity.md`](plan-linux-installer-parity.md) | Status section, restored `## Feature parity matrix`, Phase 5/Verification wording. |
| [`tests/test_installer.py`](../tests/test_installer.py) | `copy_project` portable check includes `installer.sh`. |

---

## 3. Repository inventory (exhaustive by area)

### 3.1 Root / installer / Python entrypoints

- `install_xyz.py` — Multi-OS install/uninstall/sync-alias/diagnose (diagnose **Windows-only**), TUI dispatch, path detection, copy/uninstall orchestration.
- `installer.bat` — Windows CMD dev menu (reference UX for parity).
- `installer.sh` — Unix bash dev menu (**new**).
- `repair_xyz.py` / `repair_xyz.sh` — Thin `sh` → Python repair entry.
- `adb_resolve.py` — adb resolution for menu/monitor/installer flows.
- `win_path_shim.py` — Windows HKCU PATH / shim helpers.
- `setup_vendor.py` — Vendor binary / asset staging.
- `patch_menu.py` — Dev/maintenance helper (non-runtime critical).
- `xyz-scrcpy.cmd` — Windows dev launcher from clone.
- `pyproject.toml`, `.requirements.txt` — Dependencies and packaging metadata.

**Opinion (subjective):** The split between “fat” `install_xyz.py` and thin shell stubs is consistent and keeps systemd/CMD entrypoints predictable.

### 3.2 `bin/` (runtime + TUI)

- `menu.py` — Primary TUI (devices, settings, audio, lock file).
- `monitor.py` / `monitor.sh` — Monitor loop + systemd-friendly stub.
- `launch_with_checks.py` / `launch_with_checks.sh` — Pre-check gate.
- `check_and_repair.py` / `check_and_repair.sh` — Health checks + repair.
- `config_loader.py`, `install_tui.py`, `test_syntax.py`.

**Opinion:** Duplicated `.py` / `.sh` pairs are intentional for Linux launchers; documented in README and `docs/launch-linux-strategy.md`.

### 3.3 `tests/` (15 modules, 75 cases)

- `test_installer.py`, `test_installer_sh.py` — Installer behaviour and script smoke.
- `test_install_tui.py`, `test_device_menu.py`, `test_monitor_behavior.py`, `test_shell_flows.py`, `test_audio_config.py`, `test_path_manager.py`, `test_rollback.py`, `test_adb_resolve.py`, `test_python_detector.py`, `test_shim_cmd.py`, `test_marker.py`, etc.

**Objective gap:** No automated **integration** test runs `./installer.sh` with a heredoc-driven session (flaky across CI shells); manual QA remains in the parity plan.

### 3.4 `docs/`

- `plan-linux-installer-parity.md`, `launch-linux-strategy.md`, `implementation-phases.md`, `SMOKE_FROM_RELEASE.md`, `audio-mic-restart-risks-walkthrough.md`, `assets/*.svg` (README diagrams).

### 3.5 `.github/workflows/`

- `ci.yml` — Python compile + unittest + `bash -n` on Linux.
- `release.yml`, `inno-smoke.yml` — Release / Inno smoke (Windows-oriented).

### 3.6 `packaging/windows/`

- `setup.iss`, `smoke-iscc.ps1`, `create-desktop-shortcut.ps1`, `app.ico`.

### 3.7 `scripts/`

- `clean_dev.sh`, `clean_dev.ps1`, `enable_conhost_vt.ps1`.

### 3.8 `systemd/`

- `scrcpy-auto.service` — User unit template reference.

### 3.9 `vendor/`

- `scrcpy.exe`, `adb.exe`, DLLs, `scrcpy-console.bat`, `scrcpy-noconsole.vbs`, `icon.png`, etc.

**Objective:** Binaries are not source-reviewed here; trust upstream scrcpy/adb licensing and supply chain.

### 3.10 `config/`

- Runtime config directory (populated after install; layout depends on installer).

---

## 4. Risk register (by importance)

### P0 — Correctness / security

- **`install_xyz.py` surface area:** Large monolith; regressions need broad tests (current suite mitigates but does not prove every branch).
- **Third-party curl pipe:** `installer.sh` uses official Astral `install.sh` only after explicit `[Y/n]`; air-gapped users can decline (documented pattern).

### P1 — UX / parity

- **Linux `diagnose`:** Still Windows-only in Python; `installer.sh` **[4]** is informational only until Phase 6 in the parity plan.
- **`systemctl --user` hard failures:** Install may still abort on some Linux paths where Windows already soft-fails `schtasks`; optional follow-up PR in plan.

### P2 — Maintainer ergonomics

- **`enable_conhost_vt.ps1` header** still says “opt in” though `installer.bat` runs it automatically (cosmetic doc fix).
- **Test runtime ~60 s:** UI tests print to stdout; acceptable locally but noisy in logs.

### P3 — Nice-to-have

- **Executable bit:** `git update-index --chmod=+x installer.sh` should be committed so Linux clones can run `./installer.sh` without `chmod`.
- **shellcheck:** Not wired in CI; optional `shellcheck installer.sh` job.

---

## 5. Opinions

### Objective

- Parity between `installer.bat` and `installer.sh` is **good enough for v1**: same mental model (uv → venv → menu → Python second prompts).
- CI now guards shell syntax for **`installer.sh`**, matching other bash stubs.

### Subjective

- The project punches above its weight for a **single-repo** scrcpy launcher: multi-OS, TUI, monitor loop, Windows PATH shims, and Inno packaging — complexity is justified by scope, but **onboarding** depends heavily on README accuracy (recent README updates help).
- I would eventually **split** `install_xyz.py` into modules (paths, windows shims, linux service) — not urgent if tests keep pace.

---

## 6. To-do (next tasks)

1. [ ] **Commit** with `installer.sh` mode **100755** in git (`git update-index --chmod=+x installer.sh` then commit).
2. [ ] **Manual:** `./installer.sh` on real Linux (bash/zsh, narrow `COLUMNS`, decline uv / decline venv / full install).
3. [ ] **Optional PR:** Linux `install_service` soft-fail parity with Windows `schtasks` (plan matrix).
4. [ ] **Optional PR:** `install_xyz.py --action diagnose` for Linux (systemd, PATH, adb).
5. [ ] **Doc:** one-line fix in `scripts/enable_conhost_vt.ps1` header (auto-VT).
6. [ ] **Optional:** `shellcheck` in CI for `installer.sh` + existing `*.sh` stubs.
7. [ ] **CHANGELOG.md** entry for `installer.sh` when you cut a release.

---

## 7. References

- [plan-linux-installer-parity.md](plan-linux-installer-parity.md)
- [README.md](../README.md)
- [ci.yml](../.github/workflows/ci.yml)
