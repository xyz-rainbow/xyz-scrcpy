"""Tests for CLI shim .cmd generation."""

import tempfile
import unittest
from pathlib import Path

import win_path_shim as wps


class ShimCmdTests(unittest.TestCase):
    def test_utf8_no_bom_crlf_and_quotes(self):
        with tempfile.TemporaryDirectory() as td:
            inst = Path(td) / "app"
            (inst / ".venv" / "Scripts").mkdir(parents=True)
            (inst / "bin").mkdir(parents=True)
            (inst / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
            (inst / "bin" / "launch_with_checks.py").write_text("# shim target\n", encoding="utf-8")

            out = Path(td) / "cli" / "xyz-scrcpy.cmd"
            wps.write_cli_shim_cmd(out, inst)

            raw = out.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", raw)
            self.assertNotIn(b"\n\n", raw.split(b"\r\n")[0])
            text = raw.decode("utf-8")
            self.assertIn("@echo off", text)
            self.assertIn('set "PATH=', text)
            self.assertIn("%PATH%", text)
            self.assertIn("vendor;", text)
            self.assertIn('"', text)


if __name__ == "__main__":
    unittest.main()
