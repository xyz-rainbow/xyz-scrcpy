# Plan: Linux dev installer parity with `installer.bat`

Goal: **`installer.sh`** at the repo root mirrors the **Windows `installer.bat`** UX: interactive text menu (no full-screen TUI), explicit confirmations, `uv` + `.venv` bootstrap, and delegation to **`install_xyz.py`** with the same actions where applicable. Optional items (Linux diagnose, resilient `systemctl`) remain in later phases.

## Status

- **`installer.sh`**: implemented (menu, `uv`, bootstrap, colours/width, `[Y/n]`, `install_xyz.py` for install/uninstall/sync-alias; **[4]** informational only because Python `diagnose` is Windows-only).
- **Post-install mini terminal**: `bin/terminal_open.py` shared with `monitor.py` / `launch_with_checks.py`; `install_xyz.py` uses emulator fallback chain and `--no-open-terminal` for headless CI.
- **`install_service` (Linux)**: `systemctl --user` failures are soft-warned (install continues).
- **Still open**: Linux `install_xyz.py --action diagnose`, deeper manual QA per Verification section.

## Feature parity matrix

| Windows `installer.bat` | Linux equivalent | Notes |
|-------------------------|------------------|--------|
| `pushd` repo root | `cd` to script dir (`SCRIPT_DIR` / `REPO_ROOT`) | Prefer Bash **3.2+** syntax (macOS `/bin/bash`); avoid `${var,,}` / associative arrays (Bash 4+). |
| Check / install **uv** | `command -v uv` + official install `curl ... \| sh` with **Y/n** confirm | Respect air-gapped users; decline exits **0**; append `~/.local/bin` to `PATH` for current shell session. |
| Confirm create **`.venv`** | Same prompts; `uv venv .venv` + `uv pip install` + `python setup_vendor.py` | Use `.venv/bin/python3`. |
| **Auto VT / colors** | If `[[ -t 1 ]]` and `tput colors` ≥ 8, assume ANSI OK; optional `tput cols` for width | No `enable_conhost_vt.ps1`; use `TERM` + `printf '\033[...m'`. |
| Dynamic **border width** | `COLUMNS=${COLUMNS:-$(tput cols 2>/dev/null || echo 80)}` then clamp `40..120` with margin **-3** like `menu.py` | Match `terminal_width()` behaviour. |
| Menu **1–5 + Q** | Same numbering; **Q** quit | Use `select` in bash or `read -n1` + case (avoid `0` as exit key same as Windows plan). |
| **[1]** refresh env | Same | |
| **[2]** install | `.venv/bin/python3 install_xyz.py --action install` | No `--yes`; double confirmation with Python. |
| **[3]** uninstall | `--action uninstall` | |
| **[4]** diagnose | **Omit** or show message: `install_xyz.py --action diagnose` is **Windows-only** today | **Phase B** (optional): add `install_xyz.py --action diagnose` for Linux (systemd user unit, `PATH`, adb block) reusing `adb_resolve` patterns. |
| **[5]** sync-alias | `--action sync-alias` | |
| Post-install **hint** | Echo “open new shell” / `hash -r` for `PATH` | Linux launcher is file in `launcher_dir` (e.g. `~/bin`); document per existing `install_xyz` behaviour. |
| **`schtasks` soft-fail** | Parity: **`systemctl --user`** enable/start may fail (no user session, no systemd); install should **continue** when possible | Mirror `install_xyz.py` Windows change: catch `CalledProcessError` on Linux `install_service` paths where `run_cmd` is strict, log `[WARN]`, continue if rest of install can proceed. **Separate small PR** after `installer.sh` lands. |

## Phases

### Phase 1 — Script skeleton

- **`installer.sh`** at repo root (executable bit in git when possible).
- `REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` (BASH_SOURCE for sourced-safe path).
- Main loop: draw frame, menu, `read` / `select`, dispatch to functions.
- **No** Unicode punctuation in `echo` strings (ASCII `-` only) for dumb terminals.

### Phase 2 — `uv` and bootstrap

- `:ensure_uv` equivalent: prompt + curl installer or package-manager note.
- `do_bootstrap`: same three steps as `.bat`.

### Phase 3 — Colors and width

- Reuse ANSI codes from `bin/menu.py` (`\033[38;5;118m`, `\033[35m`, `\033[38;5;213m`, `\033[0m`) behind `USE_COLOR=0/1`.
- Build `W` repeat `=` for `TW` columns.

### Phase 4 — Confirmations and `install_xyz`

- `confirm_yes_no "msg"` function: `read -r -p "msg [Y/n]: "` empty/y → yes.
- `run_install_xyz --action …` wrapper with exit-code handling and install success tip.

