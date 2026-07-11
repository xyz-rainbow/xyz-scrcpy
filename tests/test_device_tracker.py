"""Tests for bin/device_tracker.py."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

from device_tracker import DeviceTracker, connection_event_banner  # noqa: E402


class DeviceTrackerTests(unittest.TestCase):
    def test_debounce_disconnect_requires_two_misses(self):
        tracker = DeviceTracker()
        tracker.observe_adb_rows([("ABC", "device")])
        self.assertIn("ABC", tracker.stable_ready_serials())
        tracker.observe_adb_rows([])
        self.assertIn("ABC", tracker.stable_ready_serials())
        connected, disconnected = tracker.observe_adb_rows([])
        self.assertEqual(connected, [])
        self.assertEqual(disconnected, ["ABC"])

    def test_connection_banner_on_connect(self):
        banner = connection_event_banner(["XYZ"], [], lambda s: f"Phone ({s})")
        self.assertIsNotNone(banner)
        assert banner is not None
        self.assertEqual(banner["level"], "OK")
        self.assertIn("connected", banner["message"].lower())

    def test_logs_connection_events(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "device-events.log"
            tracker = DeviceTracker(log_path)
            tracker.observe_adb_rows([("S1", "device")])
            tracker.observe_adb_rows([])
            tracker.observe_adb_rows([])
            self.assertTrue(log_path.is_file())
            text = log_path.read_text(encoding="utf-8")
            self.assertIn("connected S1", text)
            self.assertIn("disconnected S1", text)


if __name__ == "__main__":
    unittest.main()
