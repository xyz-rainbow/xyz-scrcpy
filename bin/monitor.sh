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
SERIAL_STATE_FILE="/tmp/xyz_monitor_serials.state"
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
        rm -f "$SERIAL_STATE_FILE"
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

read_serials_from_adb() {
    adb devices | awk '/device$/{print $1}' | paste -sd ',' -
}

count_serials() {
    local serials="$1"
    if [ -z "$serials" ]; then
        echo 0
        return
    fi
    awk -F',' '{print NF}' <<< "$serials"
}

first_serial() {
    local serials="$1"
    IFS=',' read -r first _ <<< "$serials"
    echo "$first"
}

load_previous_serials() {
    if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
        echo "${TEST_PREV_SERIALS:-}"
        return
    fi
    if [ -f "$SERIAL_STATE_FILE" ]; then
        cat "$SERIAL_STATE_FILE"
    fi
}

save_current_serials() {
    local serials="$1"
    if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
        return
    fi
    printf '%s' "$serials" > "$SERIAL_STATE_FILE"
}

update_pause_state_from_snapshots() {
    local prev_serials="$1"
    local curr_serials="$2"
    local device_count="$3"
    PYTHONPATH="$PYTHONPATH_DIR" python3 - "$prev_serials" "$curr_serials" "$device_count" <<'PY'
import sys
import time
from config_loader import load_config, save_config

prev_serials = sys.argv[1].strip()
curr_serials = sys.argv[2].strip()
device_count = int(sys.argv[3])
cfg = load_config()
now = int(time.time())

if cfg.get("pause_active"):
    auto_discover = bool(cfg.get("auto_discover", True))
    pause_until = int(cfg.get("pause_until_epoch", 0) or 0)
    wait_reconnect = bool(cfg.get("pause_wait_reconnect", False))
    seen_disconnect = bool(cfg.get("pause_seen_disconnect", False))
    prev_set = {x for x in prev_serials.split(",") if x}
    curr_set = {x for x in curr_serials.split(",") if x}

    # Reglas de contrato:
    # 1) Pause on EXIT activa la pausa.
    # 2) Con auto_discover ON, una reconexion valida levanta la pausa.
    # 3) Reconexion valida: hubo desconexion previa o cambio de conjunto de seriales.
    reconnect_event = bool(curr_set) and (seen_disconnect or (bool(prev_set) and curr_set != prev_set))

    if device_count == 0 and wait_reconnect:
        seen_disconnect = True
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
PY
}

evaluate_test_pause_state() {
    local prev_serials="$1"
    local curr_serials="$2"
    local pause_active="${TEST_PAUSE_ACTIVE:-false}"
    local wait_reconnect="${TEST_PAUSE_WAIT_RECONNECT:-false}"
    local seen_disconnect="${TEST_PAUSE_SEEN_DISCONNECT:-false}"
    local auto_discover="${TEST_AUTO_DISCOVER:-true}"

    if [ "$pause_active" = "true" ] && [ "$wait_reconnect" = "true" ] && [ "$auto_discover" = "true" ]; then
        if [ -z "$curr_serials" ]; then
            seen_disconnect="true"
        elif [[ "$seen_disconnect" = "true" || ( -n "$prev_serials" && "$prev_serials" != "$curr_serials" ) ]]; then
            pause_active="false"
            echo "RECONNECT_RESUME" >&2
        fi
    fi

    echo "$pause_active"
}

compute_terminal_geometry() {
    local device_count="$1"
    local cols=70
    local base_rows=29
    local extra_rows=0

    # Keep three extra lines to avoid clipping header,
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
        CURRENT_SERIALS="${TEST_CURR_SERIALS:-${TEST_DEVICE_SERIAL:-}}"
    else
        CURRENT_SERIALS="$(read_serials_from_adb)"
    fi

    PREVIOUS_SERIALS="$(load_previous_serials)"
    DEVICE_COUNT="$(count_serials "$CURRENT_SERIALS")"
    DEVICE_SERIAL="$(first_serial "$CURRENT_SERIALS")"

    if [ "${MONITOR_TEST_MODE:-0}" = "1" ]; then
        AUTO_START="${TEST_AUTO_START:-true}"
        AUTO_DISCOVER="${TEST_AUTO_DISCOVER:-true}"
        PAUSE_ACTIVE="$(evaluate_test_pause_state "$PREVIOUS_SERIALS" "$CURRENT_SERIALS")"
    else
        update_pause_state_from_snapshots "$PREVIOUS_SERIALS" "$CURRENT_SERIALS" "$DEVICE_COUNT"
        AUTO_START="$(read_config_value auto_start)"
        AUTO_DISCOVER="$(read_config_value auto_discover)"
        PAUSE_ACTIVE="$(read_config_value pause_active)"
    fi

    save_current_serials "$CURRENT_SERIALS"

    # Contrato operativo:
    # - auto_start: habilita automatizacion del monitor.
    # - auto_discover: habilita reaccion a nuevas conexiones.
    # - pause_on_exit/pause_active: bloquea aperturas hasta evento valido o timeout.
    if [ -n "$DEVICE_SERIAL" ] && [ "$AUTO_START" = "true" ] && [ "$AUTO_DISCOVER" = "true" ] && [ "$PAUSE_ACTIVE" != "true" ]; then
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
