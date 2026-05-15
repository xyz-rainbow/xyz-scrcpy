#!/usr/bin/env python3
"""Terminal installer UI matching bin/menu.py (borders, colors, list navigation)."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT_DIR / "bin"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import install_xyz as ix  # noqa: E402
import menu as ui  # noqa: E402
import win_path_shim as wps  # noqa: E402


def _clear() -> None:
    if sys.platform == "win32":
        import os

        os.system("cls")
    else:
        import os

        os.system("clear")


def _tui_yes_no(title: str, *, default_yes: bool) -> bool:
    """Yes/No using same list widget as the main app; cursor starts on default."""
    opts = (["Yes", "No"] if default_yes else ["No", "Yes"])
    r = ui.show_simple_selection(title, opts)
    if r is None:
        return default_yes
    return opts[r] == "Yes"


def _tui_text_line(title: str, prompt: str, default: str) -> str:
    width = ui.terminal_width()
    border = "=" * width
    lines = [
        "",
        ui.center_line(f"{ui.RED}{border}{ui.RESET}", width),
        ui.center_line(f"{ui.MAGENTA}{title}{ui.RESET}", width),
        "",
        ui.center_line(prompt, width),
        "",
        ui.center_line(f"{ui.WHITE}Default: {default}{ui.RESET}", width),
        "",
    ]
    lines.extend(ui.render_brand_footer(width))
    _clear()
    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()
    try:
        raw = input(f"{ui.GREEN}>>> {ui.RESET}").strip()
    except EOFError:
        raw = ""
    return raw if raw else default


def _hub_options(os_name: str) -> list[str]:
    opts = ["Install", "Uninstall"]
    if os_name == "windows":
        opts.append("Diagnose (Windows)")
    opts.append("Exit")
    return opts


def main(verbose: bool = False) -> int:
    os_name = platform.system().lower()
    if os_name not in {"linux", "darwin", "windows"}:
        print(f"Unsupported OS: {os_name}")
        return 1

    src_root = ROOT_DIR
    paths = ix.detect_paths(os_name, Path.home())

    while True:
        opts = _hub_options(os_name)
        idx = ui.show_simple_selection("XYZ-scrcpy — installer", opts)
        if idx is None:
            return 0
        choice = opts[idx]
        if choice == "Exit":
            return 0

        if choice == "Diagnose (Windows)":
            inst = paths["install_dir"] if paths["install_dir"].exists() else None
            return wps.run_diagnose(inst, repo_root=src_root, clean_user_path=False)

        if choice == "Uninstall":
            if not _tui_yes_no("Confirm uninstall", default_yes=True):
                continue
            remove_files = _tui_yes_no("Delete installed app files?", default_yes=False)
            remove_repo = _tui_yes_no("Delete current repository copy?", default_yes=False)
            try:
                ix.do_uninstall(
                    paths,
                    os_name,
                    remove_app_files=remove_files,
                    remove_repo_copy=remove_repo,
                    repo_dir=src_root,
                    verbose=verbose,
                )
            except Exception as exc:  # pylint: disable=broad-except
                _show_error(str(exc))
                return 1
            _show_done("Uninstall finished.")
            continue

        # Install
        if not _tui_yes_no("Confirm install", default_yes=True):
            continue

        detected = ix.read_installed_alias(paths["install_dir"])
        alias_raw = _tui_text_line("Launcher alias", "Type alias or press Enter for:", detected)
        alias = ix.normalize_alias(alias_raw)

        enable_service = _tui_yes_no("Enable background monitor service?", default_yes=True)
        run_tests = _tui_yes_no("Run post-install checks and show log?", default_yes=True)

        try:
            ix.do_install(
                paths,
                src_root,
                os_name,
                alias,
                enable_service,
                run_tests,
                verbose=verbose,
            )
        except Exception as exc:  # pylint: disable=broad-except
            _show_error(str(exc))
            return 1
        return 0


def _show_error(message: str) -> None:
    width = ui.terminal_width()
    border = "=" * width
    lines = [
        "",
        ui.center_line(f"{ui.RED}{border}{ui.RESET}", width),
        ui.center_line(f"{ui.RED}ERROR{ui.RESET}", width),
        ui.center_line(ui.trunc_text(message, width - 4), width),
        "",
        ui.center_line("[ENTER] dismiss", width),
    ]
    lines.extend(ui.render_brand_footer(width))
    _clear()
    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()
    try:
        ui.get_key()
    except (KeyboardInterrupt, EOFError):
        pass


def _show_done(message: str) -> None:
    width = ui.terminal_width()
    border = "=" * width
    lines = [
        "",
        ui.center_line(f"{ui.GREEN}{border}{ui.RESET}", width),
        ui.center_line(f"{ui.GREEN}{message}{ui.RESET}", width),
        "",
        ui.center_line("[ENTER] return to hub", width),
    ]
    lines.extend(ui.render_brand_footer(width))
    _clear()
    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()
    try:
        ui.get_key()
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    v = "--verbose" in sys.argv
    raise SystemExit(main(verbose=v))
