#!/usr/bin/env python3
"""Open commands in a platform terminal emulator (shared by installer, launcher, monitor)."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


@dataclass
class TerminalOpenResult:
    ok: bool
    method: str = ""
    reason: str = ""
    tried: list[str] = field(default_factory=list)


def launcher_geometry() -> str:
    """Default size for the interactive menu (wide enough for the TUI, not the 40x18 monitor popup)."""
    try:
        size = shutil.get_terminal_size(fallback=(100, 28))
        cols = min(max(size.columns, 80), 132)
        rows = min(max(size.lines, 30), 42)
        return f"{cols}x{rows}"
    except OSError:
        return "100x28"


def is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def probe_graphical_session() -> tuple[bool, str]:
    system = platform.system()
    if system == "Windows":
        return True, ""
    if system == "Darwin":
        return True, ""
    if system != "Linux":
        return False, f"unsupported_platform:{system}"
    if is_wsl() and not os.environ.get("DISPLAY"):
        return False, "wsl_no_display: use Windows host adb or WSLg with DISPLAY set"
    if not os.environ.get("DISPLAY"):
        return False, "no_display: set DISPLAY or run from a graphical session"
    if not os.environ.get("XDG_RUNTIME_DIR"):
        return False, "no_xdg_runtime_dir: log in to a desktop session (systemd user)"
    return True, ""


def _linux_terminal_specs(
    geometry: str,
    title: str,
    argv: Sequence[str],
    *,
    hide_menubar: bool = False,
) -> list[tuple[str, list[str]]]:
    """Return (emulator_name, argv) pairs in try order."""
    py = argv[0]
    rest = list(argv[1:])
    joined_rest = " ".join(shlex.quote(a) for a in rest)
    full_cmd = f"{shlex.quote(py)} {joined_rest}".strip() if rest else shlex.quote(py)

    specs: list[tuple[str, list[str]]] = []
    gnome_flags = ["--geometry=" + geometry, f"--title={title}", "--"]
    if hide_menubar:
        gnome_flags = ["--hide-menubar"] + gnome_flags
    specs.append(
        (
            "gnome-terminal",
            ["gnome-terminal", *gnome_flags, py, *rest],
        )
    )
    specs.append(
        (
            "x-terminal-emulator",
            ["x-terminal-emulator", "-geometry", geometry, "-title", title, "-e", full_cmd],
        )
    )
    specs.append(
        (
            "xfce4-terminal",
            [
                "xfce4-terminal",
                f"--geometry={geometry}",
                f"--title={title}",
                "--command",
                full_cmd,
            ],
        )
    )
    specs.append(
        (
            "konsole",
            ["konsole", "--geometry", geometry, "--new-tab", "-e", py, *rest],
        )
    )
    cols, _, rows = geometry.partition("x")
    if rows:
        specs.append(
            (
                "xterm",
                ["xterm", "-geometry", f"{cols}x{rows}", "-T", title, "-e", py, *rest],
            )
        )
    return specs


def _merge_env(base: Mapping[str, str] | None, extra: Mapping[str, str] | None) -> dict[str, str]:
    env = dict(os.environ)
    if base:
        env.update(base)
    if extra:
        env.update(extra)
    return env


def _prepend_vendor_path(env: dict[str, str], cwd: Path) -> None:
    vendor = cwd / "vendor"
    if vendor.is_dir():
        env["PATH"] = str(vendor) + os.pathsep + env.get("PATH", "")


def open_command_in_terminal(
    *,
    argv: Sequence[str],
    cwd: Path,
    geometry: str | None = None,
    title: str = "XYZ-scrcpy",
    env: Mapping[str, str] | None = None,
    hide_menubar: bool = False,
) -> TerminalOpenResult:
    """Spawn argv in a new terminal window when possible."""
    if not argv:
        return TerminalOpenResult(ok=False, reason="empty_argv", tried=[])
    if geometry is None:
        geometry = launcher_geometry()

    system = platform.system()
    run_env = _merge_env(None, env)
    cwd_s = str(cwd.resolve())
    tried: list[str] = []

    if system == "Linux":
        ok_session, reason = probe_graphical_session()
        if not ok_session:
            return TerminalOpenResult(ok=False, method="", reason=reason, tried=[])

        for name, cmd in _linux_terminal_specs(geometry, title, argv, hide_menubar=hide_menubar):
            tried.append(name)
            if not shutil.which(cmd[0]):
                continue
            try:
                subprocess.Popen(
                    cmd,
                    cwd=cwd_s,
                    env=run_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return TerminalOpenResult(ok=True, method=name, reason="", tried=tried)
            except OSError:
                continue
        hint = "sudo apt install gnome-terminal"
        if is_wsl():
            hint = "WSL: install a GUI terminal or run xyz-scrcpy from Windows"
        return TerminalOpenResult(
            ok=False,
            method="",
            reason=f"no_terminal_emulator: tried {', '.join(tried)}; try: {hint}",
            tried=tried,
        )

    if system == "Darwin":
        tried.append("osascript")
        if not shutil.which("osascript"):
            return TerminalOpenResult(
                ok=False,
                reason="osascript_not_found",
                tried=tried,
            )
        script_path = argv[-1] if len(argv) > 1 else argv[0]
        py = argv[0]
        escaped = script_path.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "Terminal" to do script "{py} \\"{escaped}\\""'
        try:
            r = subprocess.run(
                ["osascript", "-e", script],
                cwd=cwd_s,
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                return TerminalOpenResult(ok=True, method="osascript", tried=tried)
            return TerminalOpenResult(
                ok=False,
                method="",
                reason=f"osascript_failed: exit {r.returncode}",
                tried=tried,
            )
        except OSError as exc:
            return TerminalOpenResult(ok=False, reason=str(exc), tried=tried)

    if system == "Windows":
        tried.append("windows_console")
        _prepend_vendor_path(run_env, cwd)
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        try:
            subprocess.Popen(
                list(argv),
                cwd=cwd_s,
                env=run_env,
                creationflags=flags,
            )
            return TerminalOpenResult(ok=True, method="windows_console", tried=tried)
        except OSError as exc:
            return TerminalOpenResult(ok=False, reason=str(exc), tried=tried)

    return TerminalOpenResult(
        ok=False,
        reason=f"unsupported_platform:{system}",
        tried=tried,
    )


def open_menu_script(
    *,
    menu_py: Path,
    python_exe: str,
    cwd: Path,
    geometry: str,
    title: str,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Monitor compatibility: open menu.py in external terminal."""
    result = open_command_in_terminal(
        argv=[python_exe, str(menu_py)],
        cwd=cwd,
        geometry=geometry,
        title=title,
        env=env,
    )
    return result.ok
