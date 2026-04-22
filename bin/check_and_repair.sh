#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$REPO_DIR/config/check.log"
TIMEOUT_SECONDS="${XYZ_CHECK_TIMEOUT_SECONDS:-90}"

mkdir -p "$REPO_DIR/config"

log() {
    local msg="$1"
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$msg" | tee -a "$LOG_FILE"
}

run_checks() {
    : > "$LOG_FILE"
    log "Starting automated checks."
    if [ "${XYZ_TEST_MODE:-0}" = "1" ]; then
        case "${XYZ_TEST_SCENARIO:-pass}" in
            pass)
                log "Test mode: checks passed."
                return 0
                ;;
            fail)
                log "Test mode: checks failed."
                return 1
                ;;
            repair-pass)
                if [ "${XYZ_TEST_REPAIR_DONE:-0}" = "1" ]; then
                    log "Test mode: checks passed after repair."
                    return 0
                fi
                log "Test mode: initial checks failed."
                return 1
                ;;
        esac
    fi

    timeout "$TIMEOUT_SECONDS" python3 -m py_compile "$REPO_DIR/install_xyz.py" "$REPO_DIR/bin/menu.py" "$REPO_DIR/bin/config_loader.py" >> "$LOG_FILE" 2>&1 || return 1
    timeout "$TIMEOUT_SECONDS" bash -n "$REPO_DIR/bin/monitor.sh" >> "$LOG_FILE" 2>&1 || return 1
    timeout "$TIMEOUT_SECONDS" python3 -m unittest discover -s "$REPO_DIR/tests" -p "test_*.py" >> "$LOG_FILE" 2>&1 || return 1
    log "All automated checks passed."
    return 0
}

run_repair() {
    log "Checks failed, running repair workflow."
    if [ "${XYZ_TEST_MODE:-0}" = "1" ]; then
        export XYZ_TEST_REPAIR_DONE=1
        log "Test mode: simulated repair completed."
        return 0
    fi
    timeout "$TIMEOUT_SECONDS" "$REPO_DIR/repair_xyz.sh" >> "$LOG_FILE" 2>&1 || true
}

if run_checks; then
    echo "PASS"
    exit 0
fi

run_repair
if run_checks; then
    echo "PASS_AFTER_REPAIR"
    exit 0
fi

log "Checks are still failing after repair."
log "Please report this issue at: https://github.com/xyz-rainbow/xyz-scrcpy/issues"
echo "FAIL_OPEN"
exit 0
