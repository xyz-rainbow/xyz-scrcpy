import unittest
from pathlib import Path
from unittest.mock import patch

import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import config_loader  # noqa: E402
import menu  # noqa: E402


class DeviceMenuHelpersTests(unittest.TestCase):
    def test_is_installable_file(self):
        self.assertTrue(menu.is_installable_file("/tmp/demo.apk"))
        self.assertFalse(menu.is_installable_file("/tmp/demo.txt"))
        self.assertFalse(menu.is_installable_file("/tmp/demo.apkm"))

    def test_parse_pm_path_output(self):
        raw = "package:/data/app/demo/base.apk\npackage:/data/app/demo/split_config.en.apk\n"
        parsed = menu.parse_pm_path_output(raw)
        self.assertEqual(
            parsed,
            [
                "/data/app/demo/base.apk",
                "/data/app/demo/split_config.en.apk",
            ],
        )

    def test_visible_page_size_respects_terminal_height(self):
        with patch("menu.terminal_rows", return_value=24):
            self.assertEqual(menu.visible_page_size(12), 12)
        with patch("menu.terminal_rows", return_value=15):
            self.assertEqual(menu.visible_page_size(12), 8)

    def test_paginated_window_centers_selection(self):
        start, end = menu.paginated_window(20, 10, page_size=8)
        self.assertEqual(start, 6)
        self.assertEqual(end, 14)

    def test_render_tui_header_includes_key_hint_and_title(self):
        lines = menu.render_tui_header("MY TITLE", 80)
        joined = "\n".join(lines)
        self.assertIn("[SPACE] [ENTER] [ESC]", joined)
        self.assertIn("MY TITLE", joined)

    @patch("menu.os.system")
    @patch("sys.stdout.write")
    @patch("menu.get_key", return_value="\x1b")
    @patch("menu.terminal_rows", return_value=24)
    def test_settings_screen_uses_apk_style_header_and_pagination(
        self, _rows, _key, mock_write, _clear
    ):
        cfg = config_loader._normalize_config({})
        returned_cfg, action = menu.settings_screen(cfg)
        self.assertEqual(action, "cancel")
        self.assertEqual(returned_cfg, cfg)
        rendered = "".join(
            call.args[0] if call.args else call.kwargs.get("s", "")
            for call in mock_write.call_args_list
        )
        self.assertIn("[SPACE] [ENTER] [ESC]", rendered)
        self.assertIn("SETTINGS - HYBRID EDIT", rendered)
        self.assertIn("...", rendered)
        self.assertIn("[Launch behavior]", rendered)

    @patch("menu.os.system")
    @patch("menu.get_key", return_value="\x1b")
    def test_show_paginated_selection_esc_returns_none(self, _key, _clear):
        result = menu.show_paginated_selection(
            "TEST",
            [f"item-{i}" for i in range(15)],
            page_size=10,
        )
        self.assertIsNone(result)

    @patch("menu.os.system")
    @patch("menu.get_key")
    @patch("sys.stdout.write")
    def test_show_paginated_selection_renders_ellipsis_and_red_selected(self, mock_write, mock_key, _clear):
        mock_key.side_effect = ["\x1b[B", "\r"]
        result = menu.show_paginated_selection(
            "TEST",
            [f"item-{i}" for i in range(15)],
            page_size=10,
            highlight_selection_red=True,
        )
        self.assertEqual(result, 1)
        rendered = "".join(
            call.args[0] if call.args else call.kwargs.get("s", "")
            for call in mock_write.call_args_list
        )
        self.assertIn("...", rendered)
        self.assertIn(menu.RED, rendered)
        self.assertIn("[SPACE] [ENTER] [ESC]", rendered)

    @patch("menu.adb_is_available", return_value=True)
    @patch("menu.run_command")
    def test_adb_export_apk_to_dir(self, mock_run, _adb_ok):
        mock_run.side_effect = [
            (True, "package:/data/app/demo/base.apk", "", 0),
            (True, "", "", 0),
        ]
        ok, exported, err = menu.adb_export_apk_to_dir("ABC123", "com.demo.app", Path("/tmp/xyz"))
        self.assertTrue(ok)
        self.assertEqual(len(exported), 1)
        self.assertEqual(err, "")

    @patch("menu.prompt_text_input", return_value="/tmp/demo.apk")
    @patch("menu.show_simple_selection", return_value=1)
    def test_hybrid_picker_manual_mode(self, _select_mode, _prompt):
        path, banner = menu.pick_path_with_hybrid_selector("APK file path", "PICKER", ask_directory=False)
        self.assertIsNone(banner)
        self.assertEqual(path, Path("/tmp/demo.apk"))

    @patch("menu.pick_path_with_gui", return_value=None)
    @patch("menu.show_simple_selection", return_value=0)
    def test_hybrid_picker_gui_unavailable(self, _select_mode, _gui):
        path, banner = menu.pick_path_with_hybrid_selector("APK file path", "PICKER", ask_directory=False)
        self.assertIsNone(path)
        self.assertEqual(banner["level"], "WARN")

    @patch("menu.os.system")
    @patch("menu.sys.stdout.write")
    @patch("menu.get_key")
    @patch("menu.load_config", return_value={"saved": True})
    @patch("menu.save_config")
    @patch("menu.launch_scrcpy")
    def test_device_submenu_screen_share(self, _launch, _save, _load, mock_get_key, _stdout_write, _os_system):
        cfg = {
            "audio_target": "host",
            "active_recall": False,
            "microphone_bus": False,
            "applied_audio_target": "host",
            "applied_active_recall": False,
            "applied_microphone_bus": False,
            "last_device_serial": "",
        }
        mock_get_key.side_effect = ["\r", "\x1b"]
        updated_cfg, banner = menu.device_submenu({"serial": "ABC123", "label": "Phone (ABC123)"}, cfg, banner=None)
        self.assertEqual(updated_cfg, {"saved": True})
        self.assertIsNone(banner)

    def test_list_devices_keeps_serial_when_getprop_fails(self):
        with (
            patch("menu.adb_is_available", return_value=True),
            patch("menu._adb_exe", return_value="/fake/adb"),
            patch("menu.adb_device_lines", return_value=[("ABC123", "device")]),
            patch("menu.subprocess.check_output", side_effect=OSError("timeout")),
        ):
            devices = menu.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["serial"], "ABC123")
        self.assertEqual(devices[0]["label"], "ABC123")

    def test_main_menu_index_for_serial(self):
        devices = [{"serial": "A", "label": "Phone (A)"}, {"serial": "B", "label": "Tab (B)"}]
        self.assertEqual(menu.main_menu_index_for_serial(devices, "B"), 1)
        self.assertIsNone(menu.main_menu_index_for_serial(devices, "Z"))

    @patch("menu.adb_list_packages", return_value=(["pkg.a", "pkg.b"], None))
    @patch("menu.show_paginated_selection", return_value=0)
    def test_select_package_uses_red_highlight_for_uninstall(self, mock_paginated, _packages):
        package, banner = menu.select_package_from_device("ABC123", banner=None, for_uninstall=True)
        self.assertEqual(package, "pkg.a")
        self.assertIsNone(banner)
        self.assertTrue(mock_paginated.call_args.kwargs["highlight_selection_red"])


if __name__ == "__main__":
    unittest.main()
