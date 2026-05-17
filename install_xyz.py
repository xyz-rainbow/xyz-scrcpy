#!/usr/bin/env python3
"""XYZ-scrcpy installer (multi-OS, semi-interactive)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import traceback
import platform
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import win_path_shim as wps
import adb_resolve

_BIN_DIR = Path(__file__).resolve().parent / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))
import terminal_open  # noqa: E402
from terminal_open import TerminalOpenResult  # noqa: E402


APP_NAME = "xyz-scrcpy"
TASK_NAME = "XYZScrcpyMonitor"
DEFAULT_ALIAS = "xyz-scrcpy"


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True)


def run_cmd_quiet(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _schtasks_run_logged(
    cmd: list[str],
    *,
    label: str,
    verbose: bool,
    install_dir: Path | None,
) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if verbose:
        print(f"[verbose] {label} exit={proc.returncode}")
    if verbose and install_dir and install_dir.exists():
        wps.log_install_line(install_dir, f"[schtasks] {label} exit={proc.returncode}", verbose=False)
    return proc


def ask_choice(prompt: str, options: list[str], default: str | None = None) -> str:
    while True:
        suffix = f" [{'/'.join(options)}]"
        if default:
            suffix += f" (default: {default})"
        answer = input(f"{prompt}{suffix}: ").strip().lower()
        if not answer and default:
            return default
        if answer in options:
            return answer
        print("Invalid option. Try again.")


def ask_input(prompt: str, default: str | None = None) -> str:
    suffix = f" (default: {default})" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    if not answer and default:
        return default
    return answer


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    options = "Y/n" if default_yes else "y/N"
    answer = input(f"{prompt} ({options}): ").strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}


def normalize_alias(alias: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]", "-", alias.strip())
    clean = re.sub(r"-{2,}", "-", clean).strip("-")
    return clean or DEFAULT_ALIAS


def detect_paths(os_name: str, home: Path) -> dict[str, Path]:
    if os_name == "linux":
        install_dir = home / ".local" / "share" / APP_NAME
        launcher_dir = home / ".local" / "bin"
        service_path = home / ".config" / "systemd" / "user" / "scrcpy-auto.service"
        return {
            "install_dir": install_dir,
            "launcher_dir": launcher_dir,
            "service_file": service_path,
        }
    if os_name == "darwin":
        install_dir = home / "Library" / "Application Support" / APP_NAME
        launcher_dir = home / "bin"
        service_path = home / "Library" / "LaunchAgents" / "com.xyz.scrcpy.monitor.plist"
        return {
            "install_dir": install_dir,
            "launcher_dir": launcher_dir,
            "service_file": service_path,
        }
    appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    install_dir = appdata / APP_NAME
    launcher_dir = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return {
        "install_dir": install_dir,
        "launcher_dir": launcher_dir,
        "service_file": appdata / f"{APP_NAME}.task.txt",
    }


def launcher_path(os_name: str, launcher_dir: Path, alias: str) -> Path:
    if os_name == "windows":
        return launcher_dir / f"{alias}.cmd"
    return launcher_dir / alias


def _is_managed_launcher(launcher_file: Path, install_dir: Path) -> bool:
    if not launcher_file.exists() or not launcher_file.is_file():
        return False
    markers = (
        str(install_dir / "bin" / "launch_with_checks.sh"),
        str(install_dir / "bin" / "launch_with_checks.py"),
    )
    try:
        content = launcher_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(m in content for m in markers)


def remove_managed_launchers(paths: dict[str, Path], os_name: str, primary_alias: str) -> None:
    launcher_dir = paths["launcher_dir"]
    install_dir = paths["install_dir"]
    primary_path = launcher_path(os_name, launcher_dir, primary_alias)

    # Remove the primary detected alias first.
    if primary_path.exists():
        primary_path.unlink()

    # Defensive cleanup: remove any leftover launchers managed by this install.
    if not launcher_dir.exists():
        return
    for entry in launcher_dir.iterdir():
        if entry == primary_path:
            continue
        if _is_managed_launcher(entry, install_dir):
            entry.unlink()


def copy_project(src_root: Path, dst_root: Path) -> None:
    ignore = shutil.ignore_patterns(
        ".git",
        ".github",
        "__pycache__",
        "*.pyc",
        ".cursor",
        ".claude",
        "agent-transcripts",
        ".venv",
    )
    if dst_root.exists():
        shutil.rmtree(dst_root)
    shutil.copytree(src_root, dst_root, ignore=ignore)


@dataclass
class RuntimeStatus:
    method: str
    message: str = ""


def python_for_post_install(install_dir: Path, os_name: str) -> str:
    if os_name == "windows":
        return str(install_dir / ".venv" / "Scripts" / "python.exe")
    venv_py = install_dir / ".venv" / "bin" / "python3"
    if venv_py.is_file():
        return str(venv_py)
    return shutil.which("python3") or "python3"


def _python_has_pip(py: str) -> bool:
    proc = subprocess.run(
        [py, "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _python_imports_psutil(py: str) -> bool:
    proc = subprocess.run(
        [py, "-c", "import psutil"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def ensure_windows_runtime_venv(install_dir: Path) -> None:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError(
            "Windows install requires 'uv' on PATH to create the runtime .venv. "
            "Install uv from https://github.com/astral-sh/uv"
        )
    venv_dir = install_dir / ".venv"
    run_cmd([uv, "venv", str(venv_dir)], check=True)
    req = install_dir / ".requirements.txt"
    if not req.is_file():
        raise FileNotFoundError(f"Missing .requirements.txt after install copy: {req}")
    run_cmd([uv, "pip", "install", "-r", str(req)], check=True)


def ensure_linux_runtime(install_dir: Path, *, verbose: bool = False) -> RuntimeStatus:
    """Install Python deps into install_dir/.venv when possible (uv > venv+pip > warn)."""
    req = install_dir / ".requirements.txt"
    venv_dir = install_dir / ".venv"
    venv_py = venv_dir / "bin" / "python3"
    uv = shutil.which("uv")

    if uv and req.is_file():
        try:
            run_cmd([uv, "venv", str(venv_dir)], check=True)
            run_cmd([uv, "pip", "install", "-r", str(req)], check=True)
            msg = "Linux runtime: uv venv + requirements installed."
            print(msg)
            wps.log_install_line(install_dir, msg, verbose=verbose)
            return RuntimeStatus("venv_ok", msg)
        except subprocess.CalledProcessError as exc:
            warn = f"[WARN] uv venv/pip failed: {exc}"
            print(warn)
            wps.log_install_line(install_dir, warn, verbose=verbose)

    py = shutil.which("python3")
    if not py:
        msg = (
            "[WARN] python3 not found. Install python3-venv and python3-pip, or install uv: "
            "https://github.com/astral-sh/uv"
        )
        print(msg)
        wps.log_install_line(install_dir, msg, verbose=verbose)
        return RuntimeStatus("failed", msg)

    if _python_has_pip(py) and req.is_file():
        try:
            run_cmd([py, "-m", "venv", str(venv_dir)], check=False)
            if venv_py.is_file():
                proc = subprocess.run(
                    [str(venv_py), "-m", "pip", "install", "-r", str(req)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and _python_imports_psutil(str(venv_py)):
                    msg = "Linux runtime: stdlib venv + pip install OK."
                    print(msg)
                    wps.log_install_line(install_dir, msg, verbose=verbose)
                    return RuntimeStatus("venv_ok", msg)
                if "externally-managed-environment" in (proc.stderr or ""):
                    hint = (
                        "[WARN] PEP 668 blocked pip in venv; install uv or: "
                        "sudo apt install python3-venv python3-pip"
                    )
                    print(hint)
                    wps.log_install_line(install_dir, hint, verbose=verbose)
        except OSError as exc:
            wps.log_install_line(install_dir, f"[WARN] venv create failed: {exc}", verbose=verbose)

        proc = subprocess.run(
            [py, "-m", "pip", "install", "--user", "psutil>=5.9"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and _python_imports_psutil(py):
            msg = "Linux runtime: psutil installed with pip --user."
            print(msg)
            wps.log_install_line(install_dir, msg, verbose=verbose)
            return RuntimeStatus("pip_user", msg)

    msg = (
        "[WARN] Could not install psutil (pip missing or blocked). "
        "Try: sudo apt install python3-venv python3-pip adb scrcpy\n"
        "Or install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    )
    print(msg)
    wps.log_install_line(install_dir, msg, verbose=verbose)
    return RuntimeStatus("failed", msg)


def verify_linux_psutil(install_dir: Path, os_name: str) -> None:
    if os_name != "linux":
        return
    py = python_for_post_install(install_dir, os_name)
    if _python_imports_psutil(py):
        return
    print(f"[WARN] psutil not importable with {py}; monitor may fail until dependencies are fixed.")


def write_launcher(os_name: str, launcher: Path, install_dir: Path) -> None:
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if os_name in ("linux", "darwin"):
        content = f"""#!/usr/bin/env bash
