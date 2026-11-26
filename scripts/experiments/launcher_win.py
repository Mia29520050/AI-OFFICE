"""
AI Office Native Windows GUI Launcher (Subsystem Windows - Zero CMD/Terminal).
Compiled with PyInstaller --windowed to guarantee 0% terminal/console flashing.
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    if getattr(sys, 'frozen', False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parent

    launcher_py = root / "app" / "launcher.py"
    venv_pythonw = root / ".venv" / "Scripts" / "pythonw.exe"

    if venv_pythonw.exists():
        pythonw = str(venv_pythonw)
    else:
        cand313 = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"))
        cand312 = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"))
        if cand313.exists():
            pythonw = str(cand313)
        elif cand312.exists():
            pythonw = str(cand312)
        else:
            pythonw = "pythonw.exe"

    flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE

    try:
        subprocess.Popen(
            [pythonw, str(launcher_py)] + sys.argv[1:],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
            startupinfo=si,
        )
    except Exception as exc:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Không thể khởi động AI Office:\n{exc}", "AI Office Lỗi", 0x10)

if __name__ == "__main__":
    main()
