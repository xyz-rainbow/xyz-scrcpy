import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MONITOR = ROOT / "bin" / "monitor.py"
LAST_OPEN_EPOCH_FILE = Path(tempfile.gettempdir()) / "xyz_monitor_last_open.epoch"


def run_monitor_test(env_overrides):
    created_state: str | None = None
    if "MONITOR_STATE_DIR" not in env_overrides:
        created_state = tempfile.mkdtemp(prefix="xyz_mon_test_")
        state_dir = created_state
    else:
        state_dir = env_overrides["MONITOR_STATE_DIR"]
    env = dict(os.environ)
    env.update(
        {
            "MONITOR_TEST_MODE": "1",
            "MONITOR_RUN_ONCE": "1",
            "MONITOR_STATE_DIR": state_dir,
            "TEST_CURR_SERIALS": "ABC123",
            "TEST_PREV_SERIALS": "",
            "TEST_OPEN_COOLDOWN_SECONDS": "30",
            "TEST_AUTO_START": "true",
            "TEST_AUTO_DISCOVER": "true",
            "TEST_PAUSE_ACTIVE": "false",
            "TEST_PAUSE_WAIT_RECONNECT": "false",
            "TEST_PAUSE_SEEN_DISCONNECT": "false",
        }
    )
    env.update(env_overrides)
    env["MONITOR_STATE_DIR"] = state_dir
    try:
        return subprocess.run(
            [sys.executable, str(MONITOR)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        if created_state:
            shutil.rmtree(created_state, ignore_errors=True)


class MonitorBehaviorTests(unittest.TestCase):
    def setUp(self):
        try:
            LAST_OPEN_EPOCH_FILE.unlink()
        except FileNotFoundError:
            pass

    def tearDown(self):
        try:
            LAST_OPEN_EPOCH_FILE.unlink()
        except FileNotFoundError:
            pass

    def test_opens_terminal_when_idle(self):
        proc = run_monitor_test({})
        self.assertEqual(proc.returncode, 0)
        self.assertIn("OPEN_TERMINAL", proc.stdout)

    def test_does_not_open_when_monitor_already_open(self):
        proc = run_monitor_test({"MONITOR_HAS_WINDOW": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("OPEN_TERMINAL", proc.stdout)

    def test_does_not_open_when_scrcpy_running(self):
        proc = run_monitor_test({"MONITOR_HAS_SCRCPY": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("OPEN_TERMINAL", proc.stdout)

    def test_does_not_open_when_pause_active(self):
        proc = run_monitor_test({"TEST_PAUSE_ACTIVE": "true", "TEST_PAUSE_WAIT_RECONNECT": "false"})
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("OPEN_TERMINAL", proc.stdout)

    def test_pause_reconnect_resumes_when_auto_discover_on(self):
        proc = run_monitor_test(
            {
                "TEST_PAUSE_ACTIVE": "true",
                "TEST_PAUSE_WAIT_RECONNECT": "true",
                "TEST_PAUSE_SEEN_DISCONNECT": "true",
                "TEST_PREV_SERIALS": "ABC123",
                "TEST_CURR_SERIALS": "ABC123",
                "TEST_AUTO_DISCOVER": "true",
            }
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("OPEN_TERMINAL", proc.stdout)

    def test_pause_reconnect_does_not_resume_when_auto_discover_off(self):
        proc = run_monitor_test(
            {
                "TEST_PAUSE_ACTIVE": "true",
                "TEST_PAUSE_WAIT_RECONNECT": "true",
                "TEST_PAUSE_SEEN_DISCONNECT": "true",
                "TEST_PREV_SERIALS": "ABC123",
                "TEST_CURR_SERIALS": "ABC123",
                "TEST_AUTO_DISCOVER": "false",
            }
        )
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("OPEN_TERMINAL", proc.stdout)

    def test_reconnect_with_different_serial_resumes(self):
        proc = run_monitor_test(
            {
                "TEST_PAUSE_ACTIVE": "true",
                "TEST_PAUSE_WAIT_RECONNECT": "true",
                "TEST_PAUSE_SEEN_DISCONNECT": "false",
                "TEST_PREV_SERIALS": "OLD001",
                "TEST_CURR_SERIALS": "NEW999",
                "TEST_AUTO_DISCOVER": "true",
            }
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("OPEN_TERMINAL", proc.stdout)

    def test_does_not_open_when_cooldown_is_active(self):
        state = tempfile.mkdtemp(prefix="xyz_cool_")
        try:
            (Path(state) / "xyz_monitor_last_open.epoch").write_text(
                str(int(time.time())),
                encoding="utf-8",
            )
            proc = run_monitor_test(
                {
                    "MONITOR_STATE_DIR": state,
                    "TEST_OPEN_COOLDOWN_SECONDS": "30",
                }
            )
            self.assertEqual(proc.returncode, 0)
            self.assertNotIn("OPEN_TERMINAL", proc.stdout)
        finally:
            shutil.rmtree(state, ignore_errors=True)

    def test_open_with_zero_cooldown_even_after_recent_open(self):
        state = tempfile.mkdtemp(prefix="xyz_cool0_")
        try:
            (Path(state) / "xyz_monitor_last_open.epoch").write_text(
                str(int(time.time())),
                encoding="utf-8",
            )
            proc = run_monitor_test(
                {
                    "MONITOR_STATE_DIR": state,
                    "TEST_OPEN_COOLDOWN_SECONDS": "0",
                }
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("OPEN_TERMINAL", proc.stdout)
        finally:
            shutil.rmtree(state, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