bash "{install_dir / 'bin' / 'launch_with_checks.sh'}"
"""
    else:
        win_inst = str(install_dir).replace("/", "\\")
        vpy = str(install_dir / ".venv" / "Scripts" / "python.exe").replace("/", "\\")
        lpy = str(install_dir / "bin" / "launch_with_checks.py").replace("/", "\\")
        content = (
            "@echo off\r\n"
            f'set "PATH={win_inst}\\vendor;%PATH%"\r\n'
            f'"{vpy}" "{lpy}"\r\n'
        )
    launcher.write_text(content, encoding="utf-8")
    if os_name in ("linux", "darwin"):
        launcher.chmod(0o755)


def config_path(install_dir: Path) -> Path:
    return install_dir / "config" / "config.json"


def read_installed_alias(install_dir: Path) -> str:
    cfg_path = config_path(install_dir)
    if not cfg_path.exists():
        return DEFAULT_ALIAS
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return normalize_alias(str(data.get("command_alias", DEFAULT_ALIAS)))
    except (json.JSONDecodeError, OSError, ValueError):
        return DEFAULT_ALIAS


def save_alias_to_config(install_dir: Path, alias: str) -> None:
    cfg_path = config_path(install_dir)
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
    cfg["command_alias"] = normalize_alias(alias)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def linux_service_content(install_dir: Path) -> str:
    monitor = install_dir / "bin" / "monitor.sh"
    log_path = install_dir / "config" / "scrcpy.log"
    display = os.environ.get("DISPLAY", ":0")
    session_type = os.environ.get("XDG_SESSION_TYPE", "")
    env_lines = f"Environment=DISPLAY={display}\n"
    if session_type:
        env_lines += f"Environment=XDG_SESSION_TYPE={session_type}\n"
    return f"""[Unit]
