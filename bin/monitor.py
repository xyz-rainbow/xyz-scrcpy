#!/usr/bin/env python3
"""Background USB device monitor (multi-OS port of legacy bin/monitor.sh)."""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
BIN_DIR = SCRIPT_DIR

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))
import adb_resolve  # noqa: E402
MENU_SCRIPT = BIN_DIR / "menu.py"
CFG_LOADER = BIN_DIR / "config_loader.py"

_STATE_ROOT = Path(os.environ.get("MONITOR_STATE_DIR", tempfile.gettempdir()))
PID_FILE = _STATE_ROOT / "xyz_monitor.pid"
SERIAL_STATE_FILE = _STATE_ROOT / "xyz_monitor_serials.state"
LAST_OPEN_EPOCH_FILE = _STATE_ROOT / "xyz_monitor_last_open.epoch"
LAST_BLOCK_REASON_FILE = _STATE_ROOT / "xyz_monitor_last_block_reason.state"

_LOGGER = logging.getLogger("xyz.monitor")


def _ensure_repo_on_path() -> None:
    b = str(BIN_DIR)
    if b not in sys.path:
        sys.path.insert(0, b)


def _prepend_vendor_to_path() -> None:
    vendor = REPO_DIR / "vendor"
    if vendor.is_dir():
        os.environ["PATH"] = str(vendor) + os.pathsep + os.environ.get("PATH", "")


def _setup_logging() -> None:
    log_dir = REPO_DIR / "config"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "monitor.log"
    root = logging.getLogger()
    root.handlers.clear()
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(fh)
    if os.environ.get("MONITOR_TEST_MODE") != "1":
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fh.formatter)
        root.addHandler(sh)
    root.setLevel(logging.INFO)


def _python_for_subprocess() -> str:
    return sys.executable or shutil.which("python3") or shutil.which("python") or "python3"


def _import_config():
    _ensure_repo_on_path()
    from config_loader import load_config, save_config  # noqa: WPS433

    return load_config, save_config


