"""Tests for adb_resolve.resolve_adb_executable."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import adb_resolve  # noqa: E402


class AdbResolveTests(unittest.TestCase):
    def test_prefers_which_when_present(self):
        with patch("adb_resolve.shutil.which", return_value=r"C:\Sdk\platform-tools\adb.exe"):
            exe, src = adb_resolve.resolve_adb_executable(Path("/fake/repo"))
        self.assertEqual(exe, r"C:\Sdk\platform-tools\adb.exe")
        self.assertEqual(src, "PATH")

    def test_vendor_fallback_when_no_which(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            vendor = root / "vendor"
            vendor.mkdir(parents=True)
            name = "adb.exe" if os.name == "nt" else "adb"
            (vendor / name).write_bytes(b"")
            with patch("adb_resolve.shutil.which", return_value=None):
                exe, src = adb_resolve.resolve_adb_executable(root)
            self.assertTrue(str(exe).replace("\\", "/").endswith(f"vendor/{name}"))
            self.assertEqual(src, f"vendor/{name}")

    def test_xyz_android_platform_tools_override(self):
        with tempfile.TemporaryDirectory() as td:
            tools = Path(td) / "platform-tools"
            tools.mkdir(parents=True)
            name = "adb.exe" if os.name == "nt" else "adb"
            (tools / name).write_bytes(b"")
            root = Path(td) / "repo"
            root.mkdir()
            with (
                patch("adb_resolve.shutil.which", return_value=None),
                patch.dict(os.environ, {adb_resolve.ENV_PLATFORM_TOOLS: str(tools)}),
            ):
                exe, src = adb_resolve.resolve_adb_executable(root)
            # Use resolve() to handle Windows short/long path name discrepancies.
            self.assertEqual(Path(exe).resolve(), (tools / name).resolve())
            self.assertEqual(src, adb_resolve.ENV_PLATFORM_TOOLS)

    def test_not_found_returns_adb_token(self):
        with tempfile.TemporaryDirectory() as td:
            # We must NOT clear the entire environment on Windows, or Path.home() fails.
            # Instead, we just clear the specific variables adb_resolve looks for.
            to_clear = {
                "ANDROID_SDK_ROOT": "",
                "ANDROID_HOME": "",
                adb_resolve.ENV_PLATFORM_TOOLS: "",
                "LOCALAPPDATA": "",
            }
            with (
                patch("adb_resolve.shutil.which", return_value=None),
                patch.dict(os.environ, to_clear),
            ):
                exe, src = adb_resolve.resolve_adb_executable(Path(td))
        self.assertEqual(exe, "adb")
        self.assertEqual(src, "not_found")


if __name__ == "__main__":
    unittest.main()
