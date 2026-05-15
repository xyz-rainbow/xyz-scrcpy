# Enable ANSI/VT100 output for the current console process (no registry changes).
# Used by installer.bat when the user opts in to colors.
$ErrorActionPreference = 'Stop'
if (-not ('NativeCon' -as [type])) {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeCon {
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr GetStdHandle(int nStdHandle);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool GetConsoleMode(IntPtr h, out uint mode);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetConsoleMode(IntPtr h, uint mode);
}
"@
}
$handle = [NativeCon]::GetStdHandle(-11) # STD_OUTPUT_HANDLE
[uint32]$mode = 0
[void][NativeCon]::GetConsoleMode($handle, [ref]$mode)
$ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
[void][NativeCon]::SetConsoleMode($handle, $mode -bor $ENABLE_VIRTUAL_TERMINAL_PROCESSING)
exit 0