Description=XYZ / Rainbowtechnology - scrcpy Auto-Monitor Service
After=network.target

[Service]
ExecStart=/bin/bash {monitor}
Restart=always
RestartSec=10
{env_lines}StandardOutput=append:{log_path}
StandardError=append:{log_path}

[Install]
WantedBy=default.target
"""


def mac_plist_content(install_dir: Path) -> str:
    monitor = install_dir / "bin" / "monitor.sh"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.xyz.scrcpy.monitor</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>{monitor}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
"""


def install_service(
    os_name: str,
    service_file: Path,
    install_dir: Path,
    enable_service: bool,
    *,
    verbose: bool = False,
) -> None:
    if os_name == "linux":
        service_file.parent.mkdir(parents=True, exist_ok=True)
        service_file.write_text(linux_service_content(install_dir), encoding="utf-8")
        if not shutil.which("systemctl"):
            msg = "[WARN] systemctl not found; skipping user service setup."
            print(msg)
            wps.log_install_line(install_dir, msg, verbose=verbose)
            return
        try:
            run_cmd(["systemctl", "--user", "daemon-reload"])
            if enable_service:
                run_cmd(["systemctl", "--user", "enable", "--now", "scrcpy-auto.service"])
            else:
                run_cmd(["systemctl", "--user", "disable", "scrcpy-auto.service"], check=False)
                run_cmd(["systemctl", "--user", "stop", "scrcpy-auto.service"], check=False)
        except subprocess.CalledProcessError as exc:
            msg = (
                f"[WARN] systemctl --user failed (exit {exc.returncode}). "
                "User session or systemd user instance may be unavailable (SSH/WSL). "
                "Install completed; enable manually: systemctl --user enable --now scrcpy-auto.service"
            )
            print(msg)
            wps.log_install_line(install_dir, msg, verbose=verbose)
        return
    if os_name == "darwin":
        service_file.parent.mkdir(parents=True, exist_ok=True)
        service_file.write_text(mac_plist_content(install_dir), encoding="utf-8")
        run_cmd(["launchctl", "unload", str(service_file)], check=False)
        run_cmd(["launchctl", "load", str(service_file)])
        return
    menu_script = install_dir / "bin" / "monitor.py"
    pythonw = install_dir / ".venv" / "Scripts" / "pythonw.exe"
    inst = str(install_dir).replace("/", "\\")
    pyw = str(pythonw).replace("/", "\\")
    mon = str(menu_script).replace("/", "\\")
    sch = shutil.which("schtasks")
    if not sch:
        msg = (
            "[WARN] schtasks.exe not found (e.g. some Server Core / reduced SKUs). "
            "Skipping Scheduled Task; enable the monitor manually if needed."
        )
        print(msg)
        wps.log_install_line(install_dir, msg, verbose=False)
        service_file.parent.mkdir(parents=True, exist_ok=True)
        service_file.write_text(TASK_NAME)
        return
    task_tr = f'cmd /c cd /d "{inst}" && set "PATH={inst}\\vendor;%PATH%" && "{pyw}" "{mon}"'
    try:
        run_cmd(
            [
                sch,
                "/create",
                "/f",
                "/sc",
                "onlogon",
                "/tn",
                TASK_NAME,
                "/tr",
                task_tr,
            ]
        )
    except subprocess.CalledProcessError as exc:
        msg = (
            f"[WARN] schtasks /create failed (exit {exc.returncode}). "
            "Often policy or elevation. Skipping scheduled task; "
            "install will still configure the CLI shim and user PATH. "
            "Create the task manually if you need logon auto-start."
        )
        print(msg)
        wps.log_install_line(install_dir, msg, verbose=False)
    if not enable_service:
        run_cmd([sch, "/end", "/tn", TASK_NAME], check=False)
    service_file.parent.mkdir(parents=True, exist_ok=True)
    service_file.write_text(TASK_NAME, encoding="utf-8")


