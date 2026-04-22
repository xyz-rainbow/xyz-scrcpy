#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK_SCRIPT="$SCRIPT_DIR/check_and_repair.sh"
MENU_SCRIPT="$SCRIPT_DIR/menu.py"
LOG_FILE="$REPO_DIR/config/check.log"
FULL_LOG_FILE="$REPO_DIR/config/full-check.log"
FULL_PID_FILE="/tmp/xyz_full_checks.pid"

open_detached_menu_terminal() {
    if [ "${XYZ_LAUNCHER_WINDOW:-0}" = "1" ]; then
        return 1
    fi
    if [ "${XYZ_SKIP_MENU_EXEC:-0}" = "1" ]; then
        return 1
    fi
    if [ "$(uname -s)" != "Linux" ]; then
        return 1
    fi
    if [ -z "${DISPLAY:-}" ] || [ -z "${XDG_RUNTIME_DIR:-}" ]; then
        return 1
    fi
    if ! command -v gnome-terminal >/dev/null 2>&1; then
        return 1
    fi

    gnome-terminal \
        --hide-menubar \
        --geometry=40x18 \
        --title="XYZ Launcher" \
        -- \
        bash -lc "XYZ_LAUNCHER_WINDOW=1 bash \"$0\""
    return 0
}

start_background_full_checks() {
    if [ -f "$FULL_PID_FILE" ]; then
        old_pid="$(cat "$FULL_PID_FILE" 2>/dev/null || true)"
        if [ -n "$old_pid" ] && ps -p "$old_pid" > /dev/null 2>&1; then
            return
        fi
    fi
    (
        nohup env XYZ_CHECK_MODE=full XYZ_CHECK_LOG_FILE="$FULL_LOG_FILE" bash "$CHECK_SCRIPT" > /dev/null 2>&1 &
        echo $! > "$FULL_PID_FILE"
    ) >/dev/null 2>&1
}

if open_detached_menu_terminal; then
    exit 0
fi

if [ "${XYZ_CHECKS_ALREADY_DONE:-0}" = "1" ]; then
    status="${XYZ_CHECKS_STATUS:-PASS}"
    echo "[INFO] Reusing installer check result: $status"
else
    echo "[INFO] Running quick syntax checks..."
    status="$(env XYZ_CHECK_MODE=quick bash "$CHECK_SCRIPT" | tail -n 1)"
fi

case "$status" in
    PASS|PASS_AFTER_REPAIR)
        start_background_full_checks
        if [ -f "$FULL_LOG_FILE" ]; then
            echo "[INFO] Full test suite is running in background: $FULL_LOG_FILE"
        else
            echo "[INFO] Full test suite started in background."
        fi
        ;;
    FAIL_OPEN)
        echo "[WARNING] Automated checks are still failing."
        echo "[WARNING] Fail-open mode is available."
        echo "[WARNING] Please report with logs: https://github.com/xyz-rainbow/xyz-scrcpy/issues"
        echo "[WARNING] GitHub issue creation requires login; or email log to rainbow@rainbowtechnology.xyz"
        read -r -p "Open menu anyway despite errors? (Y/n): " open_anyway
        open_anyway="${open_anyway,,}"
        if [ -n "$open_anyway" ] && [ "$open_anyway" != "y" ] && [ "$open_anyway" != "yes" ]; then
            echo "[INFO] Menu launch cancelled by user."
            exit 1
        fi
        ;;
    *)
        echo "[WARNING] Unknown check status: $status"
        ;;
esac

if [ -f "$LOG_FILE" ]; then
    echo "[INFO] Check log: $LOG_FILE"
fi

if [ "${XYZ_SKIP_MENU_EXEC:-0}" = "1" ]; then
    echo "[INFO] Test mode: menu execution skipped."
    exit 0
fi

echo "[INFO] Launching interactive menu..."
exec python3 "$MENU_SCRIPT"
