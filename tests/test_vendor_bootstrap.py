"""Unit tests for vendor_bootstrap (no network)."""

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import vendor_bootstrap as vb  # noqa: E402


class VendorBootstrapTests(unittest.TestCase):
    def test_detect_environment_linux_apt(self):
        def which(name):
            if name == "apt-get":
                return "/usr/bin/apt-get"
            return None

        with patch("shutil.which", side_effect=which):
            env = vb.detect_environment()
        self.assertEqual(env.package_manager, "apt")

    def test_verify_tools_resolved_vendor_adb(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vend = root / "vendor"
            vend.mkdir()
            name = "adb.exe" if os.name == "nt" else "adb"
            adb = vend / name
            adb.write_bytes(b"")
            adb.chmod(adb.stat().st_mode | 0o111)
            scrcpy = vend / ("scrcpy.exe" if os.name == "nt" else "scrcpy")
            scrcpy.write_bytes(b"")
            scrcpy.chmod(scrcpy.stat().st_mode | 0o111)
            with patch("adb_resolve.shutil.which", return_value=None):
                adb_ok, scrcpy_ok = vb.verify_tools_resolved(root)
            self.assertTrue(adb_ok)
            self.assertTrue(scrcpy_ok)

    def test_stage_vendor_download_skips_scrcpy_on_unsupported_cpu(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = vb.EnvInfo("linux", "armv7l", "none", False)
            result = vb.ToolInstallResult()
            urls: list[str] = []

            def fake_download(url: str, dest: Path) -> bool:
                urls.append(url)
                return False

            with patch.object(vb, "_download_file", side_effect=fake_download):
                vb.stage_vendor_download(root, env, result)
            self.assertTrue(any("unsupported CPU" in a for a in result.attempts))
            self.assertFalse(any("scrcpy-linux" in u for u in urls))

    def test_corrupt_zip_logs_warn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad = root / "bad.zip"
            bad.write_bytes(b"not a zip")
            result = vb.ToolInstallResult()
            ok = vb._extract_platform_tools_zip(bad, vb.vendor_dir(root), result)
            self.assertFalse(ok)
            self.assertTrue(any("WARN" in line for line in result.attempts))

    def test_ensure_android_tools_skip_download_runs_manual_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir(parents=True)
            with (
                patch.object(vb, "stage_package_managers"),
                patch.object(vb, "print_manual_recovery") as mock_manual,
                patch("adb_resolve.shutil.which", return_value=None),
            ):
                result = vb.ensure_android_tools(root, "linux", skip_vendor_download=True)
            mock_manual.assert_called_once()
            self.assertFalse(result.adb_ok)
            self.assertIn("skipped", " ".join(result.attempts).lower())

    def test_zip_extract_platform_tools_minimal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zpath = root / "pt.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("platform-tools/adb", b"#!/bin/sh\necho adb\n")
            result = vb.ToolInstallResult()
            self.assertTrue(vb._extract_platform_tools_zip(zpath, vb.vendor_dir(root), result))
            self.assertTrue(vb.vendor_adb_path(root).is_file())


if __name__ == "__main__":
    unittest.main()
