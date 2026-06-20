"""Smoke tests for repo-root installer.sh (Linux/macOS dev menu)."""

import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER_SH = ROOT / "installer.sh"


def is_wsl_bash():
    bash = shutil.which("bash")
    if not bash:
        return False
    if os.name != "nt":
        return False
    try:
        # Check if it's WSL bash (will fail if no distro)
        proc = subprocess.run(
            ["bash", "-c", "true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(shutil.which("bash"), "bash not on PATH")
class InstallerShTests(unittest.TestCase):
    def test_installer_sh_passes_bash_n(self) -> None:
        if os.name == "nt" and not is_wsl_bash():
            # If on Windows and not WSL bash (e.g. Git Bash), check if it works
            # Git Bash usually works. If it's broken WSL, skip.
            try:
                subprocess.run(["bash", "--version"], capture_output=True, timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                self.skipTest("bash found but not executable (broken WSL?)")

        # Relative script name + cwd=ROOT avoids Windows drive / [] path issues for WSL vs Git Bash.
        proc = subprocess.run(
            ["bash", "-n", "installer.sh"],
            cwd=str(ROOT),
            capture_output=True,
            text=False,  # Read raw bytes to handle null bytes if any
            check=False,
        )
        # On some Windows CI environments, output might contain null bytes from WSL stub
        out = (proc.stdout or b"").replace(b"\x00", b"").decode("utf-8", "ignore")
        err = (proc.stderr or b"").replace(b"\x00", b"").decode("utf-8", "ignore")

        if proc.returncode != 0 and "Windows Subsystem for Linux has no installed distributions" in (err + out):
            self.skipTest("WSL bash found but no distributions installed")

        self.assertEqual(proc.returncode, 0, msg=err + out)

    def test_installer_sh_content_invariants(self) -> None:
        text = INSTALLER_SH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env bash\n"), msg="expected bash shebang")
        self.assertIn('REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"', text)
        self.assertIn("install_xyz.py", text)
        self.assertIn("--action", text)
        self.assertIn("curl -LsSf https://astral.sh/uv/install.sh", text)
        self.assertIn("Windows-only", text)
        self.assertNotIn("\u2014", text, msg="avoid Unicode em dash in menu text (ASCII policy)")
        self.assertIn("Confirm [Y/n]:", text)


if __name__ == "__main__":
    unittest.main()
