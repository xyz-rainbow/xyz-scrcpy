"""Smoke: install TUI module loads and exposes a callable entrypoint."""

import importlib.util
import unittest
from pathlib import Path


class InstallTuiSmokeTests(unittest.TestCase):
    def test_install_tui_module_loads_main(self) -> None:
        root = Path(__file__).resolve().parent.parent
        path = root / "bin" / "install_tui.py"
        spec = importlib.util.spec_from_file_location("_xyz_install_tui_smoke", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        self.assertTrue(callable(getattr(mod, "main", None)))
        self.assertTrue(callable(getattr(mod, "_hub_options", None)))


if __name__ == "__main__":
    unittest.main()
