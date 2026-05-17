"""ADB USB / WiFi transport helpers."""

from __future__ import annotations

import re
import subprocess
from typing import Callable


def classify_serial(serial: str) -> str:
    return "tcp" if ":" in serial else "usb"


def get_device_ip(adb_exe: str, serial: str, run_command: Callable) -> tuple[str | None, str]:
    """Return WiFi IPv4 address from device shell, or (None, error)."""
    ok, out, err, _code = run_command(
        [adb_exe, "-s", serial, "shell", "ip", "-4", "route", "get", "table", "wlan0"],
    )
    if ok and out:
        match = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", out)
        if match:
            return match.group(1), ""
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
        if match:
            return match.group(1), ""

    ok, out, err, _code = run_command(
        [adb_exe, "-s", serial, "shell", "ip", "-4", "addr", "show", "wlan0"],
    )
    if ok and out:
        match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
        if match:
            return match.group(1), ""

    ok, out, err, _code = run_command(
        [adb_exe, "-s", serial, "shell", "getprop", "dhcp.wlan0.ipaddress"],
    )
    if ok and out.strip():
        ip = out.strip().splitlines()[0].strip()
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
            return ip, ""

    return None, err or out or "Could not detect device WiFi IP."


def enable_tcpip(adb_exe: str, serial: str, port: int, run_command: Callable) -> tuple[bool, str]:
    ok, out, err, _code = run_command([adb_exe, "-s", serial, "tcpip", str(port)])
    if ok:
        return True, (out or "").strip()
    return False, err or out or "adb tcpip failed."


def connect_wifi(
    adb_exe: str, ip: str, port: int, run_command: Callable
) -> tuple[bool, str, str]:
    target = f"{ip}:{port}"
    ok, out, err, _code = run_command([adb_exe, "connect", target])
    combined = (out or "") + (err or "")
    if ok and ("connected to" in combined.lower() or "already connected" in combined.lower()):
        return True, target, combined.strip()
    return False, target, err or out or f"adb connect {target} failed."


def disconnect_session(adb_exe: str, serial: str, run_command: Callable) -> tuple[bool, str]:
    if classify_serial(serial) == "tcp":
        ok, out, err, _code = run_command([adb_exe, "disconnect", serial])
        if ok:
            return True, (out or "").strip()
        return False, err or out or "adb disconnect failed."
    ok, out, err, _code = run_command([adb_exe, "-s", serial, "disconnect"])
    if ok:
        return True, (out or "").strip()
    ok, out, err, _code = run_command([adb_exe, "disconnect", serial])
    if ok:
        return True, (out or "").strip()
    return False, err or out or "disconnect failed."


def switch_usb(adb_exe: str, serial: str, run_command: Callable) -> tuple[bool, str]:
    ok, out, err, _code = run_command([adb_exe, "-s", serial, "usb"])
    if ok:
        return True, (out or "").strip()
    return False, err or out or "adb usb failed."
