import os
import sys
import unittest
from unittest.mock import patch, MagicMock

import types
menu = types.ModuleType("menu")
menu.termios = None
menu.tty = None
menu.os = os
sys.modules["menu"] = menu

def maybe_patch(condition, target):
    return patch(target) if condition else patch("menu.os.name")

termios_getattr_patch = maybe_patch(menu.termios, "menu.termios.tcgetattr")

@termios_getattr_patch
def test_func(mock_getattr):
    print(f"Inside test_func, mock_getattr: {mock_getattr}")

test_func()
