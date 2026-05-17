"""launch_scrcpy / launch_scrcpy_result behavior."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


def _load_menu():
    path = ROOT / "bin" / "menu.py"
    spec = importlib.util.spec_from_file_location("xyz_menu_launch", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class MenuScrcpyLaunchTests(unittest.TestCase):
    def test_launch_scrcpy_returns_false_when_unavailable(self):
        menu = _load_menu()
        with patch.object(menu, "scrcpy_is_available", return_value=False):
            ok, err = menu.launch_scrcpy_result("serial", {})
        self.assertFalse(ok)
        self.assertIn("scrcpy", err)

    def test_launch_scrcpy_false_when_serial_not_ready(self):
        menu = _load_menu()
        with (
            patch.object(menu, "scrcpy_is_available", return_value=True),
            patch.object(menu, "adb_is_available", return_value=True),
            patch.object(menu, "adb_wait_for_device", return_value=False),
        ):
            ok, err = menu.launch_scrcpy_result("ABC123", {})
        self.assertFalse(ok)
        self.assertIn("ABC123", err)

    def test_launch_scrcpy_false_when_process_exits_immediately(self):
        menu = _load_menu()
        proc = MagicMock()
        proc.poll.return_value = 1
        with (
            patch.object(menu, "scrcpy_is_available", return_value=True),
            patch.object(menu, "adb_is_available", return_value=True),
            patch.object(menu, "adb_wait_for_device", return_value=True),
            patch.object(menu, "resolve_scrcpy_binary", return_value="/fake/scrcpy"),
            patch.object(menu, "normalize_audio_preferences", side_effect=lambda c: c),
            patch.object(menu, "ensure_microphone_bus"),
            patch.object(menu, "scrcpy_supports_microphone", return_value=False),
            patch("time.sleep"),
            patch("subprocess.Popen", return_value=proc),
            patch.object(menu, "_read_scrcpy_log_tail", return_value="ERROR: device offline"),
        ):
            ok, err = menu.launch_scrcpy_result("ABC123", {"audio_target": "host"})
        self.assertFalse(ok)
        self.assertIn("device offline", err)

    def test_launch_scrcpy_catches_popen_oserror(self):
        menu = _load_menu()
        with (
            patch.object(menu, "scrcpy_is_available", return_value=True),
            patch.object(menu, "adb_is_available", return_value=True),
            patch.object(menu, "adb_wait_for_device", return_value=True),
            patch.object(menu, "resolve_scrcpy_binary", return_value="/fake/scrcpy"),
            patch.object(menu, "normalize_audio_preferences", side_effect=lambda c: c),
            patch.object(menu, "ensure_microphone_bus"),
            patch("subprocess.Popen", side_effect=OSError("ENOENT")),
        ):
            self.assertFalse(menu.launch_scrcpy("serial", {}))


class SyncAliasLauncherTests(unittest.TestCase):
    def test_sync_alias_launcher_returns_error_on_failure(self):
        sys.path.insert(0, str(ROOT / "bin"))
        import menu  # noqa: E402

        with patch(
            "menu.alias_sync.sync_command_alias",
            return_value=(False, "sync failed"),
        ):
            ok, err = menu.sync_alias_launcher("xyz-scrcpy")
        self.assertFalse(ok)
        self.assertIn("sync failed", err)


if __name__ == "__main__":
    unittest.main()
