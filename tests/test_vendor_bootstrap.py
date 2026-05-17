"""Unit tests for vendor_bootstrap (no network)."""

import os
import shutil
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
    def test_has_passwordless_sudo_false_without_sudo(self):
        with patch("shutil.which", return_value=None):
            self.assertFalse(vb._has_passwordless_sudo())

    def test_scrcpy_vendor_download_url_macos_intel(self):
        env = vb.EnvInfo("darwin", "x86_64", "brew", False)
        url = vb.scrcpy_vendor_download_url(env)
        self.assertIn("macos-x86_64", url or "")

    def test_scrcpy_vendor_download_url_macos_arm(self):
        env = vb.EnvInfo("darwin", "arm64", "brew", False)
        url = vb.scrcpy_vendor_download_url(env)
        self.assertIn("macos-aarch64", url or "")

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
            (vend / "scrcpy-server").write_bytes(b"")
            with (
                patch("adb_resolve.shutil.which", return_value=None),
                patch.object(vb, "_adb_vendor_usable", return_value=True),
                patch.object(vb, "_scrcpy_vendor_usable", return_value=True),
            ):
                adb_ok, scrcpy_ok = vb.verify_tools_resolved(root)
            self.assertTrue(adb_ok)
            self.assertTrue(scrcpy_ok)

    def test_scrcpy_vendor_usable_rejects_stub_binary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vend = vb.vendor_dir(root)
            vend.mkdir(parents=True)
            stub = vb.vendor_scrcpy_path(root)
            stub.write_bytes(b"not-scrcpy")
            _chmod = vb._chmod_executable
            _chmod(stub)
            (vend / "scrcpy-server").write_bytes(b"x")
            self.assertFalse(vb._scrcpy_vendor_usable(root))

    def test_extract_scrcpy_tar_replaces_broken_vendor_binary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vend = vb.vendor_dir(root)
            vend.mkdir(parents=True)
            stub = vb.vendor_scrcpy_path(root)
            stub.write_bytes(b"broken")
            (vend / "scrcpy-server").write_bytes(b"old")
            bundle = root / "bundle"
            bundle.mkdir()
            good_scrcpy = bundle / "scrcpy"
            good_scrcpy.write_bytes(b"#!/bin/sh\necho scrcpy 3.3.4\n")
            good_scrcpy.chmod(0o755)
            (bundle / "scrcpy-server").write_bytes(b"server")
            tar_path = root / "fake.tar.gz"
            tar_path.write_bytes(b"x")
            result = vb.ToolInstallResult()

            class FakeTar:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def extractall(self, dest, filter=None):
                    shutil.copytree(bundle, dest / "scrcpy-linux", dirs_exist_ok=True)

            with (
                patch("vendor_bootstrap.tarfile.open", return_value=FakeTar()),
                patch.object(vb, "_scrcpy_vendor_usable", side_effect=[False, True]),
            ):
                ok = vb._extract_scrcpy_tar(tar_path, vend, result)
            self.assertTrue(ok)
            self.assertTrue(vb.vendor_scrcpy_path(root).read_bytes().startswith(b"#!"))

    def test_stage_vendor_download_skips_scrcpy_on_unsupported_cpu(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = vb.EnvInfo("linux", "armv7l", "none", False)
            result = vb.ToolInstallResult()
            urls: list[str] = []

            def fake_download(url: str, dest: Path) -> bool:
                urls.append(url)
                return False

            with (
                patch.object(vb, "verify_tools_resolved", return_value=(False, False)),
                patch.object(vb, "_scrcpy_vendor_usable", return_value=False),
                patch.object(vb, "_adb_vendor_usable", return_value=False),
                patch.object(vb, "_download_file", side_effect=fake_download),
            ):
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
