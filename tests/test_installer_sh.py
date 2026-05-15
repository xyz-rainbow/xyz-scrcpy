"""Smoke tests for repo-root installer.sh (Linux/macOS dev menu)."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER_SH = ROOT / "installer.sh"


@unittest.skipUnless(shutil.which("bash"), "bash not on PATH")
class InstallerShTests(unittest.TestCase):
    def test_installer_sh_passes_bash_n(self) -> None:
        # Relative script name + cwd=ROOT avoids Windows drive / [] path issues for WSL vs Git Bash.
        proc = subprocess.run(
            ["bash", "-n", "installer.sh"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=(proc.stderr or "") + (proc.stdout or ""))

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
