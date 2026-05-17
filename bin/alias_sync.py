"""Sync launcher alias across Linux, macOS, and Windows install layouts."""

from __future__ import annotations

import platform
import sys
from pathlib import Path


def _os_name() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "darwin"
    return "linux"


def sync_command_alias(alias: str, install_root: Path) -> tuple[bool, str]:
    """Update config, shell launchers, and Windows CLI shims for *alias*."""
    install_root = Path(install_root).resolve()
    if not install_root.is_dir():
        return False, f"Install directory not found: {install_root}"

    root_str = str(install_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    installer = install_root / "install_xyz.py"
    if not installer.is_file():
        repo_installer = install_root.parent / "install_xyz.py"
        if repo_installer.is_file() and (install_root / "bin" / "menu.py").is_file():
            if str(install_root.parent) not in sys.path:
                sys.path.insert(0, str(install_root.parent))
        else:
            return False, "install_xyz.py not found in install directory."

    try:
        import install_xyz as ix  # noqa: WPS433
    except ImportError as exc:
        return False, f"Could not load installer: {exc}"

    clean_alias = ix.normalize_alias(alias)
    os_name = _os_name()
    paths = ix.detect_paths(os_name, Path.home())
    paths["install_dir"] = install_root

    try:
        ix.do_sync_alias(paths, os_name, clean_alias)
        if os_name == "windows":
            import win_path_shim as wps  # noqa: WPS433

            path_log = install_root / "config" / "path_changes.log"
            path_log.parent.mkdir(parents=True, exist_ok=True)
            wps.windows_install_cli_shim(install_root, clean_alias, path_log=path_log)
    except OSError as exc:
        return False, str(exc)
    except Exception as exc:  # pylint: disable=broad-except
        return False, str(exc)

    return True, f"Launcher updated: run `{clean_alias}` in a new terminal."
