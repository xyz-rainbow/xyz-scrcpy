"""Canonical exclude lists for install copy, release archives, and Inno Setup."""

from __future__ import annotations

# Directories and dev trees — never ship in install dir or release artifacts.
DEV_DIR_NAMES: tuple[str, ...] = (
    ".git",
    ".github",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cursor",
    ".claude",
    "agent-transcripts",
    "mcps",
    "scripts",
    "docs/internal",
)

# File globs for shutil.ignore_patterns (copy_project).
DEV_FILE_PATTERNS: tuple[str, ...] = (
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "config/*.log",
    "config/*.json",
)

# rsync --exclude paths (release.yml). Trailing slash = directory only.
RSYNC_EXCLUDES: tuple[str, ...] = (
    ".git",
    ".github",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cursor",
    ".claude",
    "agent-transcripts",
    "mcps",
    "scripts",
    "docs/internal",
    "stage-linux",
    "stage-win",
    "config/*.log",
    "config/*.json",
)

# Inno Setup [Files] Excludes (comma-separated, backslash paths).
INNO_EXCLUDES: str = (
    r"\.git\*,\.github\*,\.venv\*,\dist\*,\build\*,__pycache__\*,*.pyc,"
    r"\.cursor\*,\.claude\*,\.pytest_cache\*,\.mypy_cache\*,\.ruff_cache\*,"
    r"agent-transcripts\*,mcps\*,scripts\*,docs\internal\*,"
    r"packaging\windows\app.ico,config\*.log,config\*.json"
)


def shutil_ignore_patterns() -> tuple[str, ...]:
    """Arguments for shutil.ignore_patterns used by copy_project."""
    return DEV_DIR_NAMES + DEV_FILE_PATTERNS