def stop_service(
    os_name: str,
    service_file: Path,
    *,
    verbose: bool = False,
    install_dir: Path | None = None,
) -> None:
    if os_name == "linux":
        run_cmd_quiet(["systemctl", "--user", "stop", "scrcpy-auto.service"])
        return
    if os_name == "darwin":
        run_cmd_quiet(["launchctl", "unload", str(service_file)])
        return
    sch = shutil.which("schtasks")
    if not sch:
        return
    _schtasks_run_logged(
        [sch, "/end", "/tn", TASK_NAME],
        label=f"/end /tn {TASK_NAME}",
        verbose=verbose,
        install_dir=install_dir,
    )


def uninstall_service(
    os_name: str,
    service_file: Path,
    *,
    verbose: bool = False,
    install_dir: Path | None = None,
) -> None:
    if os_name == "linux":
        run_cmd_quiet(["systemctl", "--user", "disable", "--now", "scrcpy-auto.service"])
        if service_file.exists():
            service_file.unlink()
        run_cmd_quiet(["systemctl", "--user", "daemon-reload"])
        return
    if os_name == "darwin":
        run_cmd_quiet(["launchctl", "unload", str(service_file)])
        if service_file.exists():
            service_file.unlink()
        return
    sch = shutil.which("schtasks")
    if not sch:
        if service_file.exists():
            service_file.unlink()
        return
    _schtasks_run_logged(
        [sch, "/delete", "/tn", TASK_NAME, "/f"],
        label=f"/delete /tn {TASK_NAME} /f",
        verbose=verbose,
        install_dir=install_dir,
    )
    if service_file.exists():
        service_file.unlink()


