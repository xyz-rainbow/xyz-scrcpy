"""Resolve the Android Debug Bridge (adb) executable for this project (Windows-first fallbacks).

Resolution order (first match wins):
1. ``shutil.which("adb")`` (system PATH).
2. ``<repo>/vendor/adb.exe`` (Windows) or ``<repo>/vendor/adb`` (POSIX) when present.
3. Directory from ``XYZ_ANDROID_PLATFORM_TOOLS`` (must point at a folder containing ``adb`` / ``adb.exe``).
4. ``%ANDROID_SDK_ROOT%/platform-tools`` or ``%ANDROID_HOME%/platform-tools``.
5. On Windows only: default Android SDK layout under ``%LOCALAPPDATA%\\Android\\Sdk\\platform-tools``
   (or ``%USERPROFILE%\\AppData\\Local\\Android\\Sdk\\platform-tools`` when ``LOCALAPPDATA`` is unset).

Set ``XYZ_ANDROID_PLATFORM_TOOLS`` if you keep SDK tools outside those locations (for example a
``platform-tools`` folder whose path contains special characters).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ENV_PLATFORM_TOOLS = "XYZ_ANDROID_PLATFORM_TOOLS"


def _vendor_adb(repo_root: Path) -> Path:
    return repo_root / "vendor" / ("adb.exe" if os.name == "nt" else "adb")


def _prepend_vendor_to_path(repo_root: Path) -> None:
    """Prefer bundled adb when repo_root/vendor exists."""
    vend = repo_root / "vendor"
    if not vend.is_dir():
        return
    prefix = str(vend.resolve())
    path = os.environ.get("PATH", "")
    if prefix not in path.split(os.pathsep):
        os.environ["PATH"] = prefix + os.pathsep + path


def _platform_tools_candidates(repo_root: Path) -> list[tuple[Path, str]]:
    """Return (path_to_adb_binary, source_label) candidates in priority order (excluding PATH)."""
    out: list[tuple[Path, str]] = []
    v = _vendor_adb(repo_root)
    if v.is_file():
        out.append((v, "vendor/" + v.name))

    override = (os.environ.get(ENV_PLATFORM_TOOLS) or "").strip()
    if override:
        base = Path(override).expanduser()
        cand = base / ("adb.exe" if os.name == "nt" else "adb")
        if cand.is_file():
            out.append((cand, f"{ENV_PLATFORM_TOOLS}"))

    for env_name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        root = (os.environ.get(env_name) or "").strip()
        if not root:
            continue
        cand = Path(root).expanduser() / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if cand.is_file():
            out.append((cand, f"{env_name}/platform-tools"))

    if os.name == "nt":
        la = (os.environ.get("LOCALAPPDATA") or "").strip()
        base = Path(la) / "Android" / "Sdk" if la else Path.home() / "AppData" / "Local" / "Android" / "Sdk"
        cand = base / "platform-tools" / "adb.exe"
        if cand.is_file():
            out.append((cand, "LocalAppData/Android/Sdk/platform-tools"))

    return out


def resolve_adb_executable(repo_root: Path) -> tuple[str, str]:
    """Return ``(executable, source_tag)`` for logging/diagnostics.

    ``executable`` is an absolute path when resolved; otherwise the literal ``"adb"`` with
    ``source_tag == "not_found"`` (callers should expect subprocess failures).
    """
    _prepend_vendor_to_path(repo_root)
    w = shutil.which("adb")
    if w:
        return (w, "PATH")

    for cand, label in _platform_tools_candidates(repo_root):
        try:
            return (str(cand.resolve(strict=False)), label)
        except OSError:
            continue

    return ("adb", "not_found")


def print_adb_section(repo_root: Path) -> None:
    """Print resolved adb path, ``adb version``, and ``adb devices`` (Windows diagnose / support)."""
    print("--- adb (Android Debug Bridge) ---")
    exe, src = resolve_adb_executable(repo_root)
    print(f"resolved_executable: {exe}")
    print(f"resolution_source: {src}")
    if src == "not_found":
        print(
            "adb version: (skipped — no adb on PATH and no vendor/SDK candidate found; "
            "install platform-tools or set XYZ_ANDROID_PLATFORM_TOOLS to its directory.)"
        )
        print("adb devices: (skipped — same reason)")
        return

    try:
        proc = subprocess.run(
            [exe, "version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        merged = (proc.stdout or "") + (proc.stderr or "")
        lines = [ln for ln in merged.splitlines() if ln.strip()][:6]
        print("adb version:")
        if lines:
            for ln in lines:
                print(f"  {ln}")
        else:
            print(f"  (no output, exit {proc.returncode})")
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"adb version: (failed to run: {exc})")

    try:
        proc = subprocess.run(
            [exe, "devices"],
            text=True,
            capture_output=True,
            check=False,
            timeout=25,
        )
        out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        print("adb devices:")
        if out:
            for ln in out.splitlines():
                print(f"  {ln}")
        else:
            print(f"  (empty output, exit {proc.returncode})")
        if proc.returncode != 0:
            print(f"  (exit code {proc.returncode})")
        body = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith("List of devices")]
        if not body:
            print(
                "  hint: no devices listed — enable USB debugging on the phone, try another cable/USB port, "
                "authorize the RSA fingerprint on the device, and on Xiaomi enable "
                "\"USB debugging (Security settings)\" when applicable. spacedesk is unrelated to adb "
                "(see README troubleshooting)."
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"adb devices: (failed to run: {exc})")
