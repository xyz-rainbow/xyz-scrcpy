#!/usr/bin/env python3
"""Automated checks and optional repair (portable; replaces bash-only pipeline on Windows)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_DIR / "bin"
LOG_FILE = Path(os.environ.get("XYZ_CHECK_LOG_FILE", REPO_DIR / "config" / "check.log"))
TIMEOUT = int(os.environ.get("XYZ_CHECK_TIMEOUT_SECONDS", "90"))
CHECK_MODE = os.environ.get("XYZ_CHECK_MODE", "full")
HOME_DIR = str(Path.home())
CHECK_START_EPOCH = 0


def sanitize(msg: str) -> str:
    out = msg.replace(HOME_DIR, "~").replace(str(REPO_DIR), ".")
    return out


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {sanitize(msg)}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def detect_os_info() -> None:
    log(f"System info: platform={platform.platform()}; python={sys.version.split()[0]}")


def append_sanitized_output(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(sanitize(line) + "\n")


def run_step(argv: list[str]) -> bool:
    import tempfile

    fd, tmp_path = tempfile.mkstemp(prefix="xyz_chk_", suffix=".txt", text=True)
    os.close(fd)
    tmp = Path(tmp_path)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(REPO_DIR),
            timeout=TIMEOUT,
            capture_output=True,
            text=True,
            check=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        tmp.write_text(combined, encoding="utf-8", errors="ignore")
        append_sanitized_output(tmp)
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"Step timeout: {' '.join(argv)}")
        return False
    except OSError as exc:
        log(f"Step failed: {exc}")
        return False
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def run_shell_script(script: Path) -> bool:
    if not script.is_file():
        return False
    bash = shutil.which("bash")
    if not bash:
        log(f"Skip bash script (no bash): {script.name}")
        return True
    return run_step([bash, str(script)])


def run_checks() -> bool:
    global CHECK_START_EPOCH
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")
    CHECK_START_EPOCH = int(time.time())
    log(f"Starting automated checks (mode: {CHECK_MODE}).")
    detect_os_info()

    if os.environ.get("XYZ_TEST_MODE") == "1":
        scenario = os.environ.get("XYZ_TEST_SCENARIO", "pass")
        if scenario == "pass":
            log("Test mode: checks passed.")
            return True
        if scenario == "fail":
            log("Test mode: checks failed.")
            return False
        if scenario == "repair-pass":
            if os.environ.get("XYZ_TEST_REPAIR_DONE") == "1":
                log("Test mode: checks passed after repair.")
                return True
            log("Test mode: initial checks failed.")
            return False

    py = sys.executable or shutil.which("python3") or shutil.which("python") or "python3"
    files = [
        REPO_DIR / "install_xyz.py",
        BIN_DIR / "menu.py",
        BIN_DIR / "config_loader.py",
        BIN_DIR / "monitor.py",
        BIN_DIR / "check_and_repair.py",
        BIN_DIR / "launch_with_checks.py",
    ]
    for f in files:
        if f.is_file() and not run_step([py, "-m", "py_compile", str(f)]):
            return False

    if shutil.which("bash"):
        for sh in ("monitor.sh", "check_and_repair.sh", "launch_with_checks.sh"):
            p = BIN_DIR / sh
            if p.is_file() and not run_step(["bash", "-n", str(p)]):
                return False

    if CHECK_MODE == "full":
        if not run_step([py, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]):
            return False

    end = int(time.time())
    log(f"Timing: start_epoch={CHECK_START_EPOCH}; end_epoch={end}; elapsed_seconds={end - CHECK_START_EPOCH}")
    log("All automated checks passed.")
    return True


def run_repair() -> None:
    repair_start = int(time.time())
    log("Checks failed, running repair workflow.")
    log("Auto-repair: started.")
    if os.environ.get("XYZ_TEST_MODE") == "1":
        os.environ["XYZ_TEST_REPAIR_DONE"] = "1"
        log("Test mode: simulated repair completed.")
        repair_end = int(time.time())
        log(
            "Auto-repair timing: "
            f"start_epoch={repair_start}; end_epoch={repair_end}; "
            f"elapsed_seconds={repair_end - repair_start}"
        )
        return

    repair_script = REPO_DIR / "repair_xyz.py"
    if repair_script.is_file():
        py = sys.executable or "python3"
        proc = subprocess.run(
            [py, str(repair_script)],
            cwd=str(REPO_DIR),
            timeout=TIMEOUT,
            text=True,
            capture_output=True,
            check=False,
        )
        code = proc.returncode
    else:
        bash = shutil.which("bash")
        sh = REPO_DIR / "repair_xyz.sh"
        if bash and sh.is_file():
            proc = subprocess.run(
                [bash, str(sh)],
                cwd=str(REPO_DIR),
                timeout=TIMEOUT,
                text=True,
                capture_output=True,
                check=False,
            )
            code = proc.returncode
        else:
            log("No repair script available.")
            code = 1
    repair_end = int(time.time())
    log("Auto-repair: finished.")
    log(f"Auto-repair result: exit_code={code}")
    log(
        "Auto-repair timing: "
        f"start_epoch={repair_start}; end_epoch={repair_end}; "
        f"elapsed_seconds={repair_end - repair_start}"
    )
    if code != 0:
        log(
            "Auto-repair warning: workflow reported non-zero exit code, "
            "continuing with re-check by contract."
        )


def main() -> int:
    os.chdir(REPO_DIR)
    if run_checks():
        print("PASS")
        return 0
    run_repair()
    log("Post-repair: re-running checks.")
    if run_checks():
        print("PASS_AFTER_REPAIR")
        return 0
    log("Checks are still failing after repair.")
    if CHECK_START_EPOCH > 0:
        fail_end = int(time.time())
        log(
            "Timing: "
            f"start_epoch={CHECK_START_EPOCH}; end_epoch={fail_end}; "
            f"elapsed_seconds={fail_end - CHECK_START_EPOCH}"
        )
    log("Please report this issue at: https://github.com/xyz-rainbow/xyz-scrcpy/issues")
    log(
        "GitHub issue creation requires login; you can also email check.log to "
        "rainbow@rainbowtechnology.xyz"
    )
    print("FAIL_OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
