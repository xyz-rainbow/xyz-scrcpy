import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(_ROOT), str(_ROOT / "lib")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import xyz_scrcpy.install_xyz as install_xyz  # noqa: E402
from xyz_scrcpy._paths import repo_root  # noqa: E402

_PKG = "xyz_scrcpy.install_xyz"


class InstallerTests(unittest.TestCase):
    def test_normalize_alias(self):
        self.assertEqual(install_xyz.normalize_alias("my alias!!"), "my-alias")
        self.assertEqual(install_xyz.normalize_alias(""), "xyz-scrcpy")

    def test_launcher_path_linux(self):
        launcher = install_xyz.launcher_path("linux", Path("/tmp/bin"), "abc")
        self.assertEqual(launcher, Path("/tmp/bin/abc"))

    def test_launcher_path_windows(self):
        launcher = install_xyz.launcher_path("windows", Path("C:/bin"), "abc")
        self.assertTrue(str(launcher).endswith("abc.cmd"))

    def test_prune_managed_launchers_removes_secondary_alias(self):
        with tempfile.TemporaryDirectory() as td:
            install_dir = Path(td) / "app"
            launcher_dir = Path(td) / "bin"
            install_dir.mkdir(parents=True)
            launcher_dir.mkdir(parents=True)
            (install_dir / "bin").mkdir()
            (install_dir / "bin" / "launch_with_checks.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            marker = str(install_dir / "bin" / "launch_with_checks.sh")
            keep = launcher_dir / "xyz-scrcpy"
            stale = launcher_dir / "xyz-android"
            keep.write_text(f"bash \"{marker}\"\n", encoding="utf-8")
            stale.write_text(f"bash \"{marker}\"\n", encoding="utf-8")
            install_xyz.prune_managed_launchers(launcher_dir, install_dir, "linux", "xyz-scrcpy")
            self.assertTrue(keep.exists())
            self.assertFalse(stale.exists())

    def test_linux_launcher_includes_vendor_in_path(self):
        with tempfile.TemporaryDirectory() as td:
            install_dir = Path(td) / "app"
            install_dir.mkdir(parents=True)
            (install_dir / "bin").mkdir()
            (install_dir / "bin" / "launch_with_checks.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            launcher = Path(td) / "bin" / "xyz-scrcpy"
            launcher.parent.mkdir()
            install_xyz.write_launcher("linux", launcher, install_dir)
            text = launcher.read_text(encoding="utf-8").replace("\\", "/")
            self.assertIn("/vendor", text)
            self.assertIn("export PATH=", text)

    def test_linux_service_unit_includes_vendor_path(self):
        with tempfile.TemporaryDirectory() as td:
            install_dir = Path(td) / "app"
            install_dir.mkdir(parents=True)
            (install_dir / "bin").mkdir()
            (install_dir / "bin" / "monitor.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            unit = install_xyz.linux_service_content(install_dir).replace("\\", "/")
            self.assertIn("Environment=PATH=", unit)
            self.assertIn("/vendor", unit)

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

            with redirect_stdout(StringIO()):
                install_xyz.do_sync_alias(paths, "linux", "new-alias")
            new_launcher = install_xyz.launcher_path("linux", launcher_dir, "new-alias")
            self.assertTrue(new_launcher.exists())
            self.assertFalse(old_launcher.exists())

    def test_do_install_always_runs_clean_uninstall_first(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = {
                "install_dir": root / "app",
                "launcher_dir": root / "bin",
                "service_file": root / "svc",
            }
            src = root / "src"
            src.mkdir()
            (src / "dummy.txt").write_text("x", encoding="utf-8")
            paths["launcher_dir"].mkdir(parents=True)

            with (
                patch(f"{_PKG}.do_uninstall") as mock_uninstall,
                patch(f"{_PKG}.copy_project") as mock_copy,
                patch(f"{_PKG}.check_dependencies"),
                patch(f"{_PKG}.install_service"),
                patch(f"{_PKG}.open_initial_menu"),
                patch(f"{_PKG}.read_installed_alias", return_value="xyz-scrcpy"),
                patch(f"{_PKG}.write_launcher"),
                patch(f"{_PKG}.save_alias_to_config"),
                patch(f"{_PKG}.ensure_windows_runtime_venv"),
                patch(f"{_PKG}.ensure_linux_runtime", return_value=install_xyz.RuntimeStatus("venv_ok")),
                patch(f"{_PKG}.vb.ensure_android_tools", return_value=install_xyz.vb.ToolInstallResult()),
            ):
                with redirect_stdout(StringIO()):
                    install_xyz.do_install(paths, src, "linux", "xyz-scrcpy", True, False)
                mock_uninstall.assert_called_once()
                mock_copy.assert_called_once()

    def test_ask_yes_no_defaults_and_values(self):
        with patch("builtins.input", return_value=""):
            self.assertTrue(install_xyz.ask_yes_no("Enable service", default_yes=True))
        with patch("builtins.input", return_value="n"):
            self.assertFalse(install_xyz.ask_yes_no("Enable service", default_yes=True))

    def test_uninstall_removes_managed_orphan_launchers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_dir = root / "app"
            launcher_dir = root / "bin"
            service_file = root / "svc"
            install_dir.mkdir(parents=True)
            launcher_dir.mkdir(parents=True)
            (install_dir / "bin").mkdir(parents=True)
            (install_dir / "bin" / "launch_with_checks.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (install_dir / "config").mkdir(parents=True)
            (install_dir / "config" / "config.json").write_text(
                json.dumps({"command_alias": "main-alias"}),
                encoding="utf-8",
            )

            managed_primary = launcher_dir / "main-alias"
            managed_orphan = launcher_dir / "old-alias"
            unmanaged = launcher_dir / "not-related"
            marker = str(install_dir / "bin" / "launch_with_checks.sh")
            managed_primary.write_text(f"bash \"{marker}\"\n", encoding="utf-8")
            managed_orphan.write_text(f"bash \"{marker}\"\n", encoding="utf-8")
            unmanaged.write_text("echo hello\n", encoding="utf-8")

            paths = {
                "install_dir": install_dir,
                "launcher_dir": launcher_dir,
                "service_file": service_file,
            }

            with patch(f"{_PKG}.stop_service"), patch(f"{_PKG}.uninstall_service"):
                with redirect_stdout(StringIO()):
                    install_xyz.do_uninstall(paths, "linux")

            self.assertFalse(install_dir.exists())
            self.assertFalse(managed_primary.exists())
            self.assertFalse(managed_orphan.exists())
            self.assertTrue(unmanaged.exists())

    def test_safe_delete_repo_copy_guarded(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "install_xyz.py").write_text("print('x')\n", encoding="utf-8")
            self.assertTrue(install_xyz._safe_delete_repo_copy(repo))
            self.assertFalse(repo.exists())

    def test_open_initial_menu_delegates_to_terminal_open(self):
        with tempfile.TemporaryDirectory() as td:
            install_dir = Path(td)
            (install_dir / "bin").mkdir(parents=True)
            (install_dir / "bin" / "launch_with_checks.py").write_text("# stub\n", encoding="utf-8")
            fake = install_xyz.TerminalOpenResult(ok=True, method="gnome-terminal", tried=["gnome-terminal"])
            with patch(f"{_PKG}.terminal_open.open_command_in_terminal", return_value=fake) as mock_open:
                result = install_xyz.open_initial_menu("linux", install_dir, prechecked_status="PASS")
            self.assertTrue(result.ok)
            mock_open.assert_called_once()
            call_kw = mock_open.call_args[1]
            self.assertEqual(call_kw["env"]["XYZ_CHECKS_STATUS"], "PASS")
            self.assertEqual(call_kw["env"]["XYZ_LAUNCHER_WINDOW"], "1")

    def test_project_scripts_use_portable_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = repo_root()
            dst = root / "installed-copy"
            install_xyz.copy_project(src, dst)

            monitor_text = (dst / "bin" / "monitor.sh").read_text(encoding="utf-8")
            repair_text = (dst / "launchers" / "unix" / "repair_xyz.sh").read_text(encoding="utf-8")
            syntax_text = (dst / "bin" / "test_syntax.py").read_text(encoding="utf-8")
            service_text = (dst / "systemd" / "scrcpy-auto.service").read_text(encoding="utf-8")
            installer_sh = (dst / "installer.sh").read_text(encoding="utf-8")
            unix_installer = (dst / "launchers" / "unix" / "installer.sh").read_text(encoding="utf-8")

            self.assertIn("monitor.py", monitor_text)
            self.assertIn("launchers/unix/installer.sh", installer_sh)
            self.assertIn("install_xyz.py", unix_installer)
            self.assertNotIn("\u2014", unix_installer)
            self.assertNotIn("/home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy", repair_text)
            self.assertNotIn("/home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy", syntax_text)
            self.assertIn("%h/.local/share/xyz-scrcpy/bin/monitor.sh", service_text)

            self.assertTrue((dst / "bin" / "menu.py").is_file())
            self.assertTrue((dst / "installer.sh").is_file())
            self.assertTrue((dst / "vendor").is_dir())
            self.assertFalse((dst / "mcps").exists())
            self.assertFalse((dst / ".github").exists())
            self.assertFalse((dst / "scripts" / "clean_dev.ps1").exists())
            self.assertTrue((dst / "lib" / "xyz_scrcpy" / "install_xyz.py").is_file())
            self.assertTrue((dst / "launchers" / "windows" / "installer.bat").is_file())


if __name__ == "__main__":
    unittest.main()