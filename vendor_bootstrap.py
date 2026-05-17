"""Install adb and screen-mirroring binaries into vendor/ (multi-OS, staged fail-soft)."""

from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import adb_resolve

SCRCPY_VERSION = "3.3.4"
DOWNLOAD_TIMEOUT = 120
PKG_TIMEOUT = 300

# Pinned download URLs (no user-facing upstream product names in console output).
URL_PLATFORM_TOOLS_LINUX = "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
URL_PLATFORM_TOOLS_DARWIN = "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
URL_PLATFORM_TOOLS_WINDOWS = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
URL_SCRCPY_LINUX_X86_64 = (
    f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/"
    f"scrcpy-linux-x86_64-v{SCRCPY_VERSION}.tar.gz"
)
URL_SCRCPY_LINUX_AARCH64 = (
    f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/"
    f"scrcpy-linux-aarch64-v{SCRCPY_VERSION}.tar.gz"
)
URL_SCRCPY_MACOS_AARCH64 = (
    f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/"
    f"scrcpy-macos-aarch64-v{SCRCPY_VERSION}.tar.gz"
)
URL_SCRCPY_MACOS_X86_64 = (
    f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/"
    f"scrcpy-macos-x86_64-v{SCRCPY_VERSION}.tar.gz"
)
URL_SCRCPY_WINDOWS_ZIP = (
    f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/"
    f"scrcpy-win64-v{SCRCPY_VERSION}.zip"
)


@dataclass
class EnvInfo:
    os_name: str
    machine: str
    package_manager: str  # apt | dnf | winget | brew | none
    has_sudo: bool


@dataclass
class ToolInstallResult:
    adb_ok: bool = False
    scrcpy_ok: bool = False
    adb_source: str = "missing"
    scrcpy_source: str = "missing"
    attempts: list[str] = field(default_factory=list)


def vendor_dir(install_root: Path) -> Path:
    return install_root / "vendor"


def vendor_adb_path(install_root: Path) -> Path:
    name = "adb.exe" if os.name == "nt" else "adb"
    return vendor_dir(install_root) / name


def vendor_scrcpy_path(install_root: Path) -> Path:
    name = "scrcpy.exe" if os.name == "nt" else "scrcpy"
    return vendor_dir(install_root) / name


def vendor_path_export_line(install_root: Path) -> str:
    v = vendor_dir(install_root).resolve()
    return f'export PATH="{v}:$PATH"'


def vendor_path_env_value(install_root: Path) -> str:
    v = str(vendor_dir(install_root).resolve())
    return f"{v}{os.pathsep}{os.environ.get('PATH', '')}"


def prepend_vendor_to_path(install_root: Path) -> None:
    """Prepend install_root/vendor to PATH so adb/scrcpy resolve to bundled binaries first."""
    vend = vendor_dir(install_root)
    if not vend.is_dir():
        return
    prefix = str(vend.resolve())
    path = os.environ.get("PATH", "")
    if prefix not in path.split(os.pathsep):
        os.environ["PATH"] = prefix + os.pathsep + path


def resolve_scrcpy_executable(install_root: Path) -> tuple[str, str]:
    """Return (executable, source_tag) like adb_resolve."""
    vend = vendor_scrcpy_path(install_root)
    if vend.is_file() and os.access(vend, os.X_OK):
        return (str(vend.resolve()), "vendor/scrcpy")
    w = shutil.which("scrcpy")
    if w:
        return (w, "PATH")
    return ("scrcpy", "not_found")


def verify_tools_resolved(install_root: Path) -> tuple[bool, bool]:
    prepend_vendor_to_path(install_root)
    adb_exe, adb_src = adb_resolve.resolve_adb_executable(install_root)
    adb_ok = adb_src != "not_found"
    if adb_ok and not Path(adb_exe).is_file():
        adb_ok = shutil.which("adb") is not None
    scrcpy_exe, scrcpy_src = resolve_scrcpy_executable(install_root)
    scrcpy_ok = scrcpy_src != "not_found"
    if scrcpy_ok and scrcpy_exe != "scrcpy" and not Path(scrcpy_exe).is_file():
        scrcpy_ok = shutil.which("scrcpy") is not None
    elif scrcpy_ok and scrcpy_exe == "scrcpy":
        scrcpy_ok = shutil.which("scrcpy") is not None
    return adb_ok, scrcpy_ok