### Phase 5 — Docs and CI

- **README**: Linux row documents `./installer.sh`; parity plan remains the matrix and optional follow-ups.
- **CI**: `bash -n installer.sh` in `.github/workflows/ci.yml` (Linux job).

### Phase 6 (optional) — Linux `diagnose` and resilient `install_service`

- Extend `install_xyz.py` **diagnose** for Linux or keep menu entry as “not available” with one-line explanation.
- Harden `install_service` for Linux when `systemctl --user` is unavailable (headless, WSL without user systemd).

## Out of scope for first PR

- Full-screen TUI for Linux installer (already covered by `install_xyz.py --tui`).
- Replacing `python3 install_xyz.py` in docs as the **only** path; keep both until `installer.sh` is stable.

## Windows installer baseline (already shipped)

These items are **done** on Windows and are the reference behaviour for Linux parity.

| Area | Behaviour |
|------|-----------|
| `installer.bat` | No interactive “Enable ANSI colors…” session prompt; `try_enable_vt` + `init_esc` (`ESC` via PowerShell `Write-Output ([char]0x1B)` with `cmd` `$E` fallback). |
| Menu | ASCII only (`-` lines, no em dash); `choice /C 12345Q` for main menu. |
| Confirmations | `:confirm_yes_no` with `set /p`, label `[Y/n]`, empty / Enter = yes. |
| Layout | `get_term_width` (clamp 40–120, margin like integrated terminals); dynamic `=` border; colour only when VT OK and `ESC` is set. |
| Install path | After successful install, hint to open a **new** terminal for `PATH`. |
| `install_xyz.py` | `schtasks /create` wrapped in `try` / `except subprocess.CalledProcessError`: log `[WARN]`, **continue** so shim / PATH steps can still finish. |
| `bin/menu.py` | `terminal_width()` uses `columns - 3` (extra margin for embedded terminals). |
| `README.md` | Documents auto-VT, `[Y/n]`, no ANSI session prompt, `schtasks` soft-fail, and links this plan from the Linux row. |

**Doc nit (optional):** [`scripts/enable_conhost_vt.ps1`](../scripts/enable_conhost_vt.ps1) header still mentions “when the user opts in”; `installer.bat` now enables VT automatically — align the comment in a small follow-up PR.

## Coherence audit (read-only)

Cross-check of **Windows** implementation vs docs (no test run required for this table).

| Check | Result |
|-------|--------|
| No ANSI opt-in prompt in `.bat` | OK |
| Reliable `ESC` for ANSI | OK |
| ASCII menu lines | OK |
| `[Y/n]` + Enter = yes | OK |
| Dynamic width + coloured frame when VT OK | OK |
| `schtasks` does not abort full install | OK |
| `menu.py` margin `-3` | OK |
| README + feature table vs behaviour | OK |

**Minor / future risks**

- `:confirm_yes_no` uses `echo %~1`; unusual characters (`&`, `|`, `<`) in a future message could break under `cmd.exe` — current strings are safe.
- **CI:** `installer.bat` is not linted by `bash -n` (expected). When **`installer.sh`** exists, add `bash -n installer.sh` to the Linux workflow (see Phase 5).

## Verification

### Linux (`installer.sh`)

- Run `./installer.sh` from bash and zsh; narrow terminal width; `LANG=C` / non-UTF-8 locale.
- Decline uv / decline venv / run install and confirm Python second prompts still appear.

### Windows (`installer.bat`, regression)

- From **PowerShell** and **CMD**: run `installer.bat` — borders coloured when VT is OK; no raw `38;5;118m` without proper escape framing.
- Narrow window: border width stays within usable width.
- Run install with a policy that **denies** `schtasks`: expect `[WARN]` in console; confirm shim / PATH still complete if the rest of install succeeds; new terminal + `where xyz-scrcpy`.

### Automated (repo)

- `python -m unittest discover -s tests -p "test_*.py"` (e.g. 73 tests) after substantive changes.

## Recommended next steps

1. **Automated:** run the unittest suite locally or in CI after edits.
2. **Windows manual:** execute the regression checklist above (PowerShell + CMD, narrow width, `schtasks` denied).
3. **Docs:** optional one-line fix in `enable_conhost_vt.ps1` header to match auto-VT from `installer.bat`.
4. **This plan — implementation:** deliver **`installer.sh`** by phases (skeleton → uv/bootstrap → colours/width → confirmations / `install_xyz` → README + `bash -n` in CI).
5. **Follow-up PR (optional):** mirror `schtasks` soft-fail on Linux by catching `CalledProcessError` around **`systemctl --user`** in `install_service` when that path is strict, log `[WARN]`, continue when the rest of install can proceed (see parity matrix row).
