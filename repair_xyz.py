#!/usr/bin/env python3
"""Repair workflow: stop duplicate app processes, validate Python syntax, restart monitor service."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
BIN_DIR = REPO_DIR / "bin"
TASK_NAME = "XYZScrcpyMonitor"


def _py() -> str:
    return sys.executable or "python3"


def kill_xyz_processes() -> None:
    import psutil

    needles = (str(BIN_DIR / "menu.py"), str(BIN_DIR / "monitor.py"))
    repo = str(REPO_DIR)
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or ())
        except (psutil.Error, TypeError):
            continue
        if not cmd or repo not in cmd:
            continue
        if any(n in cmd for n in needles):
            try:
                proc.terminate()
            except psutil.Error:
                pass
    time.sleep(1)


def clear_runtime_locks() -> None:
    tmp = Path(tempfile.gettempdir())
    for name in ("xyz_menu.lock", "xyz_monitor.pid", "xyz_monitor_serials.state"):
        p = tmp / name
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def validate_syntax() -> None:
    py = _py()
    targets = [
        REPO_DIR / "install_xyz.py",
        BIN_DIR / "menu.py",
        BIN_DIR / "config_loader.py",
        BIN_DIR / "monitor.py",
        BIN_DIR / "check_and_repair.py",
        BIN_DIR / "launch_with_checks.py",
    ]
    for t in targets:
        if t.is_file():
            subprocess.check_call([py, "-m", "py_compile", str(t)], cwd=str(REPO_DIR))


def restart_service() -> None:
    system = platform.system()
    if system == "Linux":
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["systemctl", "--user", "restart", "scrcpy-auto.service"],
            check=False,
        )
        return
    if system == "Windows":
        subprocess.run(
            ["schtasks", "/end", "/tn", TASK_NAME],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["schtasks", "/run", "/tn", TASK_NAME],
            check=False,
            capture_output=True,
        )


def main() -> int:
    os.chdir(REPO_DIR)
    print("[1/3] Cleaning processes and locks...")
    try:
        kill_xyz_processes()
    except ImportError:
        print("Warning: psutil not available; skip process cleanup.")
    clear_runtime_locks()

    print("[2/3] Validating code integrity...")
    try:
        validate_syntax()
    except subprocess.CalledProcessError:
        print("ERROR: Syntax validation failed.")
        return 1

    print("[3/3] Restarting monitor service / scheduled task...")
    restart_service()
    print("Repair completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
