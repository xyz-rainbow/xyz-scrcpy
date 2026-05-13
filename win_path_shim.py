"""Windows user PATH shim, registry helpers, and CLI launcher .cmd generation (used by install_xyz.py)."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

APP_NAME = "xyz-scrcpy"
TASK_SCHED_NAME = "XYZScrcpyMonitor"
MARKER_FILENAME = "cli_path_marker.json"
BACKUP_FILENAME = ".path_backup.json"
PATH_LOG_MAX_BYTES = 5 * 1024 * 1024

_log = logging.getLogger("xyz_install")

# winreg imported lazily for non-Windows test imports
_winreg: Any = None


def _get_winreg():
    global _winreg
    if _winreg is None:
        import winreg as wr

        _winreg = wr
    return _winreg


def is_windows() -> bool:
    return sys.platform == "win32"


def windows_shim_root() -> Path:
    la = os.environ.get("LOCALAPPDATA")
    if la:
        return Path(la) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def windows_shim_dir() -> Path:
    return windows_shim_root() / "cli"


def windows_marker_path() -> Path:
    return windows_shim_root() / MARKER_FILENAME


def windows_path_backup_path() -> Path:
    return windows_shim_root() / BACKUP_FILENAME


def windows_temp_dir() -> Path:
    """Profile temp directory (TEMP/TMP or system default); do not assume C:\\Temp."""
    for key in ("TEMP", "TMP"):
        v = os.environ.get(key)
        if v:
            return Path(v)
    return Path(tempfile.gettempdir())


def shim_path_key() -> str:
    """path_key for the canonical CLI shim directory (for orphan PATH detection)."""
    return path_key_for_compare(_canonical_segment_for_path(windows_shim_dir()))


def count_user_path_shim_segments() -> int:
    """How many user Path segments match the xyz-scrcpy CLI shim directory (Windows only)."""
    if not is_windows():
        return 0
    val, _ = read_user_path_value()
    if val is None:
        return 0
    k = shim_path_key()
    if not k:
        return 0
    return sum(1 for s in split_path_segments(val) if path_key_for_compare(s) == k)


def path_key_for_compare(p: str) -> str:
    """Stable key for PATH segment deduplication (case-insensitive, normalized slashes)."""
    if not p or not p.strip():
        return ""
    raw = p.strip()
    try:
        expanded = os.path.expandvars(raw)
        resolved = Path(expanded).expanduser().resolve(strict=False)
        return os.path.normcase(os.path.normpath(str(resolved)))
    except OSError:
        return os.path.normcase(os.path.normpath(expanded.rstrip("/\\")))


def split_path_segments(path_value: str) -> list[str]:
    if not path_value:
        return []
    return [s for s in path_value.split(";") if s != ""]


def join_path_segments(segments: list[str]) -> str:
    return ";".join(segments)


def is_duplicate_segment(new_seg: str, segments: list[str]) -> bool:
    k = path_key_for_compare(new_seg)
    if not k:
        return True
    return any(path_key_for_compare(s) == k for s in segments if s)


def read_user_path_value() -> tuple[str | None, int | None]:
    """Return (path_string, winreg type) for HKCU\\Environment Path, or (None, None) if missing."""
    if not is_windows():
        return None, None
    wr = _get_winreg()
    try:
        with wr.OpenKey(wr.HKEY_CURRENT_USER, r"Environment", 0, wr.KEY_READ) as key:
            try:
                val, typ = wr.QueryValueEx(key, "Path")
            except FileNotFoundError:
                return "", wr.REG_EXPAND_SZ
            if val is None:
                return "", int(typ)
            return str(val), int(typ)
    except OSError:
        return None, None


def write_user_path_value(path_str: str, reg_type: int) -> None:
    if not is_windows():
        return
    wr = _get_winreg()
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, r"Environment", 0, wr.KEY_SET_VALUE) as key:
        wr.SetValueEx(key, "Path", 0, reg_type, path_str)


def broadcast_environment_change() -> None:
    """Notify running apps that environment changed (best-effort, WM_SETTINGCHANGE "Environment")."""
    if not is_windows():
        return
    try:
        import ctypes
        from ctypes import wintypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        timeout_ms = 5000
        result = wintypes.DWORD_PTR()
        env = ctypes.c_wchar_p("Environment")
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            env,
            SMTO_ABORTIFHUNG,
            timeout_ms,
            ctypes.byref(result),
        )
    except Exception as exc:
        _log.warning("WM_SETTINGCHANGE broadcast failed: %s", exc)


def _canonical_segment_for_path(p: Path) -> str:
    try:
        return str(p.resolve(strict=False))
    except OSError:
        return str(p)


def backup_user_path_to_file(backup_file: Path) -> None:
    val, typ = read_user_path_value()
    if val is None:
        return
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    data = {"path": val, "reg_type": typ or 2}
    backup_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def restore_user_path_from_backup(backup_file: Path) -> bool:
    if not backup_file.is_file():
        return False
    try:
        data = json.loads(backup_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    path_val = data.get("path")
    reg_type = int(data.get("reg_type", _get_winreg().REG_EXPAND_SZ))
    if path_val is None:
        return False
    write_user_path_value(str(path_val), reg_type)
    broadcast_environment_change()
    return True


def add_shim_dir_to_user_path(shim_dir: Path, path_log: Path | None = None) -> str:
    """Append canonical shim_dir to HKCU Path if not duplicate. Returns canonical segment written."""
    if not is_windows():
        return ""
    canonical = _canonical_segment_for_path(shim_dir)
    current, typ = read_user_path_value()
    if current is None:
        raise RuntimeError("Cannot read HKCU\\Environment\\Path (permission or policy).")
    if typ is None:
        typ = _get_winreg().REG_EXPAND_SZ
    segments = split_path_segments(current)
    if is_duplicate_segment(canonical, segments):
        _log.info("PATH already contains shim_dir: %s", canonical)
        return canonical
    new_segments = segments + [canonical]
    new_val = join_path_segments(new_segments)
    write_user_path_value(new_val, typ)
    broadcast_environment_change()
    if path_log:
        _append_path_log(path_log, f"ADD {canonical}")
    return canonical


def remove_segment_from_user_path(segment: str, path_log: Path | None = None) -> int:
    """Remove all segments whose path_key matches segment. Returns count removed."""
    if not is_windows():
        return 0
    key = path_key_for_compare(segment)
    if not key:
        return 0
    current, typ = read_user_path_value()
    if current is None:
        return 0
    if typ is None:
        typ = _get_winreg().REG_EXPAND_SZ
    segments = split_path_segments(current)
    kept = [s for s in segments if path_key_for_compare(s) != key]
    removed = len(segments) - len(kept)
    if removed:
        write_user_path_value(join_path_segments(kept), typ)
        broadcast_environment_change()
        if path_log:
            _append_path_log(path_log, f"REMOVE {segment} (n={removed})")
    return removed


def write_cli_shim_cmd(cmd_path: Path, install_dir: Path) -> None:
    """Write UTF-8 without BOM, ASCII-only content, CRLF; quoted paths for spaces."""
    win_inst = str(install_dir.resolve()).replace("/", "\\")
    vpy = str((install_dir / ".venv" / "Scripts" / "python.exe").resolve()).replace("/", "\\")
    lpy = str((install_dir / "bin" / "launch_with_checks.py").resolve()).replace("/", "\\")
    lines = [
        "@echo off",
        f'set "PATH={win_inst}\\vendor;%PATH%"',
        f'"{vpy}" "{lpy}"',
        "",
    ]
    content = "\r\n".join(lines)
    cmd_path.parent.mkdir(parents=True, exist_ok=True)
    cmd_path.write_bytes(content.encode("utf-8"))


def read_marker() -> dict[str, Any] | None:
    mp = windows_marker_path()
    if not mp.is_file():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_marker(data: dict[str, Any]) -> None:
    mp = windows_marker_path()
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def delete_marker() -> None:
    mp = windows_marker_path()
    try:
        mp.unlink()
    except OSError:
        pass


def _append_path_log(path_log: Path, line: str) -> None:
    try:
        path_log.parent.mkdir(parents=True, exist_ok=True)
        if path_log.is_file() and path_log.stat().st_size > PATH_LOG_MAX_BYTES:
            rotated = path_log.with_suffix(path_log.suffix + ".old")
            try:
                shutil.move(str(path_log), str(rotated))
            except OSError:
                path_log.unlink(missing_ok=True)
        with path_log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def rotate_install_log(log_path: Path) -> None:
    if log_path.is_file() and log_path.stat().st_size > PATH_LOG_MAX_BYTES:
        try:
            shutil.move(str(log_path), str(log_path.with_suffix(".log.old")))
        except OSError:
            pass


def install_log_path(install_dir: Path) -> Path:
    return install_dir / "config" / "install.log"


def path_changes_log_path(install_dir: Path) -> Path:
    return install_dir / "config" / "path_changes.log"


def log_install_line(install_dir: Path, msg: str, verbose: bool = False) -> None:
    line = msg
    if verbose:
        print(line)
    try:
        if not install_dir.exists():
            return
        cfg = install_dir / "config"
        cfg.mkdir(parents=True, exist_ok=True)
        log_file = install_log_path(install_dir)
        rotate_install_log(log_file)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def resolve_python_for_checks(min_version: tuple[int, int] = (3, 10)) -> tuple[str | None, str | None]:
    """Return (executable_path, error_message)."""
    candidates: list[list[str]] = [
        ["py", "-3", "-c", "import sys; print(sys.executable)"],
        ["python", "-c", "import sys; print(sys.executable)"],
    ]
    for argv in candidates:
        exe = argv[0]
        if shutil.which(exe) is None:
            continue
        try:
            proc = subprocess.run(
                argv,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if proc.returncode != 0 or not (proc.stdout or "").strip():
                continue
            py_path = (proc.stdout or "").strip().splitlines()[-1].strip()
            if not py_path:
                continue
            ver_proc = subprocess.run(
                [py_path, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
            )
            if ver_proc.returncode != 0:
                continue
            ver_s = (ver_proc.stdout or "").strip()
            m = re.match(r"^(\d+)\.(\d+)", ver_s)
            if not m:
                continue
            major, minor = int(m.group(1)), int(m.group(2))
            if (major, minor) < min_version:
                return None, f"Python {py_path} is {major}.{minor}; need >={min_version[0]}.{min_version[1]}."
            chk = subprocess.run(
                [py_path, "-c", "import pip"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if chk.returncode != 0:
                return (
                    None,
                    "Python appears to be embeddable or minimal (no pip). "
                    "Install full Python from https://www.python.org/downloads/ or Microsoft Store.",
                )
            return py_path, None
        except (subprocess.TimeoutExpired, OSError):
            continue
    return None, "No suitable Python 3.10+ found (try `py -3` or add `python` to PATH)."


def warn_external_tools(install_dir: Path, verbose: bool = False) -> None:
    """Non-blocking hints for adb/scrcpy."""
    vendor = install_dir / "vendor"
    has_vendor_adb = (vendor / "adb.exe").is_file()
    has_vendor_scrcpy = (vendor / "scrcpy.exe").is_file() or (vendor / "scrcpy").is_file()
    if shutil.which("adb") is None and not has_vendor_adb:
        msg = "[WARN] adb not found in PATH and not under vendor/. Install Android SDK platform-tools or run setup_vendor."
        print(msg)
        log_install_line(install_dir, msg, verbose=verbose)
    if shutil.which("scrcpy") is None and not has_vendor_scrcpy:
        msg = "[WARN] scrcpy not found in PATH and not under vendor/. Install scrcpy or run setup_vendor."
        print(msg)
        log_install_line(install_dir, msg, verbose=verbose)
    for tool, argv in (("adb", ["adb", "version"]), ("scrcpy", ["scrcpy", "--version"])):
        exe = shutil.which(tool)
        if not exe:
            continue
        try:
            proc = subprocess.run([exe] + argv[1:], text=True, capture_output=True, check=False, timeout=15)
            if proc.returncode == 0 and verbose:
                first = (proc.stdout or proc.stderr or "").splitlines()[:1]
                if first:
                    log_install_line(install_dir, f"[INFO] {tool}: {first[0]}", verbose=verbose)
        except (subprocess.TimeoutExpired, OSError):
            pass


def windows_install_cli_shim(
    install_dir: Path,
    alias: str,
    *,
    path_log: Path | None = None,
    backup_path: Path | None = None,
) -> None:
    """Add shim dir to user PATH, write <alias>.cmd, write marker.

    Call only after install_dir contains .venv (shim invokes that python).
    Backup of HKCU Path is written immediately before the first registry mutation.
    """
    if not is_windows():
        return
    shim_dir = windows_shim_dir()
    shim_dir.mkdir(parents=True, exist_ok=True)
    if backup_path is None:
        backup_path = windows_path_backup_path()
    backup_user_path_to_file(backup_path)
    seg = add_shim_dir_to_user_path(shim_dir, path_log=path_log)
    cmd_path = shim_dir / f"{alias}.cmd"
    write_cli_shim_cmd(cmd_path, install_dir)
    write_marker(
        {
            "shim_dir": seg,
            "alias": alias,
            "install_type": "installer",
            "path_segment": seg,
        }
    )


def windows_uninstall_cli_shim(
    install_dir: Path | None = None,
    *,
    path_log: Path | None = None,
    remove_shim_files: bool = True,
) -> None:
    """Remove PATH segment, marker, shim .cmd; best-effort if partial state."""
    if not is_windows():
        return
    marker = read_marker()
    if marker:
        ps = marker.get("path_segment") or marker.get("shim_dir")
        if ps:
            remove_segment_from_user_path(str(ps), path_log=path_log)
    # Removes all segments whose key matches the canonical shim dir (covers orphans and duplicates).
    remove_segment_from_user_path(_canonical_segment_for_path(windows_shim_dir()), path_log=path_log)
    if remove_shim_files:
        sd = windows_shim_root() / "cli"
        if sd.is_dir():
            try:
                shutil.rmtree(sd)
            except OSError:
                for child in sd.glob("*.cmd"):
                    try:
                        child.unlink()
                    except OSError:
                        pass
    delete_marker()
    bp = windows_path_backup_path()
    try:
        bp.unlink()
    except OSError:
        pass


def run_diagnose(install_dir: Path | None, *, clean_user_path: bool = False) -> int:
    """Print diagnostics for Windows PATH/shim/Python."""
    if not is_windows():
        print("diagnose: Windows only.")
        return 0
    val, typ = read_user_path_value()
    print("HKCU\\Environment\\Path:")
    print(f"  type: {typ}")
    print(f"  value ({len(val or '')} chars): {(val or '')[:500]}{'...' if val and len(val) > 500 else ''}")
    print("segments (keys):", [path_key_for_compare(s) for s in split_path_segments(val or "")][:40])
    print("shim_root:", windows_shim_root())
    print("shim_dir:", windows_shim_dir(), "exists:", windows_shim_dir().is_dir())
    print("marker:", read_marker())
    print("user Path segments matching CLI shim key:", count_user_path_shim_segments())
    print("windows_temp_dir():", windows_temp_dir())
    py, err = resolve_python_for_checks()
    print("python:", py, "error:", err)
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_SCHED_NAME],
            text=True,
            capture_output=True,
            check=False,
        )
        print("schtasks query:", proc.returncode)
        if proc.stdout:
            print(proc.stdout[:800])
    except OSError as exc:
        print("schtasks:", exc)
    if install_dir and install_dir.exists():
        print("install_dir:", install_dir)
    if clean_user_path:
        pl = path_changes_log_path(install_dir) if install_dir and install_dir.exists() else None
        n = remove_segment_from_user_path(_canonical_segment_for_path(windows_shim_dir()), path_log=pl)
        print(f"clean_user_path: removed {n} matching HKCU Path segment(s).")
    return 0
