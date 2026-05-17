#!/usr/bin/env python3
try:
    import fcntl
except ImportError:
    fcntl = None
import os
import re
import select
import shutil
import signal
import subprocess
import sys
try:
    import termios
except ImportError:
    termios = None
import time
try:
    import tty
except ImportError:
    tty = None
from pathlib import Path

from config_loader import load_config, save_config

BRAND_NAME = "RAINBOWTECHNOLOGY"
LOGO = [
    r"██╗  ██╗ ██╗   ██╗ ███████╗",
    r"╚██╗██╔╝ ╚██╗ ██╔╝ ╚══███╔╝",
    r" ╚███╔╝   ╚████╔╝    ███╔╝ ",
    r" ██╔██╗    ╚██╔╝    ███╔╝  ",
    r"██╔╝ ██╗    ██║    ███████╗",
    r"╚═╝  ╚═╝    ╚═╝    ╚══════╝",
]

RED, GREEN, MAGENTA, ORANGE, WHITE, RESET = (
    "\033[91m",
    "\033[38;5;118m",
    "\033[35m",
    "\033[38;5;208m",
    "\033[37m",
    "\033[0m",
)
NEON_PINK = "\033[38;5;213m"

ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import adb_resolve  # noqa: E402

try:
    import vendor_bootstrap as vb  # noqa: E402
except ImportError:
    vb = None  # type: ignore[assignment]

import tempfile
LOCK_PATH = os.path.join(tempfile.gettempdir(), "xyz_menu.lock")
INSTALLER_PATH = ROOT_DIR / "install_xyz.py"
SCRCPY_VENDOR_BIN = ROOT_DIR / "vendor" / ("scrcpy.exe" if os.name == "nt" else "scrcpy")
LIME = "\033[38;5;154m"
MIC_BUS_NAME = "xyz-mic-input"
BANNER_COLORS = {"ERROR": RED, "WARN": ORANGE, "OK": GREEN}
INSTALLABLE_EXTENSIONS = {".apk"}
ESCAPE_POLL_TIMEOUT = 0.05
ESCAPE_SEQUENCE_DEADLINE = 0.25
MAIN_MENU_DEVICE_POLL_SEC = 5
_ARROW_FINAL_BYTES = frozenset("ABCD")


def _normalize_key(seq: str) -> str:
    """Map SS3 arrow sequences (ESC O x) to CSI form (ESC [ x)."""
    if len(seq) >= 3 and seq[0] == "\x1b" and seq[1] == "O" and seq[2] in _ARROW_FINAL_BYTES:
        return "\x1b[" + seq[2]
    return seq


def _escape_sequence_complete(seq: str) -> bool:
    if len(seq) < 2 or seq[0] != "\x1b":
        return True
    if seq[1] == "O":
        return len(seq) >= 3
    if seq[1] == "[":
        if len(seq) >= 3 and seq[-1] in _ARROW_FINAL_BYTES:
            return True
        if len(seq) >= 4 and seq[-1].isalpha():
            return True
    return False


def _stdin_bytes_waiting(fd: int) -> int:
    if fcntl is None:
        return 0
    import array

    buf = array.array("i", [0])
    try:
        fcntl.ioctl(fd, termios.FIONREAD, buf)  # type: ignore[attr-defined]
        return int(buf[0])
    except (OSError, AttributeError, ValueError):
        return 0


def _read_escape_sequence(first: str, fd: int) -> str:
    """Read bytes after ESC until a full sequence or deadline (avoid bare ESC on arrows)."""
    seq = first
    waiting = _stdin_bytes_waiting(fd)
    if waiting > 0:
        try:
            data = os.read(fd, min(waiting, 64))
            if data:
                seq += data.decode("utf-8", errors="replace")
        except OSError:
            pass
    if len(seq) > 1 and _escape_sequence_complete(seq):
        return _normalize_key(seq)
    deadline = time.monotonic() + ESCAPE_SEQUENCE_DEADLINE
    while time.monotonic() < deadline:
        if len(seq) > 1 and _escape_sequence_complete(seq):
            return _normalize_key(seq)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select([fd], [], [], min(ESCAPE_POLL_TIMEOUT, remaining))
        if not ready:
            if len(seq) == 1:
                continue
            break
        try:
            data = os.read(fd, 1)
        except OSError:
            break
        if data:
            seq += data.decode("utf-8", errors="replace")
    if len(seq) == 1:
        return "\x1b"
    return _normalize_key(seq)


def _adb_exe() -> str:
    return adb_resolve.resolve_adb_executable(ROOT_DIR)[0]


def adb_is_available() -> bool:
    return adb_resolve.resolve_adb_executable(ROOT_DIR)[1] != "not_found"


def scrcpy_is_available() -> bool:
    if vb is not None:
        return vb.resolve_scrcpy_executable(ROOT_DIR)[1] != "not_found"
    if SCRCPY_VENDOR_BIN.is_file() and os.access(SCRCPY_VENDOR_BIN, os.X_OK):
        return True
    return shutil.which("scrcpy") is not None


def _read_key_raw_fd(fd: int) -> str:
    """Read one key (or escape sequence) from fd already in raw mode."""
    data = os.read(fd, 1)
    if not data:
        return ""
    ch = data.decode("utf-8", errors="replace")
    if ch != "\x1b":
        return ch
    return _read_escape_sequence(ch, fd)


def get_key():
    if os.name != "nt":
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return _read_key_raw_fd(fd)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    else:
        import msvcrt
        ch = msvcrt.getch()
        if ch == b'\xe0':
            ch2 = msvcrt.getch()
            if ch2 == b'H': return "\x1b[A"
            if ch2 == b'P': return "\x1b[B"
            if ch2 == b'M': return "\x1b[C"
            if ch2 == b'K': return "\x1b[D"
        if ch == b'\r': return "\r"
        try:
            return ch.decode("utf-8")
        except (UnicodeDecodeError, LookupError):
            return ch.decode("latin-1")


def wait_menu_key(timeout_sec: float = MAIN_MENU_DEVICE_POLL_SEC) -> str | None:
    """Wait for a key or return None on timeout (main menu device polling)."""
    if os.name != "nt":
        if not sys.stdin.isatty():
            return get_key()
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ready, _, _ = select.select([fd], [], [], max(0.0, timeout_sec))
            if not ready:
                return None
            return _read_key_raw_fd(fd)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    import msvcrt

    deadline = time.monotonic() + max(0.0, timeout_sec)
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            return get_key()
        time.sleep(0.05)
    return None


