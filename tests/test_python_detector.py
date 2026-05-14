"""resolve_python_for_checks with mocked subprocess / which."""

import unittest
from unittest.mock import MagicMock, patch

import win_path_shim as wps


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
        with patch("win_path_shim.shutil.which", return_value=None):
            exe, err = wps.resolve_python_for_checks()
        self.assertIsNone(exe)
        self.assertIsNotNone(err)

    def test_py_launcher_happy_path(self):
        pyexe = r"C:\Python312\python.exe"

        def which(name):
            return "py" if name == "py" else None

        with (
            patch("win_path_shim.shutil.which", side_effect=which),
            patch("win_path_shim.subprocess.run", side_effect=_fake_run_for_py3_happy(pyexe)),
        ):
            exe, err = wps.resolve_python_for_checks()
        self.assertEqual(exe, pyexe)
        self.assertIsNone(err)

    def test_rejects_embeddable_without_pip(self):
        pyexe = r"C:\Emb\python.exe"

        def which(name):
            return "py" if name == "py" else None

        with (
            patch("win_path_shim.shutil.which", side_effect=which),
            patch("win_path_shim.subprocess.run", side_effect=_fake_run_embeddable(pyexe)),
        ):
            exe, err = wps.resolve_python_for_checks()
        self.assertIsNone(exe)
        self.assertIn("pip", (err or "").lower())


if __name__ == "__main__":
    unittest.main()