def detect_environment() -> EnvInfo:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = "windows" if system == "windows" else "darwin" if system == "darwin" else "linux"
    pm = "none"
    if os_name == "linux":
        if shutil.which("apt-get"):
            pm = "apt"
        elif shutil.which("dnf"):
            pm = "dnf"
    elif os_name == "windows" and shutil.which("winget"):
        pm = "winget"
    elif os_name == "darwin" and shutil.which("brew"):
        pm = "brew"
    has_sudo = _has_passwordless_sudo()
    return EnvInfo(os_name=os_name, machine=machine, package_manager=pm, has_sudo=has_sudo)


def scrcpy_vendor_download_url(env: EnvInfo) -> str | None:
    """Pinned scrcpy archive URL for the host OS/CPU, or None if unsupported."""
    if env.os_name == "linux":
        if env.machine in ("aarch64", "arm64"):
            return URL_SCRCPY_LINUX_AARCH64
        if env.machine in ("x86_64", "amd64"):
            return URL_SCRCPY_LINUX_X86_64
        return None
    if env.os_name == "darwin":
        if env.machine in ("aarch64", "arm64"):
            return URL_SCRCPY_MACOS_AARCH64
        if env.machine in ("x86_64", "amd64"):
            return URL_SCRCPY_MACOS_X86_64
        return None
    return None


def _has_passwordless_sudo() -> bool:
    if not shutil.which("sudo"):
        return False
    try:
        proc = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _log(result: ToolInstallResult, msg: str, *, warn: bool = False) -> None:
    prefix = "[WARN]" if warn else "[INFO]"
    line = f"{prefix} {msg}"
    result.attempts.append(line)


def _chmod_executable(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _download_file(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "xyz-scrcpy-installer/1.0"})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            data = resp.read()
        if len(data) < 512:
            return False
        usage = shutil.disk_usage(dest.parent)
        if usage.free < len(data) + 50_000_000:
            return False
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
        return True
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return False


def _find_file_named(root: Path, name: str) -> Path | None:
    if (root / name).is_file():
        return root / name
    for p in root.rglob(name):
        if p.is_file():
            return p
    return None