def check_dependencies(os_name: str, *, verbose: bool = False, project_root: Path | None = None) -> None:
    required = ["adb", "scrcpy"]
    required.insert(0, "python" if os_name == "windows" else "python3")
    missing = []
    for dep in required:
        if dep == "adb" and project_root is not None:
            if adb_resolve.resolve_adb_executable(project_root)[1] != "not_found":
                continue
        if shutil.which(dep) is None:
            missing.append(dep)
    if missing:
        msg = f"Warning: Missing dependencies: {', '.join(missing)}"
        print(msg)
        if verbose:
            logging.getLogger("xyz_install").info(msg)
        print("Installation will continue, but runtime may fail until dependencies are installed.")
        if os_name == "linux" and any(d in missing for d in ("adb", "scrcpy")):
            print("Debian/Ubuntu hint: sudo apt install adb scrcpy")
    if os_name == "linux" and shutil.which("pactl") is None:
        print("Notice: 'pactl' not found. Microphone Bus feature (xyz-mic-input) will fallback gracefully.")
    if os_name == "linux":
        emulators = (
            "gnome-terminal",
            "x-terminal-emulator",
            "xfce4-terminal",
            "konsole",
            "xterm",
        )
        if not any(shutil.which(e) for e in emulators):
            print(
                "Notice: no common terminal emulator on PATH. "
                "Post-install mini window may not open; try: sudo apt install gnome-terminal"
            )


def run_post_install_checks(install_dir: Path, os_name: str) -> tuple[str, str]:
    check_script = install_dir / "bin" / "check_and_repair.py"
    py = python_for_post_install(install_dir, os_name)
    proc = subprocess.run(
        [py, str(check_script)],
        text=True,
        capture_output=True,
        check=False,
        cwd=str(install_dir),
    )
    status = (proc.stdout or "").strip().splitlines()
    status_code = status[-1].strip() if status else "UNKNOWN"
    log_path = install_dir / "config" / "check.log"
    summary = f"Check result: {status_code}"
    if log_path.exists():
        summary += " | log: ./config/check.log"
    return status_code, summary


def show_check_log(install_dir: Path) -> None:
    log_path = install_dir / "config" / "check.log"
    if not log_path.exists():
        print("No check log generated.")
        return
    print("\n--- check.log (last 40 lines) ---")
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[-120:]:
        if line.startswith("[") or "Ran " in line or line in {"OK", "FAILED"} or "Please report this issue" in line:
            print(line)
    print("--- end of check.log ---\n")


def _launcher_check_env(prechecked_status: str | None) -> dict[str, str]:
    env: dict[str, str] = {"XYZ_LAUNCHER_WINDOW": "1"}
    if prechecked_status:
        env["XYZ_CHECKS_ALREADY_DONE"] = "1"
        env["XYZ_CHECKS_STATUS"] = prechecked_status
    return env


def open_initial_menu(
    os_name: str,
    install_dir: Path,
    prechecked_status: str | None = None,
) -> TerminalOpenResult:
    launcher_py = install_dir / "bin" / "launch_with_checks.py"
    py = python_for_post_install(install_dir, os_name)
    return terminal_open.open_command_in_terminal(
        argv=[py, str(launcher_py)],
        cwd=install_dir,
        geometry="40x18",
        title="XYZ Initial Menu",
        env=_launcher_check_env(prechecked_status),
        hide_menubar=(os_name == "linux"),
    )


def run_menu_inline(
    os_name: str,
    install_dir: Path,
    prechecked_status: str | None = None,
) -> None:
    launcher_py = install_dir / "bin" / "launch_with_checks.py"
    py = python_for_post_install(install_dir, os_name)
    env = dict(os.environ)
    env.update(_launcher_check_env(prechecked_status))
    env.pop("XYZ_LAUNCHER_WINDOW", None)
    subprocess.run([py, str(launcher_py)], check=False, cwd=str(install_dir), env=env)


