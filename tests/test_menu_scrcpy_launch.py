"""launch_scrcpy must not raise when scrcpy is missing."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
            self.assertFalse(menu.launch_scrcpy("serial", {}))

    def test_launch_scrcpy_catches_popen_oserror(self):
        menu = _load_menu()
        with (
            patch.object(menu, "scrcpy_is_available", return_value=True),
            patch.object(menu, "resolve_scrcpy_binary", return_value="/fake/scrcpy"),
            patch.object(menu, "normalize_audio_preferences", side_effect=lambda c: c),
            patch.object(menu, "ensure_microphone_bus"),
            patch("subprocess.Popen", side_effect=OSError("ENOENT")),
        ):
            self.assertFalse(menu.launch_scrcpy("serial", {}))


if __name__ == "__main__":
    unittest.main()
