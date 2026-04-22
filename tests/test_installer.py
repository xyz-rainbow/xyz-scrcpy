import json
import tempfile
import unittest
from pathlib import Path

import install_xyz


class InstallerTests(unittest.TestCase):
    def test_normalize_alias(self):
        self.assertEqual(install_xyz.normalize_alias("my alias!!"), "my-alias")
        self.assertEqual(install_xyz.normalize_alias(""), "xyz-scrcpy")

    def test_launcher_path_linux(self):
        launcher = install_xyz.launcher_path("linux", Path("/tmp/bin"), "abc")
        self.assertEqual(str(launcher), "/tmp/bin/abc")

    def test_launcher_path_windows(self):
        launcher = install_xyz.launcher_path("windows", Path("C:/bin"), "abc")
        self.assertTrue(str(launcher).endswith("abc.cmd"))

    def test_alias_saved_and_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            install_dir = Path(td)
            install_xyz.save_alias_to_config(install_dir, "my custom alias")
            alias = install_xyz.read_installed_alias(install_dir)
            self.assertEqual(alias, "my-custom-alias")

    def test_sync_alias_replaces_old_launcher(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_dir = root / "app"
            launcher_dir = root / "bin"
            install_dir.mkdir(parents=True)
            launcher_dir.mkdir(parents=True)
            (install_dir / "bin").mkdir()
            (install_dir / "bin" / "menu.py").write_text("print('ok')\n", encoding="utf-8")

            paths = {
                "install_dir": install_dir,
                "launcher_dir": launcher_dir,
                "service_file": root / "dummy.service",
            }

            install_xyz.save_alias_to_config(install_dir, "old-alias")
            old_launcher = install_xyz.launcher_path("linux", launcher_dir, "old-alias")
            install_xyz.write_launcher("linux", old_launcher, install_dir)
            self.assertTrue(old_launcher.exists())

            install_xyz.do_sync_alias(paths, "linux", "new-alias")
            new_launcher = install_xyz.launcher_path("linux", launcher_dir, "new-alias")
            self.assertTrue(new_launcher.exists())
            self.assertFalse(old_launcher.exists())


if __name__ == "__main__":
    unittest.main()