def report_initial_menu_result(
    result: TerminalOpenResult,
    alias: str,
    *,
    non_interactive: bool,
    verbose: bool = False,
    os_name: str = "linux",
    install_dir: Path | None = None,
) -> None:
    line = (
        f"terminal_open ok={result.ok} method={result.method!r} reason={result.reason!r} tried={result.tried}"
    )
    if install_dir:
        wps.log_install_line(install_dir, line, verbose=verbose)
    if verbose:
        print(f"[verbose] {line}")

    if result.ok:
        print(f"Mini terminal opened ({result.method}).")
        return

    print("Could not open a graphical terminal for the initial menu.")
    if result.reason:
        print(f"  Reason: {result.reason}")
    if result.tried:
        print(f"  Tried: {', '.join(result.tried)}")
    if os_name == "linux":
        print("  Hint: sudo apt install gnome-terminal   (or: sudo apt install xterm)")
    print(f"  Launch manually: {alias}")

    if non_interactive or not sys.stdin.isatty():
        return
    answer = input("Open menu in this terminal now? (Y/n): ").strip().lower()
    if not answer or answer in ("y", "yes"):
        if install_dir:
            run_menu_inline(os_name, install_dir)


def do_install(
    paths: dict[str, Path],
    src_root: Path,
    os_name: str,
    alias: str,
    enable_service: bool,
    run_tests_and_log: bool,
    *,
    verbose: bool = False,
    no_open_terminal: bool = False,
    non_interactive: bool = False,
) -> None:
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"Installing to: {paths['install_dir']}")
    check_dependencies(os_name, verbose=verbose, project_root=src_root)
    install_root = paths["install_dir"]
    previous_alias = read_installed_alias(install_root) if install_root.exists() else DEFAULT_ALIAS
    print("Running clean install (removing previous installation first)...")
    do_uninstall(paths, os_name, remove_app_files=True, remove_repo_copy=False, verbose=verbose)
    try:
        copy_project(src_root, paths["install_dir"])
        if os_name == "windows":
            ensure_windows_runtime_venv(paths["install_dir"])
        elif os_name == "linux":
            runtime = ensure_linux_runtime(paths["install_dir"], verbose=verbose)
            wps.log_install_line(
                paths["install_dir"],
                f"linux_runtime method={runtime.method} {runtime.message}",
                verbose=verbose,
            )
        save_alias_to_config(paths["install_dir"], alias)
        launch_path = launcher_path(os_name, paths["launcher_dir"], alias)
        previous_path = launcher_path(os_name, paths["launcher_dir"], previous_alias)
        if previous_path != launch_path and previous_path.exists():
            previous_path.unlink()
        write_launcher(os_name, launch_path, paths["install_dir"])
        install_service(
            os_name,
            paths["service_file"],
            paths["install_dir"],
            enable_service,
            verbose=verbose,
        )
        if os_name == "windows":
            pl = paths["install_dir"] / "config" / "path_changes.log"
            try:
                wps.windows_install_cli_shim(paths["install_dir"], alias, path_log=pl)
            except Exception:
                wps.windows_uninstall_cli_shim(paths["install_dir"], path_log=pl)
                raise
    except Exception as exc:
        detail = f"INSTALL FAILED: {exc}\n{traceback.format_exc()}"
        wps.log_install_line(paths["install_dir"], detail, verbose=verbose)
        raise
    print("Install completed.")
    print(f"Launcher: {launch_path}")
    verify_linux_psutil(paths["install_dir"], os_name)
    if os_name == "linux" and enable_service:
        print("Linux: user unit installed/enabled — start or check with: systemctl --user start scrcpy-auto.service")
    elif os_name == "linux":
        print("Linux: user unit installed but left disabled (your choice at install time).")

    if os_name == "windows":
        wps.warn_external_tools(paths["install_dir"], verbose=verbose)

    if run_tests_and_log:
        print("Running tests and validations now. Please wait...")
        status, summary = run_post_install_checks(paths["install_dir"], os_name)
        print(summary)
        show_check_log(paths["install_dir"])
        if status == "FAIL_OPEN":
            print("Checks still failing after repair.")
            print("Please report in GitHub Issues: https://github.com/xyz-rainbow/xyz-scrcpy/issues")
        if no_open_terminal:
            print("Skipping initial mini terminal (--no-open-terminal).")
        else:
            print("Opening initial mini terminal...")
            result = open_initial_menu(os_name, paths["install_dir"], prechecked_status=status)
            report_initial_menu_result(
                result,
                alias,
                non_interactive=non_interactive,
                verbose=verbose,
                os_name=os_name,
                install_dir=paths["install_dir"],
            )
    else:
        print("Tests skipped by user. Menu can still open in fail-open mode.")
        print("If issues appear, report in GitHub Issues: https://github.com/xyz-rainbow/xyz-scrcpy/issues")
        if no_open_terminal:
            print("Skipping initial mini terminal (--no-open-terminal).")
        else:
            print("Opening initial mini terminal...")
            result = open_initial_menu(os_name, paths["install_dir"])
            report_initial_menu_result(
                result,
                alias,
                non_interactive=non_interactive,
                verbose=verbose,
                os_name=os_name,
                install_dir=paths["install_dir"],
            )


