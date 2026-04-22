import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MONITOR = ROOT / "bin" / "monitor.sh"


def run_monitor_test(env_overrides):
    env = dict(os.environ)
    env.update(
        {
            "MONITOR_TEST_MODE": "1",
            "MONITOR_RUN_ONCE": "1",
            "TEST_DEVICE_SERIAL": "ABC123",
            "TEST_DEVICE_COUNT": "1",
            "TEST_AUTO_START": "true",
            "TEST_PAUSE_ACTIVE": "false",
        }
    )
    env.update(env_overrides)
    proc = subprocess.run(
        ["bash", str(MONITOR)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc


class MonitorBehaviorTests(unittest.TestCase):
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
        proc = run_monitor_test({"TEST_PAUSE_ACTIVE": "true"})
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("OPEN_TERMINAL", proc.stdout)


if __name__ == "__main__":
    unittest.main()