def _install_binary_from_path(src: Path, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        _chmod_executable(dest)
        return dest.is_file()
    except OSError:
        return False


def _extract_platform_tools_zip(zip_path: Path, vendor: Path, result: ToolInstallResult) -> bool:
    adb_name = "adb.exe" if os.name == "nt" else "adb"
    dest = vendor / adb_name
    if dest.is_file():
        return True
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            if zf.testzip() is not None:
                _log(result, "platform-tools zip failed integrity check", warn=True)
                return False
            tmp = Path(tempfile.mkdtemp(prefix="xyz_pt_"))
            try:
                zf.extractall(tmp)
                found = _find_file_named(tmp, adb_name)
                if not found:
                    _log(result, f"{adb_name} not found inside platform-tools archive", warn=True)
                    return False
                return _install_binary_from_path(found, dest)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    except (zipfile.BadZipFile, OSError) as exc:
        _log(result, f"platform-tools extract failed: {exc}", warn=True)
        return False


def _extract_scrcpy_tar(tar_path: Path, vendor: Path, result: ToolInstallResult) -> bool:
    dest = vendor_scrcpy_path(vendor.parent)
    if dest.is_file():
        return True
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            tmp = Path(tempfile.mkdtemp(prefix="xyz_scrcpy_"))
            try:
                if sys.version_info >= (3, 12):
                    tf.extractall(tmp, filter="data")
                else:
                    tf.extractall(tmp)
                found = _find_file_named(tmp, "scrcpy")
                if not found:
                    _log(result, "scrcpy binary not found in screen-mirror archive", warn=True)
                    return False
                return _install_binary_from_path(found, dest)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    except (tarfile.TarError, OSError) as exc:
        _log(result, f"screen-mirror archive extract failed: {exc}", warn=True)
        return False


def _extract_scrcpy_win_zip(zip_path: Path, vendor: Path, result: ToolInstallResult) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            if zf.testzip() is not None:
                _log(result, "Windows bundle zip failed integrity check", warn=True)
                return False
            tmp = Path(tempfile.mkdtemp(prefix="xyz_scrcpy_win_"))
            try:
                zf.extractall(tmp)
                for name in zf.namelist():
                    base = os.path.basename(name)
                    if not base:
                        continue
                    src = tmp / name
                    if not src.is_file():
                        continue
                    dest = vendor / base
                    if dest.exists() and dest.is_dir():
                        continue
                    _install_binary_from_path(src, dest)
                ok_scrcpy = vendor_scrcpy_path(vendor.parent).is_file()
                ok_adb = vendor_adb_path(vendor.parent).is_file()
                return ok_scrcpy or ok_adb
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    except (zipfile.BadZipFile, OSError) as exc:
        _log(result, f"Windows bundle extract failed: {exc}", warn=True)
        return False


def _write_vendor_notice(vendor: Path) -> None:
    notice = vendor / "NOTICE"
    if notice.exists():
        return
    text = (
        "Bundled third-party binaries for XYZ-scrcpy\n"
        "----------------------------------------\n"
        f"- Android platform-tools (adb): Apache License 2.0\n"
        f"- Screen mirroring client v{SCRCPY_VERSION}: Apache License 2.0\n"
        "Install staging may also use system packages (apt/winget/brew) when download is unavailable.\n"
    )
    try:
        vendor.mkdir(parents=True, exist_ok=True)
        notice.write_text(text, encoding="utf-8")
    except OSError:
        pass


def stage_vendor_download(install_root: Path, env: EnvInfo, result: ToolInstallResult) -> None:
    vendor = vendor_dir(install_root)
    vendor.mkdir(parents=True, exist_ok=True)
    _write_vendor_notice(vendor)
    adb_ok, scrcpy_ok = verify_tools_resolved(install_root)
    if adb_ok and scrcpy_ok:
        _log(result, "vendor tools already present; skipping download")
        return

    tmp_dir = Path(tempfile.mkdtemp(prefix="xyz_vendor_dl_"))
    try:
        if env.os_name == "linux":
            if not adb_ok:
                zip_path = tmp_dir / "platform-tools.zip"
                _log(result, "Downloading Android platform-tools (adb)...")
                if _download_file(URL_PLATFORM_TOOLS_LINUX, zip_path):
                    if _extract_platform_tools_zip(zip_path, vendor, result):
                        result.adb_source = "vendor"
                        _log(result, "adb installed to vendor/")
                    else:
                        _log(result, "adb vendor extract failed", warn=True)
                else:
                    _log(result, "adb download failed (network or disk)", warn=True)
            if not scrcpy_ok:
                arch_url = scrcpy_vendor_download_url(env)
                if not arch_url:
                    _log(result, f"unsupported CPU {env.machine} for bundled screen-mirror download", warn=True)
                else:
                    tar_path = tmp_dir / "scrcpy.tar.gz"
                    _log(result, f"Downloading screen-mirror tool v{SCRCPY_VERSION}...")
                    if _download_file(arch_url, tar_path):
                        if _extract_scrcpy_tar(tar_path, vendor, result):
                            result.scrcpy_source = "vendor"
                            _log(result, "scrcpy installed to vendor/")
                        else:
                            _log(result, "scrcpy vendor extract failed", warn=True)
                    else:
                        _log(result, "scrcpy download failed (network or disk)", warn=True)

        elif env.os_name == "darwin":
            if not adb_ok:
                zip_path = tmp_dir / "platform-tools.zip"
                _log(result, "Downloading Android platform-tools (adb)...")
                if _download_file(URL_PLATFORM_TOOLS_DARWIN, zip_path):
                    if _extract_platform_tools_zip(zip_path, vendor, result):
                        result.adb_source = "vendor"
                        _log(result, "adb installed to vendor/")
                    else:
                        _log(result, "adb vendor extract failed", warn=True)
                else:
                    _log(result, "adb download failed (network or disk)", warn=True)
            if not scrcpy_ok:
                arch_url = scrcpy_vendor_download_url(env)
                if not arch_url:
                    _log(result, f"unsupported CPU {env.machine} for bundled screen-mirror download", warn=True)
                else:
                    tar_path = tmp_dir / "scrcpy.tar.gz"
                    _log(result, f"Downloading screen-mirror tool v{SCRCPY_VERSION}...")
                    if _download_file(arch_url, tar_path):
                        if _extract_scrcpy_tar(tar_path, vendor, result):
                            result.scrcpy_source = "vendor"
                            _log(result, "scrcpy installed to vendor/")
                        else:
                            _log(result, "scrcpy vendor extract failed", warn=True)
                    else:
                        _log(result, "scrcpy download failed (network or disk)", warn=True)

        elif env.os_name == "windows":
            zip_path = tmp_dir / "scrcpy-win.zip"
            _log(result, f"Downloading Windows tool bundle v{SCRCPY_VERSION}...")
            if _download_file(URL_SCRCPY_WINDOWS_ZIP, zip_path):
                if _extract_scrcpy_win_zip(zip_path, vendor, result):
                    if vendor_scrcpy_path(install_root).is_file():
                        result.scrcpy_source = "vendor"
                    if vendor_adb_path(install_root).is_file():
                        result.adb_source = "vendor"
            if not vendor_adb_path(install_root).is_file():
                zip_path = tmp_dir / "platform-tools.zip"
                _log(result, "Downloading Android platform-tools (adb)...")
                if _download_file(URL_PLATFORM_TOOLS_WINDOWS, zip_path):
                    _extract_platform_tools_zip(zip_path, vendor, result)
                    if vendor_adb_path(install_root).is_file():
                        result.adb_source = "vendor"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_command(cmd: list[str], result: ToolInstallResult, label: str) -> bool:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=PKG_TIMEOUT,
            check=False,
        )
        snippet = (proc.stderr or proc.stdout or "").strip().replace("\n", " ")[:200]
        _log(
            result,
            f"{label}: exit={proc.returncode}" + (f" ({snippet})" if snippet and proc.returncode != 0 else ""),
            warn=proc.returncode != 0,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log(result, f"{label} failed: {exc}", warn=True)
        return False


def stage_package_managers(install_root: Path, env: EnvInfo, result: ToolInstallResult) -> None:
    adb_ok, scrcpy_ok = verify_tools_resolved(install_root)
    if adb_ok and scrcpy_ok:
        return

    if env.package_manager == "apt":
        if not env.has_sudo:
            _log(result, "sudo not available; skipping apt install", warn=True)
            return
        if not adb_ok:
            _run_command(
                ["sudo", "-n", "apt-get", "install", "-y", "adb"],
                result,
                "apt adb",
            )
        if not scrcpy_ok:
            _run_command(
                ["sudo", "-n", "apt-get", "install", "-y", "scrcpy"],
                result,
                "apt scrcpy",
            )
    elif env.package_manager == "dnf":
        if not env.has_sudo:
            _log(result, "sudo not available; skipping dnf install", warn=True)
            return
        if not adb_ok:
            _run_command(
                ["sudo", "-n", "dnf", "install", "-y", "android-tools"],
                result,
                "dnf android-tools",
            )
        if not scrcpy_ok:
            _run_command(
                ["sudo", "-n", "dnf", "install", "-y", "scrcpy"],
                result,
                "dnf scrcpy",
            )
    elif env.package_manager == "winget":
        if not adb_ok:
            _run_command(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "Google.PlatformTools",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                result,
                "winget PlatformTools",
            )
        if not scrcpy_ok:
            _run_command(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "Genymobile.scrcpy",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                result,
                "winget scrcpy",
            )
    elif env.package_manager == "brew":
        if not adb_ok:
            _run_command(["brew", "install", "android-platform-tools"], result, "brew android-platform-tools")
        if not scrcpy_ok:
            _run_command(["brew", "install", "scrcpy"], result, "brew scrcpy")
    else:
        _log(result, "no supported package manager detected for stage B", warn=True)

    adb_ok, scrcpy_ok = verify_tools_resolved(install_root)
    if adb_ok:
        _, src = adb_resolve.resolve_adb_executable(install_root)
        if src != "not_found":
            result.adb_source = src
    if scrcpy_ok:
        _, src = resolve_scrcpy_executable(install_root)
        if src != "not_found":
            result.scrcpy_source = src


def print_manual_recovery(os_name: str, install_root: Path, result: ToolInstallResult) -> None:
    adb_ok, scrcpy_ok = verify_tools_resolved(install_root)
    if adb_ok and scrcpy_ok:
        return
    print("\n--- Android tools: manual recovery (last resort) ---")
    if os_name == "linux":
        print("  sudo apt install adb scrcpy")
        print("  # Fedora: sudo dnf install android-tools scrcpy")
    elif os_name == "windows":
        print("  winget install -e --id Google.PlatformTools")
        print("  winget install -e --id Genymobile.scrcpy")
        print(f"  Or copy adb.exe and scrcpy.exe into: {vendor_dir(install_root)}")
    elif os_name == "darwin":
        print("  brew install android-platform-tools scrcpy")
    print(f"  Or set XYZ_ANDROID_PLATFORM_TOOLS=/path/to/platform-tools directory")
    print(f"  Install log: {install_root / 'config' / 'install.log'}")
    print("---\n")


def ensure_android_tools(
    install_root: Path,
    os_name: str | None = None,
    *,
    verbose: bool = False,
    skip_vendor_download: bool = False,
) -> ToolInstallResult:
    """Stages A (vendor download) -> B (package managers) -> C (manual hints)."""
    install_root = install_root.resolve()
    env = detect_environment()
    if os_name:
        env.os_name = os_name
    result = ToolInstallResult()

    print("Installing Android tools (adb) and screen-mirror client (scrcpy)...")

    if not skip_vendor_download:
        stage_vendor_download(install_root, env, result)
    else:
        _log(result, "vendor download skipped (--skip-vendor-download)")

    adb_ok, scrcpy_ok = verify_tools_resolved(install_root)
    result.adb_ok = adb_ok
    result.scrcpy_ok = scrcpy_ok
    if adb_ok and result.adb_source == "missing":
        _, src = adb_resolve.resolve_adb_executable(install_root)
        result.adb_source = src if src != "not_found" else "path"
    if scrcpy_ok and result.scrcpy_source == "missing":
        _, src = resolve_scrcpy_executable(install_root)
        result.scrcpy_source = src if src != "not_found" else "path"

    if not adb_ok or not scrcpy_ok:
        stage_package_managers(install_root, env, result)
        adb_ok, scrcpy_ok = verify_tools_resolved(install_root)
        result.adb_ok = adb_ok
        result.scrcpy_ok = scrcpy_ok

    if verbose:
        for line in result.attempts:
            print(line)

    summary = (
        f"Android tools: adb={'OK' if adb_ok else 'MISSING'} ({result.adb_source}) "
        f"scrcpy={'OK' if scrcpy_ok else 'MISSING'} ({result.scrcpy_source})"
    )
    print(summary)
    _log(result, summary)

    if not adb_ok or not scrcpy_ok:
        print_manual_recovery(env.os_name, install_root, result)

    return result