def _safe_delete_repo_copy(repo_dir: Path) -> bool:
    """Delete repository folder with safety rails."""
    repo_dir = repo_dir.resolve()
    home = Path.home().resolve()
    if repo_dir in (Path("/"), home) or repo_dir == home.parent:
        return False
    # Basic guard to ensure we only remove an expected repo directory.
    if not (repo_dir / "install_xyz.py").exists():
        return False
    shutil.rmtree(repo_dir)
    return True


def do_uninstall(
    paths: dict[str, Path],
    os_name: str,
    remove_app_files: bool = True,
    remove_repo_copy: bool = False,
    repo_dir: Path | None = None,
    *,
    verbose: bool = False,
) -> None:
    print("Stopping service/task first...")
    idir = paths["install_dir"]
    stop_service(
        os_name,
        paths["service_file"],
        verbose=verbose,
        install_dir=idir if idir.exists() else None,
    )
    if os_name == "windows":
        pl = idir / "config" / "path_changes.log" if idir.exists() else None
        wps.windows_uninstall_cli_shim(idir, path_log=pl)
    print("Removing service/task from startup...")
    uninstall_service(
        os_name,
        paths["service_file"],
        verbose=verbose,
        install_dir=idir if idir.exists() else None,
    )
    install_dir = paths["install_dir"]
    alias = read_installed_alias(install_dir) if install_dir.exists() else DEFAULT_ALIAS
    remove_managed_launchers(paths, os_name, alias)
    if remove_app_files and paths["install_dir"].exists():
        shutil.rmtree(paths["install_dir"])
    elif not remove_app_files:
        print("Installed app files were kept by user choice.")
    if remove_repo_copy and repo_dir:
        if _safe_delete_repo_copy(repo_dir):
            print(f"Repository copy removed: {repo_dir}")
        else:
            print("Repository removal skipped by safety checks.")
    print("Uninstall completed.")