def log_message(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOGGER.info(msg)


def read_config_value(key: str) -> str:
    load_config, _ = _import_config()
    cfg = load_config()
    value = cfg.get(key, "")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def update_pause_state_from_snapshots(prev_serials: str, curr_serials: str, device_count: int) -> None:
    load_config, save_config = _import_config()
    cfg = load_config()
    now = int(time.time())

    if cfg.get("pause_active"):
        auto_discover = bool(cfg.get("auto_discover", True))
        pause_until = int(cfg.get("pause_until_epoch", 0) or 0)
        wait_reconnect = bool(cfg.get("pause_wait_reconnect", False))
        seen_disconnect = bool(cfg.get("pause_seen_disconnect", False))
        prev_set = {x for x in prev_serials.split(",") if x}
        curr_set = {x for x in curr_serials.split(",") if x}

        reconnect_event = bool(curr_set) and (
            seen_disconnect or (bool(prev_set) and curr_set != prev_set)
        )

        if device_count == 0 and wait_reconnect:
            cfg["pause_seen_disconnect"] = True

        if auto_discover and wait_reconnect and reconnect_event:
            cfg["pause_active"] = False
            cfg["pause_wait_reconnect"] = False
            cfg["pause_seen_disconnect"] = False
            cfg["pause_until_epoch"] = 0
        elif now >= pause_until and pause_until > 0:
            cfg["pause_active"] = False
            cfg["pause_wait_reconnect"] = False
            cfg["pause_seen_disconnect"] = False
            cfg["pause_until_epoch"] = 0

        save_config(cfg)


def evaluate_test_pause_state(prev_serials: str, curr_serials: str) -> str:
    pause_active = os.environ.get("TEST_PAUSE_ACTIVE", "false").lower() == "true"
    wait_reconnect = os.environ.get("TEST_PAUSE_WAIT_RECONNECT", "false").lower() == "true"
    seen_disconnect = os.environ.get("TEST_PAUSE_SEEN_DISCONNECT", "false").lower() == "true"
    auto_discover = os.environ.get("TEST_AUTO_DISCOVER", "true").lower() == "true"

    if pause_active and wait_reconnect and auto_discover:
        if not curr_serials.strip():
            seen_disconnect = True
        elif seen_disconnect or (prev_serials and prev_serials != curr_serials):
            pause_active = False
            print("RECONNECT_RESUME", file=sys.stderr, flush=True)

    return "true" if pause_active else "false"


def read_serials_from_adb() -> str:
    try:
        adb = adb_resolve.resolve_adb_executable(REPO_DIR)[0]
        out = subprocess.check_output(
            [adb, "devices"],
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    serials: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return ",".join(serials)


def count_serials(serials: str) -> int:
    if not serials.strip():
        return 0
    return len([x for x in serials.split(",") if x])


def first_serial(serials: str) -> str:
    for x in serials.split(","):
        if x.strip():
            return x.strip()
    return ""


def load_previous_serials() -> str:
    if os.environ.get("MONITOR_TEST_MODE") == "1":
        return os.environ.get("TEST_PREV_SERIALS", "")
    if SERIAL_STATE_FILE.is_file():
        return SERIAL_STATE_FILE.read_text(encoding="utf-8", errors="ignore")
    return ""


def save_current_serials(serials: str) -> None:
    if os.environ.get("MONITOR_TEST_MODE") == "1":
        return
    SERIAL_STATE_FILE.write_text(serials, encoding="utf-8")


def resolve_open_cooldown_seconds() -> int:
    default_value = 30
    if os.environ.get("MONITOR_TEST_MODE") == "1" and os.environ.get("TEST_OPEN_COOLDOWN_SECONDS"):
        candidate = os.environ["TEST_OPEN_COOLDOWN_SECONDS"]
    elif os.environ.get("OPEN_COOLDOWN_SECONDS"):
        candidate = os.environ["OPEN_COOLDOWN_SECONDS"]
    else:
        candidate = read_config_value("open_cooldown_seconds")
    try:
        n = int(candidate)
    except (TypeError, ValueError):
        n = default_value
    return max(0, min(n, 600))


def last_open_epoch() -> int:
    if not LAST_OPEN_EPOCH_FILE.is_file():
        return 0
    raw = LAST_OPEN_EPOCH_FILE.read_text(encoding="utf-8", errors="ignore").strip()
    return int(raw) if raw.isdigit() else 0


def touch_last_open_epoch() -> None:
    LAST_OPEN_EPOCH_FILE.write_text(str(int(time.time())), encoding="utf-8")


def is_open_cooldown_active(seconds: int) -> tuple[bool, str]:
    if seconds <= 0:
        return False, ""
    now = int(time.time())
    last = last_open_epoch()
    if last <= 0:
        return False, ""
    delta = now - last
    if delta < seconds:
        return True, f"cooldown_active({delta}s/{seconds}s)"
    return False, ""


def validate_menu_syntax() -> bool:
    py = _python_for_subprocess()
    targets = [str(MENU_SCRIPT), str(CFG_LOADER), str(BIN_DIR / "monitor.py")]
    for t in targets:
        if Path(t).is_file():
            r = subprocess.run(
                [py, "-m", "py_compile", t],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if r.returncode != 0:
                return False
    return True


def compute_terminal_geometry(device_count: int) -> str:
    cols = 40
    base_rows = 18
    extra_rows = max(0, device_count - 1)
    return f"{cols}x{base_rows + extra_rows}"


def is_monitor_or_scrcpy_active(serial: str) -> tuple[bool, str]:
    import psutil as ps

    if os.environ.get("MONITOR_TEST_MODE") == "1":
        if os.environ.get("MONITOR_HAS_MENU_PROCESS") == "1":
            return True, "existing_menu_process"
        if os.environ.get("MONITOR_HAS_WINDOW") == "1" or os.environ.get("MONITOR_HAS_SCRCPY") == "1":
            return True, "existing_monitor_or_scrcpy"
        return False, ""

    menu_path = str(MENU_SCRIPT)
    for proc in ps.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or ())
        except (ps.Error, TypeError):
            continue
        if "XYZ Monitor -" in cmd:
            return True, "existing_monitor_window"
        if menu_path in cmd and "menu.py" in cmd:
            return True, "existing_menu_process"

    if serial:
        pat = re.compile(r"(scrcpy|scrcpy\.exe).*-s\s+" + re.escape(serial), re.I)
        for proc in ps.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or ())
            except (ps.Error, TypeError):
                continue
            if pat.search(cmd):
                return True, "existing_scrcpy_serial"

    for proc in ps.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            cmd = " ".join(proc.info.get("cmdline") or ())
        except (ps.Error, TypeError):
            continue
        if name in ("scrcpy", "scrcpy.exe") or re.search(r"[/\\]scrcpy(\.exe)?(\s|$)", cmd, re.I):
            return True, "existing_scrcpy_any"

    return False, ""


def log_block_reason_if_changed(reason: str) -> None:
    if not reason:
        return
    prev = ""
    if LAST_BLOCK_REASON_FILE.is_file():
        prev = LAST_BLOCK_REASON_FILE.read_text(encoding="utf-8", errors="ignore")
    if prev != reason:
        log_message(f"[INFO] Popup blocked: {reason}")
        LAST_BLOCK_REASON_FILE.write_text(reason, encoding="utf-8")


def clear_block_reason_state() -> None:
    try:
        LAST_BLOCK_REASON_FILE.unlink()
    except OSError:
        pass


def open_menu_terminal(geometry: str, title: str) -> bool:
    import terminal_open

    py = _python_for_subprocess()
    return terminal_open.open_menu_script(
        menu_py=MENU_SCRIPT,
        python_exe=py,
        cwd=REPO_DIR,
        geometry=geometry,
        title=title,
    )


def _pid_lock_acquire() -> None:
    if os.environ.get("MONITOR_TEST_MODE") == "1":
        return
    import psutil

    if PID_FILE.is_file():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            old_pid = None
        if old_pid and psutil.pid_exists(old_pid):
            sys.exit(0)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _pid_lock_release() -> None:
    if os.environ.get("MONITOR_TEST_MODE") == "1":
        return
    for p in (PID_FILE, SERIAL_STATE_FILE):
        try:
            p.unlink()
        except OSError:
            pass


def run_loop() -> None:
    while True:
        if os.environ.get("MONITOR_TEST_MODE") == "1":
            current = os.environ.get("TEST_CURR_SERIALS") or os.environ.get("TEST_DEVICE_SERIAL", "")
        else:
            current = read_serials_from_adb()

        previous = load_previous_serials()
        device_count = count_serials(current)
        device_serial = first_serial(current)

        if os.environ.get("MONITOR_TEST_MODE") == "1":
            auto_start = os.environ.get("TEST_AUTO_START", "true").lower() == "true"
            auto_discover = os.environ.get("TEST_AUTO_DISCOVER", "true").lower() == "true"
            pause_active = evaluate_test_pause_state(previous, current) == "true"
        else:
            update_pause_state_from_snapshots(previous, current, device_count)
            auto_start = read_config_value("auto_start").lower() == "true"
            auto_discover = read_config_value("auto_discover").lower() == "true"
            pause_active = read_config_value("pause_active").lower() == "true"

        cooldown_sec = resolve_open_cooldown_seconds()
        save_current_serials(current)

        if device_serial and auto_start and auto_discover and not pause_active:
            if os.environ.get("MONITOR_TEST_MODE") == "1" or validate_menu_syntax():
                blocked, reason = is_monitor_or_scrcpy_active(device_serial)
                if not blocked:
                    cool, cool_reason = is_open_cooldown_active(cooldown_sec)
                    if cool:
                        log_block_reason_if_changed(cool_reason)
                    else:
                        geometry = compute_terminal_geometry(device_count)
                        if os.environ.get("MONITOR_TEST_MODE") == "1":
                            print(f"OPEN_TERMINAL:{geometry}:{device_serial}", flush=True)
                        else:
                            log_message(f"[INFO] Opening monitor terminal for serial {device_serial}.")
                            if open_menu_terminal(geometry, f"XYZ Monitor - {device_serial}"):
                                touch_last_open_epoch()
                                clear_block_reason_state()
                            else:
                                log_message(
                                    "[WARNING] No compatible terminal emulator found. Popup launch skipped."
                                )
                        time.sleep(3)
                else:
                    log_block_reason_if_changed(reason)
            else:
                log_message("[CRITICAL] Syntax error in menu/config loader. Terminal launch blocked.")
                time.sleep(30)

        time.sleep(5)
        if os.environ.get("MONITOR_RUN_ONCE") == "1":
            break


def main() -> None:
    os.chdir(REPO_DIR)
    _prepend_vendor_to_path()
    if os.environ.get("MONITOR_TEST_MODE") != "1":
        _setup_logging()
    _pid_lock_acquire()
    try:
        run_loop()
    finally:
        _pid_lock_release()


if __name__ == "__main__":
    try:
        import psutil  # noqa: F401
    except ImportError:
        print(
            "ERROR: psutil is required. pip install -r .requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