def visible_len(text):
    return len(ANSI_PATTERN.sub("", text))


def center_line(text, width):
    pad = max(0, (width - visible_len(text)) // 2)
    return (" " * pad) + text


def trunc_text(text, max_len):
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return "." * max_len
    return text[: max_len - 3] + "..."


def terminal_width():
    # Extra margin: integrated terminals may reserve a column; keeps borders inside visible width.
    return max(40, min(120, shutil.get_terminal_size(fallback=(80, 24)).columns - 3))


def terminal_rows():
    try:
        return max(20, shutil.get_terminal_size(fallback=(80, 24)).lines)
    except OSError:
        return 24


def visible_page_size(reserved_lines: int = 12) -> int:
    """Rows available for scrollable content after header, hints, and brand footer."""
    return max(8, terminal_rows() - reserved_lines)


def render_tui_header(title: str, width: int, banner=None) -> list[str]:
    """Shared top frame for paginated lists and SETTINGS (matches APK package menu)."""
    border = "=" * width
    lines: list[str] = []
    if banner:
        level = str(banner.get("level", "WARN")).upper()
        color = BANNER_COLORS.get(level, ORANGE)
        msg = trunc_text(f"[{level}] {banner.get('message', '')}", width - 2)
        lines.append(center_line(f"{color}{msg}{RESET}", width))
        lines.append("")
    lines.extend(
        [
            center_line("[SPACE] [ENTER] [ESC]".center(width), width),
            center_line(f"{RED}{border}{RESET}", width),
            center_line(f"{MAGENTA}{title}{RESET}", width),
            "",
        ]
    )
    return lines


def paginated_window(total: int, selected_idx: int, page_size: int) -> tuple[int, int]:
    """Return (start, end) slice indices centered on selected_idx."""
    if total <= 0:
        return 0, 0
    window_start = max(0, min(selected_idx - (page_size // 2), max(0, total - page_size)))
    window_end = min(total, window_start + page_size)
    return window_start, window_end


def normalize_alias(alias):
    clean = re.sub(r"[^a-zA-Z0-9._-]", "-", str(alias).strip())
    clean = re.sub(r"-{2,}", "-", clean).strip("-")
    return clean or "xyz-scrcpy"


def prompt_text_input(prompt, default):
    sys.stdout.write("\n")
    sys.stdout.flush()
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def run_command(cmd):
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    except OSError as exc:
        return False, "", str(exc), 1
    return proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip(), proc.returncode


def make_banner(level, message, ttl=3):
    return {"level": level, "message": str(message), "ttl": max(1, int(ttl))}


def tick_banner(banner):
    if not banner:
        return None
    updated = dict(banner)
    updated["ttl"] = int(updated.get("ttl", 1)) - 1
    if updated["ttl"] <= 0:
        return None
    return updated


def is_installable_file(path):
    ext = Path(path).suffix.lower()
    return ext in INSTALLABLE_EXTENSIONS


def parse_pm_path_output(output):
    paths = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        remote_path = line[len("package:") :].strip()
        if remote_path:
            paths.append(remote_path)
    return paths


def render_brand_footer(width):
    border = "=" * width
    return [
        "",
        center_line(f"{GREEN}{border}{RESET}", width),
        center_line(f"{NEON_PINK}[{BRAND_NAME}]".center(width) + f"{RESET}", width),
        center_line(f"{GREEN}{border}{RESET}", width),
    ]


def show_paginated_selection(
    title,
    options,
    banner=None,
    footer_hint="[UP/DOWN] move [ENTER] select [ESC] back",
    page_size=10,
    highlight_selection_red=False,
):
    idx = 0
    local_banner = banner
    while True:
        width = terminal_width()
        total = len(options)
        window_start, window_end = paginated_window(total, idx, page_size)
        visible = options[window_start:window_end]

        lines = render_tui_header(title, width, banner=local_banner)

        if window_start > 0:
            lines.append(center_line("...", width))

        for offset, opt in enumerate(visible):
            global_idx = window_start + offset
            text = trunc_text(opt, width - 4)
            if global_idx == idx:
                if highlight_selection_red:
                    text = f"{RED}{text}{RESET}"
                lines.append(center_line(f"> {text}", width))
            else:
                lines.append(center_line(f"  {text}", width))

        if window_end < total:
            lines.append(center_line("...", width))

        lines.append("")
        lines.append(center_line(footer_hint, width))
        lines.extend(render_brand_footer(width))

        os.system("cls" if os.name == "nt" else "clear")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        key = get_key()
        local_banner = tick_banner(local_banner)
        if key == "\x1b[A":
            idx = (idx - 1) % total
        elif key == "\x1b[B":
            idx = (idx + 1) % total
        elif key == "\r":
            return idx
        elif key == "\x1b":
            return None


def show_simple_selection(title, options, banner=None, footer_hint="[UP/DOWN] move [ENTER] select [ESC] back"):
    return show_paginated_selection(
        title,
        options,
        banner=banner,
        footer_hint=footer_hint,
        page_size=10,
        highlight_selection_red=False,
    )


def pick_path_with_hybrid_selector(title, mode_title, ask_directory=False, banner=None):
    mode_options = ["GUI picker", "Manual path", "Back"]
    mode_idx = show_simple_selection(mode_title, mode_options, banner=banner)
    if mode_idx is None or mode_options[mode_idx] == "Back":
        return None, make_banner("WARN", "Action cancelled.")
    mode = mode_options[mode_idx]

    if mode == "Manual path":
        os.system("cls" if os.name == "nt" else "clear")
        try:
            entered = prompt_text_input(title, "")
        except EOFError:
            entered = ""
        path = Path(entered).expanduser() if entered else None
    else:
        path = pick_path_with_gui(ask_directory=ask_directory)
        if path is None:
            return None, make_banner("WARN", "GUI picker unavailable or cancelled.")

    if path is None:
        return None, make_banner("WARN", "No path selected.")
    return path, None


def pick_path_with_gui(ask_directory=False):
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--title=Select path"]
        if ask_directory:
            cmd.append("--directory")
        ok, out, _err, _code = run_command(cmd)
        if ok and out:
            return Path(out.strip()).expanduser()
        return None
    if shutil.which("kdialog"):
        if ask_directory:
            cmd = ["kdialog", "--getexistingdirectory", str(Path.home())]
        else:
            cmd = ["kdialog", "--getopenfilename", str(Path.home()), "*.apk"]
        ok, out, _err, _code = run_command(cmd)
        if ok and out:
            return Path(out.strip()).expanduser()
        return None
    return None


def adb_list_packages(serial):
    if not adb_is_available():
        return None, "adb not available. Re-run install or place platform-tools in vendor/."
    ok, out, err, _ = run_command([_adb_exe(), "-s", serial, "shell", "pm", "list", "packages"])
    if not ok:
        return None, err or "Unable to list packages."
    packages = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            pkg = line[len("package:") :].strip()
            if pkg:
                packages.append(pkg)
    return sorted(packages), None


def adb_install_apk(serial, apk_path):
    if not adb_is_available():
        return False, "", "adb not available.", 1
    return run_command([_adb_exe(), "-s", serial, "install", "-r", str(apk_path)])


def adb_uninstall_package(serial, package_name):
    if not adb_is_available():
        return False, "", "adb not available.", 1
    return run_command([_adb_exe(), "-s", serial, "uninstall", package_name])


def adb_disconnect(serial):
    if not adb_is_available():
        return False, "", "adb not available.", 1
    ok, out, err, code = run_command([_adb_exe(), "-s", serial, "disconnect"])
    if ok:
        return True, out, err, code
    return run_command([_adb_exe(), "disconnect", serial])


def adb_export_apk_to_dir(serial, package_name, destination_dir):
    if not adb_is_available():
        return False, [], "adb not available."
    ok, out, err, _ = run_command([_adb_exe(), "-s", serial, "shell", "pm", "path", package_name])
    if not ok:
        return False, [], err or "Unable to get APK paths."
    remote_paths = parse_pm_path_output(out)
    if not remote_paths:
        return False, [], "No APK paths found for package."

    destination_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for index, remote in enumerate(remote_paths, start=1):
        suffix = f"-{index}" if len(remote_paths) > 1 else ""
        target = destination_dir / f"{package_name}{suffix}.apk"
        pull_ok, _out, pull_err, _ = run_command([_adb_exe(), "-s", serial, "pull", remote, str(target)])
        if not pull_ok:
            return False, exported, pull_err or f"Failed pulling {remote}"
        exported.append(str(target))
    return True, exported, ""


def adb_try_backup(serial, package_name, destination_dir):
    if not adb_is_available():
        return False, "", "adb not available.", 1
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_file = destination_dir / f"{package_name}.ab"
    return run_command(
        [
            _adb_exe(),
            "-s",
            serial,
            "backup",
            "-apk",
            "-obb",
            "-f",
            str(backup_file),
            package_name,
        ]
    )


def _launcher_managed_by_install(launcher_file: Path) -> bool:
    if not launcher_file.is_file():
        return False
    markers = (
        str(ROOT_DIR / "bin" / "launch_with_checks.sh"),
        str(ROOT_DIR / "bin" / "launch_with_checks.py"),
    )
    try:
        content = launcher_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(m in content for m in markers)


def stale_managed_launcher_names(current_alias: str) -> list[str]:
    """Other managed launcher basenames in ~/.local/bin (linux) still on PATH."""
    if os.name == "nt":
        return []
    launcher_dir = Path.home() / ".local" / "bin"
    if not launcher_dir.is_dir():
        return []
    current = normalize_alias(current_alias)
    stale = []
    for entry in launcher_dir.iterdir():
        if not entry.is_file() or entry.name == current:
            continue
        if _launcher_managed_by_install(entry):
            stale.append(entry.name)
    return stale


def sync_alias_launcher(alias) -> tuple[bool, str]:
    if not INSTALLER_PATH.exists():
        return False, "Installer not found."
    try:
        proc = subprocess.run(
            [
                "python3",
                str(INSTALLER_PATH),
                "--action",
                "sync-alias",
                "--alias",
                alias,
                "--yes",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return False, detail or f"sync-alias failed (exit {proc.returncode})"
        return True, ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def has_audio_pending(cfg):
    return any(
        [
            str(cfg.get("audio_target", "host")) != str(cfg.get("applied_audio_target", "host")),
            bool(cfg.get("active_recall", False)) != bool(cfg.get("applied_active_recall", False)),
            bool(cfg.get("microphone_bus", False)) != bool(cfg.get("applied_microphone_bus", False)),
        ]
    )


def normalize_audio_preferences(cfg):
    normalized = dict(cfg)
    if bool(normalized.get("active_recall", False)) and str(normalized.get("audio_target", "host")).lower() == "device":
        # Active Recall uses Android microphone capture, which requires host-side audio enabled.
        normalized["audio_target"] = "host"
    return normalized


def adb_device_lines():
    """Return parsed ``adb devices`` rows as (serial, state) excluding the header."""
    if not adb_is_available():
        return []
    try:
        adb = _adb_exe()
        raw = subprocess.check_output([adb, "devices"], text=True, timeout=30).splitlines()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return []
    rows = []
    for line in raw:
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def adb_devices_status_message(cfg=None):
    """Human hint when adb works but no device is ready for the menu."""
    if not adb_is_available():
        return (
            "adb not found. Re-run install or place platform-tools in vendor/. "
            "Debian: sudo apt install adb scrcpy"
        )
    rows = adb_device_lines()
    last_serial = (cfg or {}).get("last_device_serial")
    if not rows:
        if last_serial:
            return (
                f"Phone not listed by adb; showing last device ({last_serial}). "
                "Enable USB debugging, use a data cable, authorize RSA, then replug USB."
            )
        return (
            "adb OK but no phone detected. Enable USB debugging, use a data cable, "
            "authorize the RSA prompt on the phone, then replug USB."
        )
    ready = [serial for serial, state in rows if state == "device"]
    if ready:
        return ""
    hints = []
    for serial, state in rows:
        if state == "unauthorized":
            hints.append(f"{serial}: tap Allow on the phone's USB debugging prompt")
        elif state == "offline":
            hints.append(f"{serial}: offline — replug cable or run adb kill-server")
        else:
            hints.append(f"{serial}: {state}")
    return "adb: " + "; ".join(hints)


def _device_label_for_serial(adb: str, serial: str, state_tag: str = "") -> str:
    label = serial
    try:
        model = subprocess.check_output(
            [adb, "-s", serial, "shell", "getprop", "ro.product.model"],
            text=True,
            timeout=15,
        ).strip()
        if model:
            label = f"{model} ({serial})"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    if state_tag:
        return f"{label} [{state_tag}]"
    return label


def adb_serial_reachable(adb: str, serial: str) -> bool:
    try:
        proc = subprocess.run(
            [adb, "-s", serial, "get-state"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        state = (proc.stdout or proc.stderr or "").strip().lower()
        return proc.returncode == 0 and state in ("device", "recovery", "sideload", "rescue")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def list_devices():
    if not adb_is_available():
        return []
    adb = _adb_exe()
    devices = []
    for serial, state in adb_device_lines():
        if state != "device":
            continue
        devices.append({"serial": serial, "label": _device_label_for_serial(adb, serial)})
    return devices


def list_devices_for_menu(cfg):
    """Devices for main menu: ready, offline/unauthorized, and last known serial when reachable."""
    if not adb_is_available():
        return []
    adb = _adb_exe()
    by_serial: dict[str, dict] = {}
    for serial, state in adb_device_lines():
        if state == "device":
            by_serial[serial] = {"serial": serial, "label": _device_label_for_serial(adb, serial)}
        elif state in ("offline", "unauthorized"):
            by_serial[serial] = {
                "serial": serial,
                "label": _device_label_for_serial(adb, serial, state),
            }

    last_serial = (cfg or {}).get("last_device_serial")
    if last_serial and last_serial not in by_serial:
        if adb_serial_reachable(adb, last_serial):
            tag = "reconnecting"
        else:
            tag = "last used"
        by_serial[last_serial] = {
            "serial": last_serial,
            "label": _device_label_for_serial(adb, last_serial, tag),
        }

    return list(by_serial.values())


def main_menu_index_for_serial(devices, serial: str | None) -> int | None:
    """Index of device in main-menu opts, or None if not connected."""
    if not serial:
        return None
    for i, device in enumerate(devices):
        if device["serial"] == serial:
            return i
    return None


def resolve_scrcpy_binary():
    if vb is not None:
        exe, src = vb.resolve_scrcpy_executable(ROOT_DIR)
        if src != "not_found":
            return exe
    if SCRCPY_VENDOR_BIN.exists() and os.access(SCRCPY_VENDOR_BIN, os.X_OK):
        return str(SCRCPY_VENDOR_BIN)
    return "scrcpy"


def scrcpy_supports_microphone():
    scrcpy_bin = resolve_scrcpy_binary()
    try:
        output = subprocess.check_output([scrcpy_bin, "--help"], text=True, stderr=subprocess.STDOUT)
    except (subprocess.SubprocessError, OSError):
        return False
    lowered = output.lower()
    return "--audio-source" in lowered and "mic" in lowered


def _pactl_short_entries(kind):
    output = subprocess.check_output(["pactl", "list", "short", kind], text=True)
    entries = []
    for line in output.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        entries.append(parts)
    return entries


def audio_input_exists(name):
    try:
        if sys.platform == "linux":
            if shutil.which("pactl") is None:
                return False
            source_entries = _pactl_short_entries("sources")
            source_names = [parts[1].strip() for parts in source_entries if len(parts) > 1]
            return name in source_names

        if sys.platform == "darwin":
            output = subprocess.check_output(["system_profiler", "SPAudioDataType"], text=True, stderr=subprocess.STDOUT)
            lowered = output.lower()
            return name.lower() in lowered

        if sys.platform.startswith("win"):
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Name",
                ],
                text=True,
                stderr=subprocess.STDOUT,
            )
            return name.lower() in output.lower()
    except (subprocess.SubprocessError, OSError):
        return False
    return False


def ensure_microphone_bus(enabled):
    if not enabled:
        return False
    if sys.platform.startswith("win"):
        if audio_input_exists(MIC_BUS_NAME):
            return True
        print("[WARN] Windows microphone bus requires a virtual audio cable (for example VB-CABLE).")
        print(f"[WARN] Create or rename a virtual input to '{MIC_BUS_NAME}', then select it as your recording input.")
        return False
    if sys.platform == "darwin":
        if audio_input_exists(MIC_BUS_NAME):
            return True
        print("[WARN] macOS microphone bus requires a virtual loopback driver (for example BlackHole).")
        print(f"[WARN] Create or rename an input device as '{MIC_BUS_NAME}', then route system audio to it.")
        return False
    if sys.platform != "linux":
        print("[WARN] Microphone bus is not supported on this OS yet.")
        return False
    if shutil.which("pactl") is None:
        print("[WARN] microphone_bus requires 'pactl' (PulseAudio/PipeWire).")
        return False
    try:
        modules = _pactl_short_entries("modules")
        primary_remap_module_id = ""
        duplicate_module_ids = []

        # Cleanup legacy implementation that created an extra output sink,
        # and collapse duplicate remap modules for xyz-mic-input.
        for parts in modules:
            mod_id = parts[0].strip()
            module_name = parts[1].strip() if len(parts) > 1 else ""
            args = parts[-1]
            if f"sink_name={MIC_BUS_NAME}-sink" in args:
                subprocess.run(
                    ["pactl", "unload-module", mod_id],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                continue
            if module_name == "module-remap-source" and f"source_name={MIC_BUS_NAME}" in args:
                if not primary_remap_module_id:
                    primary_remap_module_id = mod_id
                else:
                    duplicate_module_ids.append(mod_id)

        for mod_id in duplicate_module_ids:
            subprocess.run(
                ["pactl", "unload-module", mod_id],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if audio_input_exists(MIC_BUS_NAME):
            return True

        # If a stale remap module exists but source is gone, unload and rebuild cleanly.
        if primary_remap_module_id:
            subprocess.run(
                ["pactl", "unload-module", primary_remap_module_id],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        default_sink = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
        if not default_sink:
            print("[WARN] Could not detect default sink for microphone bus.")
            return False
        created = subprocess.run(
            [
                "pactl",
                "load-module",
                "module-remap-source",
                f"master={default_sink}.monitor",
                f"source_name={MIC_BUS_NAME}",
                f"source_properties=device.description={MIC_BUS_NAME}",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if created.returncode != 0:
            print("[WARN] Unable to create microphone bus module.")
            return False

        return audio_input_exists(MIC_BUS_NAME)
    except (subprocess.SubprocessError, OSError):
        print("[WARN] Unable to initialize microphone bus.")
        return False


def kill_scrcpy_for_serial(serial: str) -> None:
    """Stop scrcpy instances bound to ``serial`` (psutil when available, else pkill on Unix)."""
    try:
        import psutil
    except ImportError:
        if os.name != "nt":
            subprocess.run(
                ["pkill", "-f", f"scrcpy.*-s[[:space:]]*{serial}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return
    pat = re.compile(rf"(scrcpy|scrcpy\.exe).*-s\s+{re.escape(serial)}\b", re.I)
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or ())
        except (psutil.Error, TypeError):
            continue
        if pat.search(cmd):
            try:
                proc.terminate()
            except psutil.Error:
                pass


def scrcpy_menu_log_path() -> Path:
    return ROOT_DIR / "config" / "scrcpy-menu.log"


def adb_serial_in_device_state(serial: str) -> bool:
    for listed_serial, state in adb_device_lines():
        if listed_serial == serial and state == "device":
            return True
    return False


def adb_wait_for_device(serial: str, timeout_sec: float = 5.0) -> bool:
    if adb_serial_in_device_state(serial):
        return True
    if not adb_is_available():
        return False
    try:
        proc = subprocess.run(
            [_adb_exe(), "-s", serial, "wait-for-device"],
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_sec),
            check=False,
        )
        return proc.returncode == 0 and adb_serial_in_device_state(serial)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _scrcpy_child_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "SDL_VIDEODRIVER"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _read_scrcpy_log_tail(log_path: Path, max_chars: int = 240) -> str:
    if not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def launch_scrcpy_result(serial, cfg) -> tuple[bool, str]:
    if not scrcpy_is_available():
        return False, "scrcpy not found. Re-run install or place scrcpy in vendor/."
    if not adb_is_available():
        return False, "adb not available."
    if not adb_wait_for_device(serial, timeout_sec=5.0):
        return (
            False,
            f"Device {serial} not ready (check: adb devices). "
            "Enable USB debugging and authorize the phone.",
        )
    cfg = normalize_audio_preferences(cfg)
    audio_target = str(cfg.get("audio_target", "host")).lower()
    active_recall = bool(cfg.get("active_recall", False))
    microphone_bus = bool(cfg.get("microphone_bus", False))
    scrcpy_bin = resolve_scrcpy_binary()
    cmd = [scrcpy_bin, "-s", serial, "--render-driver=software"]
    if audio_target == "device":
        cmd.append("--no-audio")
    if active_recall:
        if scrcpy_supports_microphone():
            cmd.append("--audio-source=mic")
        else:
            print("[WARN] Microphone is not supported by current scrcpy version.")
    ensure_microphone_bus(microphone_bus)
    log_path = scrcpy_menu_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n--- launch {serial} ---\n")
            log_file.flush()
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=_scrcpy_child_env(),
                cwd=str(ROOT_DIR),
            )
    except OSError as exc:
        return False, str(exc)
    time.sleep(0.4)
    if proc.poll() is not None:
        tail = _read_scrcpy_log_tail(log_path)
        hint = tail or "scrcpy exited immediately."
        return False, f"{hint} See config/scrcpy-menu.log"
    return True, ""


def launch_scrcpy(serial, cfg) -> bool:
    ok, _msg = launch_scrcpy_result(serial, cfg)
    return ok


def render_menu(opts, idx, width, banner=None):
    border = "=" * width
    out = []
    if banner:
        level = str(banner.get("level", "WARN")).upper()
        color = BANNER_COLORS.get(level, ORANGE)
        msg = trunc_text(f"[{level}] {banner.get('message', '')}", width - 2)
        out.append(center_line(f"{color}{msg}{RESET}", width))
        out.append("")
    out.extend(
        [
            center_line("[SPACE] [ENTER] [ESC]".center(width), width),
            center_line(f"{RED}{border}{RESET}", width),
            "",
        ]
    )
    for line in LOGO:
        out.append(center_line(f"{GREEN}{line.center(width)}{RESET}", width))
    out.append("")
    for i, opt in enumerate(opts):
        label = trunc_text(opt, width - 4)
        if i == idx:
            line = f"> {ORANGE}{label}{RESET} <"
        else:
            line = label
        out.append(center_line(line, width))
    out.extend(render_brand_footer(width))
    return out


def confirm_action(message, default_no=True):
    os.system("cls" if os.name == "nt" else "clear")
    suffix = "[y/N]" if default_no else "[Y/n]"
    try:
        response = input(f"{message} {suffix}: ").strip().lower()
    except EOFError:
        return not default_no
    if not response:
        return not default_no
    return response in {"y", "yes"}


def select_package_from_device(serial, banner=None, for_uninstall=False):
    packages, err = adb_list_packages(serial)
    if err:
        return None, make_banner("ERROR", f"ADB error: {err}")
    if not packages:
        return None, make_banner("WARN", "No packages found on device.")

    idx = show_paginated_selection(
        f"APPS ON DEVICE ({serial})",
        packages,
        banner=banner,
        footer_hint="[UP/DOWN] package [ENTER] select [ESC] back",
        page_size=10,
        highlight_selection_red=for_uninstall,
    )
    if idx is None:
        return None, make_banner("WARN", "Selection cancelled.")
    return packages[idx], None


def apps_submenu(serial, banner=None):
    options = ["Install APK", "Download to PC", "Uninstall from device", "Back"]
    idx = 0
    local_banner = banner
    while True:
        width = terminal_width()
        lines = render_menu([f"{opt} ({serial})" if opt != "Back" else opt for opt in options], idx, width, banner=local_banner)
        os.system("cls" if os.name == "nt" else "clear")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        key = get_key()
        local_banner = tick_banner(local_banner)
        if key == "\x1b[A":
            idx = (idx - 1) % len(options)
            continue
        if key == "\x1b[B":
            idx = (idx + 1) % len(options)
            continue
        if key == "\x1b":
            return make_banner("WARN", "Back to device menu.")
        if key != "\r":
            continue

        selected = options[idx]
        if selected == "Back":
            return make_banner("WARN", "Back to device menu.")

        if selected == "Install APK":
            apk_path, picker_banner = pick_path_with_hybrid_selector(
                "APK file path",
                "INSTALL APK - PICKER MODE",
                ask_directory=False,
                banner=local_banner,
            )
            if picker_banner:
                local_banner = picker_banner
                continue
            if not apk_path or not apk_path.exists():
                local_banner = make_banner("ERROR", "Invalid path: file not found.")
                continue
            if not is_installable_file(apk_path):
                local_banner = make_banner("ERROR", "Only .apk files are supported.")
                continue
            ok, out, err, _ = adb_install_apk(serial, apk_path)
            if ok:
                local_banner = make_banner("OK", f"Installed APK: {apk_path.name}")
            else:
                local_banner = make_banner("ERROR", f"Install failed: {err or out or 'unknown error'}")
            continue

        if selected == "Uninstall from device":
            package_name, pkg_banner = select_package_from_device(serial, banner=local_banner, for_uninstall=True)
            if pkg_banner:
                local_banner = pkg_banner
                continue
            if not confirm_action(f"Uninstall '{package_name}' from device?", default_no=True):
                local_banner = make_banner("WARN", "Uninstall cancelled.")
                continue
            ok, out, err, _ = adb_uninstall_package(serial, package_name)
            if ok:
                local_banner = make_banner("OK", f"Uninstalled: {package_name}")
            else:
                local_banner = make_banner("ERROR", f"Uninstall failed: {err or out or 'unknown error'}")
            continue

        if selected == "Download to PC":
            package_name, pkg_banner = select_package_from_device(serial, banner=local_banner, for_uninstall=False)
            if pkg_banner:
                local_banner = pkg_banner
                continue
            mode_options = ["Export APK(s)", "Backup app+data (try)", "Auto (best available)", "Back"]
            mode_idx = show_simple_selection("DOWNLOAD MODE", mode_options, banner=local_banner)
            if mode_idx is None or mode_options[mode_idx] == "Back":
                local_banner = make_banner("WARN", "Download cancelled.")
                continue

            destination_dir, dir_banner = pick_path_with_hybrid_selector(
                "Destination directory",
                "DOWNLOAD - DESTINATION PICKER",
                ask_directory=True,
                banner=local_banner,
            )
            if dir_banner:
                local_banner = dir_banner
                continue
            if destination_dir is None:
                local_banner = make_banner("ERROR", "No destination selected.")
                continue

            selected_mode = mode_options[mode_idx]
            if selected_mode == "Export APK(s)":
                ok, exported, err = adb_export_apk_to_dir(serial, package_name, destination_dir)
                if ok:
                    local_banner = make_banner("OK", f"Exported {len(exported)} APK file(s).")
                else:
                    local_banner = make_banner("ERROR", f"Export failed: {err}")
                continue

            if selected_mode == "Backup app+data (try)":
                ok, out, err, _ = adb_try_backup(serial, package_name, destination_dir)
                if ok:
                    local_banner = make_banner("OK", f"Backup created for {package_name}.")
                else:
                    local_banner = make_banner("WARN", f"Backup unavailable: {err or out or 'not supported'}")
                continue

            backup_ok, out, err, _ = adb_try_backup(serial, package_name, destination_dir)
            if backup_ok:
                local_banner = make_banner("OK", f"Backup created for {package_name}.")
                continue
            export_ok, exported, export_err = adb_export_apk_to_dir(serial, package_name, destination_dir)
            if export_ok:
                local_banner = make_banner("WARN", f"Backup unavailable, exported {len(exported)} APK file(s).")
            else:
                local_banner = make_banner("ERROR", f"Auto mode failed: {err or out or export_err}")
            continue


def device_submenu(device, cfg, banner=None):
    serial = device["serial"]
    options = ["Screen Share", "Apps", "Disconnect", "Back"]
    idx = 0
    local_banner = banner
    updated_cfg = dict(cfg)
    while True:
        width = terminal_width()
        decorated = [f"{opt} ({serial})" if opt != "Back" else opt for opt in options]
        lines = render_menu(decorated, idx, width, banner=local_banner)
        os.system("cls" if os.name == "nt" else "clear")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        key = get_key()
        local_banner = tick_banner(local_banner)
        if key == "\x1b[A":
            idx = (idx - 1) % len(options)
            continue
        if key == "\x1b[B":
            idx = (idx + 1) % len(options)
            continue
        if key == "\x1b":
            return updated_cfg, None
        if key != "\r":
            continue

        selected = options[idx]
        if selected == "Back":
            return updated_cfg, None

        if selected == "Screen Share":
            updated_cfg = normalize_audio_preferences(updated_cfg)
            ok, err = launch_scrcpy_result(serial, updated_cfg)
            if ok:
                updated_cfg["applied_audio_target"] = updated_cfg.get("audio_target", "host")
                updated_cfg["applied_active_recall"] = bool(updated_cfg.get("active_recall", False))
                updated_cfg["applied_microphone_bus"] = bool(updated_cfg.get("microphone_bus", False))
                updated_cfg["last_device_serial"] = serial
                save_config(updated_cfg)
                updated_cfg = load_config()
                local_banner = make_banner("OK", f"Screen Share started for {serial}.")
            else:
                local_banner = make_banner("ERROR", err or "Screen Share failed.")
            continue

        if selected == "Disconnect":
            if not confirm_action(f"Disconnect device '{serial}'?", default_no=True):
                local_banner = make_banner("WARN", "Disconnect cancelled.")
                continue
            ok, out, err, _ = adb_disconnect(serial)
            if ok:
                local_banner = make_banner("OK", f"Disconnected: {serial}")
            else:
                local_banner = make_banner("ERROR", f"Disconnect failed: {err or out or 'unknown error'}")
            continue

        if selected == "Apps":
            local_banner = apps_submenu(serial, banner=local_banner)
            continue


def settings_screen(cfg):
    temp_cfg = dict(cfg)
    temp_cfg["command_alias"] = normalize_alias(temp_cfg.get("command_alias", "xyz-scrcpy"))
    temp_cfg["open_cooldown_seconds"] = int(temp_cfg.get("open_cooldown_seconds", 30) or 30)
    field_idx = 0
    field_meta = {
        "auto_start": {"kind": "bool", "label": "Auto-start monitor"},
        "auto_discover": {"kind": "bool", "label": "Auto-discover devices"},
        "open_cooldown_seconds": {
            "kind": "int",
            "label": "Open cooldown (seconds)",
            "min": 0,
            "max": 600,
            "step": 5,
            "prompt": "Enter open cooldown in seconds (0-600)",
        },
        "audio_target": {"kind": "enum_audio", "label": "Audio target"},
        "active_recall": {"kind": "bool", "label": "Active Recall"},
        "microphone_bus": {"kind": "bool", "label": f"Microphone Bus ({MIC_BUS_NAME})"},
        "pause_on_exit": {"kind": "bool", "label": "Pause on EXIT"},
        "exit_pause_minutes": {
            "kind": "int",
            "label": "Pause duration (minutes)",
            "min": 1,
            "max": 43200,
            "step": 10,
            "prompt": "Enter pause duration in minutes (1-43200)",
        },
        "command_alias": {
            "kind": "text",
            "label": "Command alias",
            "prompt": "Enter new command alias",
        },
    }
    sections = [
        ("Launch behavior", ["auto_start", "auto_discover", "open_cooldown_seconds"]),
        ("Audio", ["audio_target", "active_recall", "microphone_bus"]),
        ("Session / Pause", ["pause_on_exit", "exit_pause_minutes"]),
        ("General", ["command_alias"]),
    ]
    fields = [
        "auto_start",
        "auto_discover",
        "open_cooldown_seconds",
        "audio_target",
        "active_recall",
        "microphone_bus",
        "pause_on_exit",
        "exit_pause_minutes",
        "command_alias",
        "APPLY",
        "CANCEL",
    ]

    def clamp_int(value, min_value, max_value):
        return max(min_value, min(max_value, value))

    def format_field(name):
        if name == "audio_target":
            return f"{field_meta[name]['label']}: {str(temp_cfg.get(name, 'host')).upper()}"
        if name in {"active_recall", "microphone_bus", "auto_start", "auto_discover", "pause_on_exit"}:
            return f"{field_meta[name]['label']}: {'ON' if bool(temp_cfg.get(name, False)) else 'OFF'}"
        if name in {"open_cooldown_seconds", "exit_pause_minutes"}:
            range_hint = f"{field_meta[name]['min']}-{field_meta[name]['max']}"
            return f"{field_meta[name]['label']}: {temp_cfg.get(name)} [{range_hint}]"
        if name == "command_alias":
            return f"{field_meta[name]['label']}: {temp_cfg.get(name, 'xyz-scrcpy')}"
        if name == "APPLY":
            return "[Apply]"
        if name == "CANCEL":
            return "[Cancel]"
        return name

    def apply_fast_edit(name, key):
        meta = field_meta.get(name)
        if not meta:
            return
        kind = meta["kind"]
        if kind == "bool":
            temp_cfg[name] = not bool(temp_cfg.get(name, False))
            return
        if kind == "enum_audio":
            current = str(temp_cfg.get("audio_target", "host")).lower()
            temp_cfg["audio_target"] = "device" if current == "host" else "host"
            return
        if kind == "int":
            direction = 1 if key == "\x1b[C" else -1
            step = int(meta.get("step", 1))
            current = int(temp_cfg.get(name, meta.get("min", 0)) or meta.get("min", 0))
            updated = current + (step * direction)
            temp_cfg[name] = clamp_int(updated, int(meta.get("min", 0)), int(meta.get("max", 999999)))

    def apply_precise_edit(name):
        meta = field_meta.get(name)
        if not meta:
            return
        kind = meta["kind"]
        if kind == "text":
            os.system("cls" if os.name == "nt" else "clear")
            try:
                entered = prompt_text_input(meta["prompt"], temp_cfg.get(name, "xyz-scrcpy"))
            except EOFError:
                entered = temp_cfg.get(name, "xyz-scrcpy")
            temp_cfg[name] = normalize_alias(entered)
            return
        if kind == "int":
            os.system("cls" if os.name == "nt" else "clear")
            try:
                entered = prompt_text_input(meta["prompt"], str(temp_cfg.get(name, meta.get("min", 0))))
            except EOFError:
                entered = str(temp_cfg.get(name, meta.get("min", 0)))
            try:
                parsed = int(entered)
            except ValueError:
                parsed = int(temp_cfg.get(name, meta.get("min", 0)) or meta.get("min", 0))
            temp_cfg[name] = clamp_int(parsed, int(meta.get("min", 0)), int(meta.get("max", 999999)))
            return
        apply_fast_edit(name, "\x1b[C")

    while True:
        width = terminal_width()
        lines = render_tui_header("SETTINGS - HYBRID EDIT", width)
        selected = fields[field_idx]
        rendered_rows = []
        for title, group_fields in sections:
            rendered_rows.append((None, f"[{title}]"))
            for name in group_fields:
                rendered_rows.append((name, format_field(name)))
            rendered_rows.append((None, ""))
        rendered_rows.append((None, "[Actions]"))
        rendered_rows.append(("APPLY", format_field("APPLY")))
        rendered_rows.append(("CANCEL", format_field("CANCEL")))

        sel_row = 0
        for row_idx, (name, _row) in enumerate(rendered_rows):
            if name == selected:
                sel_row = row_idx
                break
        total_rows = len(rendered_rows)
        page_size = visible_page_size(12)
        window_start, window_end = paginated_window(total_rows, sel_row, page_size)

        if window_start > 0:
            lines.append(center_line("...", width))

        for name, row in rendered_rows[window_start:window_end]:
            if name is None:
                if row:
                    lines.append(center_line(f"{MAGENTA}{trunc_text(row, width - 2)}{RESET}", width))
                else:
                    lines.append("")
                continue
            text = trunc_text(row, width - 4)
            changed = name in temp_cfg and temp_cfg.get(name) != cfg.get(name)
            if changed:
                text = f"{RED}{text}{RESET}"
            lines.append(center_line((f"> {text}" if name == selected else f"  {text}"), width))

        if window_end < total_rows:
            lines.append(center_line("...", width))
        lines.append("")
        lines.append(center_line("[UP/DOWN] move [LEFT/RIGHT] quick edit [ENTER] precise/apply [ESC] back", width))
        lines.extend(render_brand_footer(width))
        os.system("cls" if os.name == "nt" else "clear")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        key = get_key()
        if key == "\x1b[A":
            field_idx = (field_idx - 1) % len(fields)
        elif key == "\x1b[B":
            field_idx = (field_idx + 1) % len(fields)
        elif key in ("\x1b[C", "\x1b[D", " "):
            name = fields[field_idx]
            if name not in {"APPLY", "CANCEL"}:
                apply_fast_edit(name, key)
        elif key == "\r":
            name = fields[field_idx]
            if name == "APPLY":
                temp_cfg["command_alias"] = normalize_alias(temp_cfg["command_alias"])
                temp_cfg = normalize_audio_preferences(temp_cfg)
                save_config(temp_cfg)
                sync_ok, sync_err = sync_alias_launcher(temp_cfg["command_alias"])
                return load_config(), "apply", sync_err if not sync_ok else ""
            elif name == "CANCEL":
                return cfg, "cancel", ""
            else:
                apply_precise_edit(name)
        elif key == "\x1b":
            return cfg, "cancel", ""


def activate_pause_on_exit(cfg):
    cfg["pause_active"] = True
    cfg["pause_wait_reconnect"] = True
    cfg["pause_seen_disconnect"] = False
    pause_minutes = int(cfg.get("exit_pause_minutes", 1440))
    cfg["pause_until_epoch"] = int(time.time()) + (max(1, pause_minutes) * 60)
    save_config(cfg)


def main():
    if hasattr(signal, "SIGWINCH"):
        signal.signal(signal.SIGWINCH, lambda *_: None)
    lock_file = open(LOCK_PATH, "w", encoding="utf-8")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)

    idx = 0
    cfg = load_config()
    banner = None
    restore_menu_serial = None
    alias = normalize_alias(cfg.get("command_alias", "xyz-scrcpy"))
    banner_parts: list[str] = []
    stale_launchers = stale_managed_launcher_names(alias)
    if stale_launchers:
        banner_parts.append(
            f"Use `{alias}` — old launcher(s) on PATH: {', '.join(stale_launchers)}"
        )
    if not adb_is_available():
        banner_parts.append(adb_devices_status_message(cfg))
    else:
        device_hint = adb_devices_status_message(cfg)
        if device_hint:
            banner_parts.append(device_hint)
    if banner_parts:
        banner = make_banner("WARN", " | ".join(banner_parts))
    try:
        while True:
            width = terminal_width()
            devices = list_devices_for_menu(cfg)
            if restore_menu_serial:
                restored = main_menu_index_for_serial(devices, restore_menu_serial)
                if restored is not None:
                    idx = restored
                restore_menu_serial = None
            device_labels = [d["label"] for d in devices]
            restart_label = "RESTART"
            if has_audio_pending(cfg):
                restart_label = f"{LIME}RESTART{RESET}"
            else:
                restart_label = f"{RED}RESTART{RESET}"
            opts = device_labels + ["SETTINGS", restart_label, "EXIT"]
            if idx >= len(opts):
                idx = 0

            os.system("cls" if os.name == "nt" else "clear")
            sys.stdout.write("\n".join(render_menu(opts, idx, width, banner=banner)))
            sys.stdout.flush()

            key = wait_menu_key(MAIN_MENU_DEVICE_POLL_SEC)
            if key is None:
                if not devices and cfg.get("last_device_serial"):
                    banner = make_banner(
                        "WARN",
                        "Waiting for device... (refreshing every 5s)",
                        ttl=2,
                    )
                elif adb_is_available():
                    hint = adb_devices_status_message()
                    if hint:
                        banner = make_banner("WARN", hint, ttl=2)
                    else:
                        banner = tick_banner(banner)
                continue
            banner = tick_banner(banner)
            if key == "\x1b[A":
                idx = (idx - 1) % len(opts)
            elif key == "\x1b[B":
                idx = (idx + 1) % len(opts)
            elif key == "\r":
                if idx < len(devices):
                    selected_device = devices[idx]
                    cfg, sub_banner = device_submenu(selected_device, cfg, banner=banner)
                    if sub_banner is not None:
                        banner = sub_banner
                    restore_menu_serial = selected_device["serial"]
                    continue
                selected = opts[idx]
                if selected == "EXIT":
                    if cfg.get("pause_on_exit"):
                        activate_pause_on_exit(cfg)
                    break
                if selected == "SETTINGS":
                    cfg, settings_action, sync_err = settings_screen(cfg)
                    if settings_action == "apply":
                        if sync_err:
                            banner = make_banner(
                                "ERROR",
                                f"Settings saved but alias sync failed: {sync_err}",
                            )
                        else:
                            banner = make_banner("OK", "Settings updated.")
                        restore_menu_serial = cfg.get("last_device_serial")
                    else:
                        restore_menu_serial = cfg.get("last_device_serial")
                    continue
                if "RESTART" in selected:
                    target_serial = cfg.get("last_device_serial")
                    if not target_serial and devices:
                        target_serial = devices[0]["serial"]
                    if target_serial:
                        cfg = normalize_audio_preferences(cfg)
                        kill_scrcpy_for_serial(target_serial)
                        time.sleep(0.4)
                        ok, err = launch_scrcpy_result(target_serial, cfg)
                        if ok:
                            cfg["applied_audio_target"] = cfg.get("audio_target", "host")
                            cfg["applied_active_recall"] = bool(cfg.get("active_recall", False))
                            cfg["applied_microphone_bus"] = bool(cfg.get("microphone_bus", False))
                            cfg["last_device_serial"] = target_serial
                            save_config(cfg)
                            cfg = load_config()
                            banner = make_banner("OK", f"Restarted screen share for {target_serial}.")
                            restore_menu_serial = target_serial
                        else:
                            banner = make_banner(
                                "ERROR",
                                err or "Cannot restart screen share.",
                            )
                            restore_menu_serial = target_serial
                    else:
                        banner = make_banner("WARN", "No target device available to restart.")
                    continue
            elif key == "\x1b":
                break
    finally:
        if os.path.exists(LOCK_PATH):
            try:
                lock_file.close()
            except OSError:
                pass
            try:
                os.remove(LOCK_PATH)
            except OSError:
                pass
        os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    main()