def do_sync_alias(paths: dict[str, Path], os_name: str, alias: str) -> None:
    install_dir = paths["install_dir"]
    if not install_dir.exists():
        print("Install directory not found. Run install first.")
        return
    previous_alias = read_installed_alias(install_dir)
    old_path = launcher_path(os_name, paths["launcher_dir"], previous_alias)
    new_path = launcher_path(os_name, paths["launcher_dir"], alias)
    if old_path != new_path and old_path.exists():
        old_path.unlink()
    save_alias_to_config(install_dir, alias)
    write_launcher(os_name, new_path, install_dir)
    if os_name == "windows" and wps.read_marker():
        mr = wps.read_marker() or {}
        prev_a = str(mr.get("alias") or "").strip()
        if prev_a and prev_a != alias:
            na = normalize_alias(prev_a)
            for ext in (".cmd", ".bat"):
                old_shim = wps.windows_shim_dir() / f"{na}{ext}"
                if old_shim.is_file():
                    try:
                        old_shim.unlink()
                    except OSError:
                        pass
        h, shim_cmd = wps.write_cli_shim_pair(wps.windows_shim_dir(), alias, install_dir)
        mr["alias"] = alias
        mr["shim_content_hash"] = h
        mr["shim_cmd"] = str(shim_cmd)
        wps.write_marker(mr)
    print(f"Alias synced: {alias}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XYZ-scrcpy multi-OS installer")
    parser.add_argument(
        "--action",
        choices=["install", "uninstall", "remove", "sync-alias", "diagnose"],
        help="Run without interactive action prompt.",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument("--alias", help="Custom launcher alias/command name.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging to console and install.log (Windows).")
    parser.add_argument(
        "--clean-user-path",
        action="store_true",
        help="With --action diagnose (Windows): remove HKCU Path segment(s) matching the xyz-scrcpy CLI shim directory.",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Interactive full-screen installer (same TUI style as bin/menu.py).",
    )
    parser.add_argument(
        "--no-open-terminal",
        action="store_true",
        help="Do not spawn the post-install mini terminal (CI/headless).",
    )
    return parser.parse_args()


def _run_install_tui(verbose: bool) -> int:
    import importlib.util

    path = Path(__file__).resolve().parent / "bin" / "install_tui.py"
    spec = importlib.util.spec_from_file_location("xyz_install_tui", path)
    if spec is None or spec.loader is None:
        print("Could not load install_tui module.")
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return int(mod.main(verbose=verbose))


def main() -> int:
    args = parse_args()
    os_name = platform.system().lower()
    if os_name not in {"linux", "darwin", "windows"}:
        print(f"Unsupported OS: {os_name}")
        return 1

    if args.tui:
        return _run_install_tui(verbose=args.verbose)

    src_root = Path(__file__).resolve().parent
    paths = detect_paths(os_name, Path.home())

    if args.action == "diagnose":
        if os_name != "windows":
            print("diagnose is only supported on Windows.")
            return 1
        inst = paths["install_dir"] if paths["install_dir"].exists() else None
        return wps.run_diagnose(inst, repo_root=src_root, clean_user_path=args.clean_user_path)

    action = args.action
    if not action:
        action = "install" if ask_yes_no("Install now", default_yes=True) else "uninstall"
    if action == "remove":
        action = "uninstall"

    if not args.yes:
        confirm = ask_choice(f"Confirm '{action}'", ["y", "n"], default="y")
        if confirm != "y":
            print("Aborted by user.")
            return 0

    try:
        if action in ("install", "sync-alias"):
            detected_alias = read_installed_alias(paths["install_dir"])
            if args.alias:
                alias = normalize_alias(args.alias)
            elif args.action:
                alias = detected_alias
            else:
                alias = normalize_alias(ask_input("Launcher alias", detected_alias))
            if action == "install":
                if args.yes:
                    enable_service = True
                    run_tests_and_log = True
                else:
                    enable_service = ask_yes_no("Enable service", default_yes=True)
                    run_tests_and_log = ask_yes_no("Run tests and view log", default_yes=True)
                do_install(
                    paths,
                    src_root,
                    os_name,
                    alias,
                    enable_service,
                    run_tests_and_log,
                    verbose=args.verbose,
                    no_open_terminal=args.no_open_terminal,
                    non_interactive=args.yes,
                )
            else:
                do_sync_alias(paths, os_name, alias)
        else:
            if args.yes:
                remove_files = True
                remove_repo_copy = False
            else:
                remove_files = ask_yes_no("Delete installed app files", default_yes=False)
                remove_repo_copy = ask_yes_no("Delete current repository copy", default_yes=False)
            do_uninstall(
                paths,
                os_name,
                remove_app_files=remove_files,
                remove_repo_copy=remove_repo_copy,
                repo_dir=src_root,
                verbose=args.verbose,
            )
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {' '.join(exc.cmd)}")
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Unexpected error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
