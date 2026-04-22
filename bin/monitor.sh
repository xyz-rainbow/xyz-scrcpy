#!/bin/bash
# __  ____   _______
# \ \/ /\ \ / /__  /
#  \  /  \ V /  / / 
#  /  \   | |  / /_ 
# /_/\_\  |_| /____|
# #xyz-rainbowtechnology
# #rainbowtechnology.xyz
# #rainbow.xyz
# #rainbow@rainbowtechnology.xyz
# #i-love-you
# #You're not supposed to see this!

set -u

PID_FILE="/tmp/xyz_monitor.pid"
REPO_DIR="/home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy"
MENU_SCRIPT="$REPO_DIR/bin/menu.py"
CFG_LOADER="$REPO_DIR/bin/config_loader.py"
PYTHONPATH_DIR="$REPO_DIR/bin"

if [ "${MONITOR_TEST_MODE:-0}" != "1" ]; then
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            exit 0
        fi
    fi
    echo $$ > "$PID_FILE"
fi

cleanup() {
    if [ "${MONITOR_TEST_MODE:-0}" != "1" ]; then
        rm -f "$PID_FILE"
    fi
}
trap cleanup EXIT

log_message() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

validate_menu_syntax() {
    python3 -m py_compile "$MENU_SCRIPT" "$CFG_LOADER" > /dev/null 2>&1
}

read_config_value() {
    local key="$1"
    PYTHONPATH="$PYTHONPATH_DIR" python3 - "$key" <<'PY'
import json
import os
import sys
from config_loader import load_config, save_config

key = sys.argv[1]
cfg = load_config()
value = cfg.get(key, "")
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

update_pause_state_from_devices() {
    local device_count="$1"
    PYTHONPATH="$PYTHONPATH_DIR" python3 - "$device_count" <<'PY'
import sys
import time
from config_loader import load_config, save_config

device_count = int(sys.argv[1])
cfg = load_config()
now = int(time.time())

if cfg.get("pause_active"):
    pause_until = int(cfg.get("pause_until_epoch", 0) or 0)
    wait_reconnect = bool(cfg.get("pause_wait_reconnect", False))
    seen_disconnect = bool(cfg.get("pause_seen_disconnect", False))

    if device_count == 0 and wait_reconnect:
        seen_disconnect = True
        cfg["pause_seen_disconnect"] = True

    if device_count > 0 and wait_reconnect and seen_disconnect:
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
PY
}

compute_terminal_geometry() {
    local device_count="$1"
    local cols=70
    local base_rows=26
    local extra_rows=0

    # Keep two extra lines to avoid clipping header,
    # then add one line per additional detected device.
    if [ "$device_count" -gt 1 ]; then
        extra_rows=$((device_count - 1))
    fi

    local rows=$((base_rows + extra_rows))
    echo "${cols}x${rows}"
}

is_monitor_or_scrcpy_active() {
    local serial="$1"
    if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
        if [ "${MONITOR_HAS_WINDOW:-0}" = "1" ] || [ "${MONITOR_HAS_SCRCPY:-0}" = "1" ]; then
            return 0
        fi
        return 1
    fi

    # If any monitor terminal is already open, avoid opening more popups.
    if pgrep -f "XYZ Monitor -" > /dev/null; then
        return 0
    fi

    # If scrcpy is already running (same device or any device), do not spawn popups.
    if [ -n "$serial" ] && pgrep -f "scrcpy.*-s[[:space:]]*$serial" > /dev/null; then
        return 0
    fi
    if pgrep -x scrcpy > /dev/null; then
        return 0
    fi

    return 1
}

while true; do
    if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
        DEVICE_SERIAL="${TEST_DEVICE_SERIAL:-}"
        DEVICE_COUNT="${TEST_DEVICE_COUNT:-0}"
    else
        DEVICE_SERIAL=$(adb devices | awk '/device$/{print $1}' | head -1)
        DEVICE_COUNT=$(adb devices | awk '/device$/{count++} END{print count+0}')
    fi

    update_pause_state_from_devices "$DEVICE_COUNT"

    if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
        AUTO_START="${TEST_AUTO_START:-true}"
        PAUSE_ACTIVE="${TEST_PAUSE_ACTIVE:-false}"
    else
        AUTO_START="$(read_config_value auto_start)"
        PAUSE_ACTIVE="$(read_config_value pause_active)"
    fi

    if [ -n "$DEVICE_SERIAL" ] && [ "$AUTO_START" = "true" ] && [ "$PAUSE_ACTIVE" != "true" ]; then
        if [ "${MONITOR_TEST_MODE:-0}" = "1" ] || validate_menu_syntax; then
            if ! is_monitor_or_scrcpy_active "$DEVICE_SERIAL"; then
                GEOMETRY="$(compute_terminal_geometry "$DEVICE_COUNT")"
                if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
                    echo "OPEN_TERMINAL:$GEOMETRY:$DEVICE_SERIAL"
                else
                    gnome-terminal --hide-menubar --geometry="$GEOMETRY" --title="XYZ Monitor - $DEVICE_SERIAL" -- python3 "$MENU_SCRIPT"
                fi
                sleep 3
            fi
        else
            log_message "[CRITICAL] Syntax error in menu/config loader. Terminal launch blocked."
            sleep 30
        fi
    fi

    sleep 5
    if [ "${MONITOR_RUN_ONCE:-0}" = "1" ]; then
        break
    fi
done
# #xyz-rainbow
