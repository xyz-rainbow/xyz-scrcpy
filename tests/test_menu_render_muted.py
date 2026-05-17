"""Menu render and list_devices integration tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import menu  # noqa: E402
from device_tracker import DeviceTracker  # noqa: E402


class MenuMutedRenderTests(unittest.TestCase):
    def test_render_menu_muted_device_gray(self):
        lines = menu.render_menu(
            ["Phone (ABC) [disconnected]", "SETTINGS"],
            0,
            80,
            muted_indices=[0],
        )
        joined = "\n".join(lines)
        self.assertIn(menu.GRAY, joined)

    @patch("menu.adb_is_available", return_value=True)
    @patch("menu._adb_exe", return_value="/fake/adb")
    @patch("menu.adb_device_lines", return_value=[])
    @patch("menu.adb_serial_reachable", return_value=False)
    @patch("menu._cached_device_label", return_value="Phone (141a98fa) [disconnected]")
    def test_list_devices_preserves_last_serial_on_empty_adb(
        self, _label, _reach, _lines, _adb, _ok
    ):
        tracker = DeviceTracker()
        devices, _event = menu.list_devices_for_menu(
            {"last_device_serial": "141a98fa"}, tracker
        )
        tracker.observe_adb_rows([("141a98fa", "device")])
        devices2, _ = menu.list_devices_for_menu({"last_device_serial": "141a98fa"}, tracker)
        self.assertGreaterEqual(len(devices), 1)
        self.assertGreaterEqual(len(devices2), 1)


if __name__ == "__main__":
    unittest.main()
