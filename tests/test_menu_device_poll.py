"""Tests for main-menu device polling and list_devices_for_menu."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import menu  # noqa: E402


class WaitMenuKeyTests(unittest.TestCase):
    @patch("menu.os.name", "posix")
    @patch("menu.sys.stdin")
    @patch("menu.termios.tcgetattr")
    @patch("menu.termios.tcsetattr")
    @patch("menu.tty.setraw")
    @patch("menu.select.select", return_value=([], [], []))
    def test_wait_menu_key_timeout_returns_none(
        self, _select, _setraw, _setattr, _getattr, mock_stdin
    ):
        mock_stdin.isatty.return_value = True
        mock_stdin.fileno.return_value = 0
        self.assertIsNone(menu.wait_menu_key(0.1))

    @patch("menu.os.name", "posix")
    @patch("menu.sys.stdin")
    @patch("menu.termios.tcgetattr")
    @patch("menu.termios.tcsetattr")
    @patch("menu.tty.setraw")
    @patch("menu.select.select", return_value=([0], [], []))
    @patch("menu.os.read", return_value=b"a")
    def test_wait_menu_key_reads_key_when_ready(
        self, _read, _select, _setraw, _setattr, _getattr, mock_stdin
    ):
        mock_stdin.isatty.return_value = True
        mock_stdin.fileno.return_value = 0
        self.assertEqual(menu.wait_menu_key(1.0), "a")

    @patch("menu.os.name", "posix")
    @patch("menu.sys.stdin")
    @patch("menu.termios.tcgetattr")
    @patch("menu.termios.tcsetattr")
    @patch("menu.tty.setraw")
    @patch("menu.select.select", return_value=([0], [], []))
    @patch("menu._read_key_raw_fd", return_value="\x1b[B")
    def test_wait_menu_key_reads_arrow_sequence(
        self, _read_key, _select, _setraw, _setattr, _getattr, mock_stdin
    ):
        mock_stdin.isatty.return_value = True
        mock_stdin.fileno.return_value = 0
        self.assertEqual(menu.wait_menu_key(1.0), "\x1b[B")


class ListDevicesForMenuTests(unittest.TestCase):
    def test_list_devices_for_menu_includes_offline(self):
        with (
            patch("menu.adb_is_available", return_value=True),
            patch("menu._adb_exe", return_value="/fake/adb"),
            patch("menu.adb_device_lines", return_value=[("ABC123", "offline")]),
            patch("menu._device_label_for_serial", return_value="Phone (ABC123) [offline]"),
        ):
            devices, _event = menu.list_devices_for_menu({})
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["serial"], "ABC123")

    def test_list_devices_for_menu_shows_last_serial_when_adb_empty(self):
        with (
            patch("menu.adb_is_available", return_value=True),
            patch("menu._adb_exe", return_value="/fake/adb"),
            patch("menu.adb_device_lines", return_value=[]),
            patch("menu.adb_serial_reachable", return_value=False),
            patch("menu._device_label_for_serial", return_value="141a98fa [last used]"),
        ):
            devices, _event = menu.list_devices_for_menu({"last_device_serial": "141a98fa"})
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["serial"], "141a98fa")

    def test_adb_devices_status_message_with_last_serial(self):
        with patch("menu.adb_is_available", return_value=True), patch(
            "menu.adb_device_lines", return_value=[]
        ):
            msg = menu.adb_devices_status_message({"last_device_serial": "141a98fa"})
        self.assertIn("141a98fa", msg)
        self.assertIn("not listed by adb", msg)

    def test_list_devices_for_menu_last_serial_reconnecting(self):
        with (
            patch("menu.adb_is_available", return_value=True),
            patch("menu._adb_exe", return_value="/fake/adb"),
            patch("menu.adb_device_lines", return_value=[]),
            patch("menu.adb_serial_reachable", return_value=True),
            patch("menu._device_label_for_serial", return_value="141a98fa [reconnecting]"),
        ):
            devices, _event = menu.list_devices_for_menu({"last_device_serial": "141a98fa"})
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["serial"], "141a98fa")

    def test_list_devices_for_menu_includes_unauthorized(self):
        with (
            patch("menu.adb_is_available", return_value=True),
            patch("menu._adb_exe", return_value="/fake/adb"),
            patch("menu.adb_device_lines", return_value=[("XYZ", "unauthorized")]),
            patch("menu._device_label_for_serial", return_value="Phone (XYZ) [unauthorized]"),
        ):
            devices, _event = menu.list_devices_for_menu({})
        self.assertEqual(len(devices), 1)
        self.assertIn("unauthorized", devices[0]["label"])

    def test_list_devices_for_menu_dedupes_serial(self):
        with (
            patch("menu.adb_is_available", return_value=True),
            patch("menu._adb_exe", return_value="/fake/adb"),
            patch(
                "menu.adb_device_lines",
                return_value=[("ABC123", "device"), ("ABC123", "offline")],
            ),
            patch(
                "menu._device_label_for_serial",
                side_effect=lambda _adb, serial, tag="": f"{serial}{'-' + tag if tag else ''}",
            ),
        ):
            devices, _event = menu.list_devices_for_menu({})
        self.assertEqual(len(devices), 1)


class MainMenuPollIntegrationTests(unittest.TestCase):
    @patch("menu.os.system")
    @patch("sys.stdout.write")
    @patch("menu.wait_menu_key", side_effect=[None, "\x1b"])
    @patch("menu.list_devices_for_menu")
    @patch("menu.load_config", return_value={})
    @patch("menu.adb_is_available", return_value=True)
    @patch("menu.adb_devices_status_message", return_value="")
    def test_main_polls_devices_on_timeout(
        self, _hint, _adb_ok, _load, mock_list, mock_wait, _write, _clear
    ):
        mock_list.side_effect = [
            ([], None),
            ([{"serial": "ABC123", "label": "Phone (ABC123)"}], None),
        ]
        with patch("menu.fcntl.flock"), patch("builtins.open", unittest.mock.mock_open()):
            menu.main()
        self.assertGreaterEqual(mock_list.call_count, 2)
        self.assertGreaterEqual(mock_wait.call_count, 2)
