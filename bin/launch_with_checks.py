#!/usr/bin/env python3
"""Pre-check launcher then start the interactive menu (portable)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent
REPO_DIR = BIN_DIR.parent
CHECK_PY = BIN_DIR / "check_and_repair.py"
MENU_SCRIPT = BIN_DIR / "menu.py"
LOG_FILE = REPO_DIR / "config" / "check.log"
FULL_LOG_FILE = REPO_DIR / "config" / "full-check.log"
FULL_PID_FILE = Path(tempfile.gettempdir()) / "xyz_full_checks.pid"
ISSUE_BASE = "https://github.com/xyz-rainbow/xyz-scrcpy/issues/new"


def _py() -> str:
    return sys.executable or "python3"


def open_detached_menu_terminal() -> bool:
    if os.environ.get("XYZ_LAUNCHER_WINDOW") == "1":
        return False
    if os.environ.get("XYZ_SKIP_MENU_EXEC") == "1":
        return False
    if platform.system() != "Linux":
        return False
    if not os.environ.get("DISPLAY") or not os.environ.get("XDG_RUNTIME_DIR"):
        return False
    gnome = shutil.which("gnome-terminal")
    if not gnome:
        return False
    script = str(Path(__file__).resolve())
    cmd = [
        gnome,
        "--hide-menubar",
        "--geometry=40x18",
        "--title=XYZ Launcher",
        "--",
        "bash",
        "-lc",
        f'XYZ_LAUNCHER_WINDOW=1 exec "{_py()}" "{script}"',
    ]
    try:
        subprocess.Popen(cmd, cwd=str(REPO_DIR), start_new_session=True)
        return True
    except OSError:
        return False


def start_background_full_checks() -> None:
    if FULL_PID_FILE.is_file():
        try:
            import psutil

            old = int(FULL_PID_FILE.read_text(encoding="utf-8").strip())
            if psutil.pid_exists(old):
                return
        except (ValueError, ImportError, OSError):
            pass
    env = os.environ.copy()
    env["XYZ_CHECK_MODE"] = "full"
    env["XYZ_CHECK_LOG_FILE"] = str(FULL_LOG_FILE)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0
    try:
        proc = subprocess.Popen(
            [_py(), str(CHECK_PY)],
            cwd=str(REPO_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            start_new_session=True,
        )
        FULL_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except OSError:
        pass


def _issue_body() -> str:
    import platform as plat

    os_info = plat.platform()
    scrcpy_info = "scrcpy unknown"
    try:
        out = subprocess.check_output(["scrcpy", "--version"], text=True, stderr=subprocess.STDOUT, timeout=5)
        scrcpy_info = (out or "").splitlines()[0].strip() if out else scrcpy_info
    except (OSError, subprocess.SubprocessError):
        pass
    log_snippet = crash_snippet = timing_snippet = ""
    if LOG_FILE.is_file():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        interesting = [ln for ln in lines[-120:] if ln.startswith("[") or any(x in ln for x in ("Traceback", "FAILED", "ERROR"))]
        log_snippet = "\n".join(interesting[-40:]).strip()
        keys = ("traceback", "exception", "error", "failed", "segmentation fault", "core dumped")
        matches = [ln for ln in lines if any(k in ln.lower() for k in keys)]
        crash_snippet = "\n".join(matches[-25:]).strip()
        timing = [ln for ln in lines if "Timing:" in ln]
        timing_snippet = "\n".join(timing[-5:]).strip()
    return (
        "## What happened\nFail-open mode was triggered by launch checks.\n\n"
        "## Environment\n- Launcher: xyz-scrcpy\n- Check mode: fail-open\n\n"
        f"## System info\n- OS: {os_info}\n- {scrcpy_info}\n\n"
        "## Time log\n```\n" + (timing_snippet or "(no timing info found)") + "\n```\n\n"
        "## Crash context (sanitized)\n```\n" + (crash_snippet or "(no crash context found)") + "\n```\n\n"
        "## Sanitized log excerpt\n```\n" + (log_snippet or "(no log excerpt)") + "\n```\n"
    )


def open_prefilled_issue() -> None:
    title = "Fail-open detected during launcher checks"
    params = urllib.parse.urlencode({"title": title, "body": _issue_body()})
    url = ISSUE_BASE + "?" + params
    if shutil.which("xdg-open") and platform.system() == "Linux":
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[INFO] Opened prefilled issue page in browser.")
    else:
        try:
            webbrowser.open(url)
            print("[INFO] Opened prefilled issue page in browser.")
        except Exception:
            print("[INFO] Open this prefilled issue URL manually:")
            print(url)


def run_quick_checks() -> str:
    env = os.environ.copy()
    env["XYZ_CHECK_MODE"] = "quick"
    proc = subprocess.run(
        [_py(), str(CHECK_PY)],
        cwd=str(REPO_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    out = (proc.stdout or "").strip().splitlines()
    return out[-1].strip() if out else "UNKNOWN"


def main() -> int:
    if open_detached_menu_terminal():
        return 0

    if os.environ.get("XYZ_CHECKS_ALREADY_DONE") == "1":
        status = os.environ.get("XYZ_CHECKS_STATUS", "PASS")
        print(f"[INFO] Reusing installer check result: {status}")
    else:
        print("[INFO] Running quick syntax checks...")
        status = run_quick_checks()

    if status in ("PASS", "PASS_AFTER_REPAIR"):
        start_background_full_checks()
        if FULL_LOG_FILE.is_file():
            print(f"[INFO] Full test suite is running in background: {FULL_LOG_FILE}")
        else:
            print("[INFO] Full test suite started in background.")
    elif status == "FAIL_OPEN":
        print("[WARNING] Automated checks are still failing.")
        print("[WARNING] Fail-open mode is available.")
        print("[WARNING] Please report with logs: https://github.com/xyz-rainbow/xyz-scrcpy/issues")
        print(
            "[WARNING] GitHub issue creation requires login; or email log to "
            "rainbow@rainbowtechnology.xyz"
        )
        open_issue = input("Open prefilled GitHub issue page now? (Y/n): ").strip().lower()
        if not open_issue or open_issue in ("y", "yes"):
            open_prefilled_issue()
        open_anyway = input("Open menu anyway despite errors? (Y/n): ").strip().lower()
        if open_anyway and open_anyway not in ("y", "yes"):
            print("[INFO] Menu launch cancelled by user.")
            return 1
    else:
        print(f"[WARNING] Unknown check status: {status}")

    if LOG_FILE.is_file():
        print("[INFO] Check log: ./config/check.log")

    if os.environ.get("XYZ_SKIP_MENU_EXEC") == "1":
        print("[INFO] Test mode: menu execution skipped.")
        return 0

    print("[INFO] Launching interactive menu...")
    os.execv(_py(), [_py(), str(MENU_SCRIPT)])


if __name__ == "__main__":
    raise SystemExit(main())
