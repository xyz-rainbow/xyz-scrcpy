"""menu.py must not crash when adb is missing."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def _load_menu():
    path = ROOT / "bin" / "menu.py"
    spec = importlib.util.spec_from_file_location("xyz_menu", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["xyz_menu_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class MenuAdbMissingTests(unittest.TestCase):
    def test_list_devices_empty_when_adb_not_found(self):
        menu = _load_menu()
        with patch.object(menu, "adb_is_available", return_value=False):
            self.assertEqual(menu.list_devices(), [])

    def test_list_devices_handles_file_not_found(self):
        menu = _load_menu()
        with (
            patch.object(menu, "adb_is_available", return_value=True),
            patch.object(menu, "_adb_exe", return_value="adb"),
            patch("subprocess.check_output", side_effect=FileNotFoundError("adb")),
        ):
            self.assertEqual(menu.list_devices(), [])


if __name__ == "__main__":
    unittest.main()
