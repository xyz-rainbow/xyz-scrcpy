#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK_SCRIPT="$SCRIPT_DIR/check_and_repair.sh"
MENU_SCRIPT="$SCRIPT_DIR/menu.py"
LOG_FILE="$REPO_DIR/config/check.log"

status="$(bash "$CHECK_SCRIPT" | tail -n 1)"
case "$status" in
    PASS|PASS_AFTER_REPAIR)
        ;;
    FAIL_OPEN)
        echo "[WARNING] Automated checks are still failing."
        echo "[WARNING] Fail-open mode is available."
        echo "[WARNING] Please report with logs: https://github.com/xyz-rainbow/xyz-scrcpy/issues"
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

exec python3 "$MENU_SCRIPT"
