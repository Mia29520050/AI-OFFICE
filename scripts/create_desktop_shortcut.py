"""Create Desktop Shortcut for AI Office.

Configures a native Windows .lnk shortcut running directly via wscript.exe //B
to guarantee 100% silent execution without flashing any terminal / cmd window.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
VBS_PATH = ROOT_DIR / "Start-AI-Office.vbs"
ICON_PATH = ROOT_DIR / "app" / "ui" / "assets" / "ai-office.ico"


def create_shortcut() -> Path:
    # Resolve Windows Desktop path
    desktop_dir = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
    if not desktop_dir.exists():
        desktop_dir = Path.home() / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    shortcut_path = desktop_dir / "AI Office.lnk"
    wscript_exe = Path(os.path.expandvars(r"%SystemRoot%\System32\wscript.exe"))
    if not wscript_exe.exists():
        wscript_exe = Path("wscript.exe")

    # Shortcut parameters
    target = str(wscript_exe)
    arguments = f'//B "{VBS_PATH}"'
    working_dir = str(ROOT_DIR)
    icon_loc = f"{ICON_PATH},0" if ICON_PATH.exists() else ""
    description = "AI Office - Tro ly AI & Studio Sang tao Da Nang"

    # Use PowerShell COM interface (standard & universal on Windows)
    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}')
$Shortcut.TargetPath = '{target}'
$Shortcut.Arguments = '{arguments}'
$Shortcut.WorkingDirectory = '{working_dir}'
$Shortcut.Description = '{description}'
if ('{icon_loc}' -ne '') {{
    $Shortcut.IconLocation = '{icon_loc}'
}}
$Shortcut.WindowStyle = 7
$Shortcut.Save()
"""

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        text=True,
        creationflags=flags,
        startupinfo=si,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"Failed to create shortcut: {proc.stderr}")

    print(f"Created shortcut successfully: {shortcut_path}")
    print(f" - Target:           {target}")
    print(f" - Arguments:        {arguments}")
    print(f" - WorkingDirectory: {working_dir}")
    print(f" - IconLocation:     {icon_loc}")
    print(" - Terminal mode:    0 (Completely hidden via wscript //B)")
    return shortcut_path


if __name__ == "__main__":
    try:
        path = create_shortcut()
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
