"""resolve_python_for_checks with mocked subprocess / which."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))

import _paths  # noqa: E402, F401, I001

from xyz_scrcpy import win_path_shim as wps  # noqa: E402, I001

_MOD = "xyz_scrcpy.win_path_shim"


def _fake_run_for_py3_happy(pyexe: str):
    """py -3.10.. fail; py -3 returns executable; version + pip checks succeed."""

    def _fake(cmd, **kwargs):
        m = MagicMock()
        m.stderr = ""
        cs = " ".join(cmd)
        if "print(sys.executable)" in cs:
            if len(cmd) >= 2 and cmd[0] == "py" and cmd[1] == "-3":
                m.returncode = 0
                m.stdout = pyexe + "\n"
            else:
                m.returncode = 1
                m.stdout = ""
        elif "sys.version_info" in cs or "% sys.version" in cs:
            m.returncode = 0
            m.stdout = "3.12\n"
        elif "import pip" in cs:
            m.returncode = 0
            m.stdout = ""
        else:
            m.returncode = 1
            m.stdout = ""
        return m

    return _fake


def _fake_run_embeddable(pyexe: str):
    def _fake(cmd, **kwargs):
        m = MagicMock()
        m.stderr = ""
        cs = " ".join(cmd)
        if "print(sys.executable)" in cs:
            if len(cmd) >= 2 and cmd[0] == "py" and cmd[1] == "-3":
                m.returncode = 0
                m.stdout = pyexe + "\n"
            else:
                m.returncode = 1
                m.stdout = ""
        elif "sys.version_info" in cs or "% sys.version" in cs:
            m.returncode = 0
            m.stdout = "3.12\n"
        elif "import pip" in cs:
            m.returncode = 1
            m.stdout = ""
        else:
            m.returncode = 1
            m.stdout = ""
        return m

    return _fake


class PythonDetectorTests(unittest.TestCase):
    def test_no_candidates(self):
        with patch(f"{_MOD}.shutil.which", return_value=None):
            exe, err = wps.resolve_python_for_checks()
        self.assertIsNone(exe)
        self.assertIsNotNone(err)

    def test_py_launcher_happy_path(self):
        pyexe = r"C:\Python312\python.exe"

        def which(name):
            return "py" if name == "py" else None

        with (
            patch(f"{_MOD}.shutil.which", side_effect=which),
            patch(f"{_MOD}.subprocess.run", side_effect=_fake_run_for_py3_happy(pyexe)),
        ):
            exe, err = wps.resolve_python_for_checks()
        self.assertEqual(exe, pyexe)
        self.assertIsNone(err)

    def test_rejects_embeddable_without_pip(self):
        pyexe = r"C:\Emb\python.exe"

        def which(name):
            return "py" if name == "py" else None

        with (
            patch(f"{_MOD}.shutil.which", side_effect=which),
            patch(f"{_MOD}.subprocess.run", side_effect=_fake_run_embeddable(pyexe)),
        ):
            exe, err = wps.resolve_python_for_checks()
        self.assertIsNone(exe)
        self.assertIn("pip", (err or "").lower())


if __name__ == "__main__":
    unittest.main()
