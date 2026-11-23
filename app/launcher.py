from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent
for _p in (str(ROOT), str(APP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import uvicorn
import webview
from main import app, init_db
LOG = ROOT / "data" / "launcher.log"
RELAUNCH_GUARD = ROOT / "data" / ".relaunch_guard"
APP_USER_MODEL_ID = "OpenAI.AIOffice.Desktop"


def set_app_user_model_id() -> bool:
    """Keep the taskbar identity and icon separate from the pythonw.exe host."""
    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        set_id = shell32.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        result = set_id(APP_USER_MODEL_ID)
        if result < 0:
            raise OSError(f"SetCurrentProcessExplicitAppUserModelID failed: 0x{result & 0xFFFFFFFF:08X}")
        return True
    except Exception:
        return False


def is_elevated() -> bool:
    """Return True when this process has an elevated Windows token."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def focus_existing_instance() -> bool:
    """If an AI Office window is already open, bring it to focus and avoid duplicate processes."""
    try:
        import win32gui
        import win32con
        hwnd = win32gui.FindWindow(None, "AI Office")
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
    except Exception:
        pass
    return False


def relaunch_without_elevation() -> bool:
    """Ask Explorer to launch silently via VBS without flashing a cmd console.

    WebView2 IME input (including UniKey/EVKey) can fail when the host window
    runs elevated while the input method runs at medium integrity.
    """
    try:
        vbs = ROOT / "Start-AI-Office.vbs"
        target = str(vbs) if vbs.exists() else str(ROOT / "Start-AI-Office.bat")
        subprocess.Popen(
            ["explorer.exe", target],
            close_fds=True,
        )
        return True
    except Exception:
        return False


def server_is_running() -> bool:
    try:
        # /api/status awaits ollama_status() which can take ~2.2s on Windows when Ollama is offline.
        urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=5).read()
        return True
    except Exception:
        return False


_OLLAMA_PROC: subprocess.Popen | None = None


def ensure_local_ollama() -> bool:
    """Start local `ollama serve` silently in the background if not already listening."""
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2.0).read()
        return True
    except Exception:
        pass
    candidate = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"))
    ollama_exe = str(candidate) if candidate.is_file() else (shutil.which("ollama") or "")
    if not ollama_exe:
        return False
    try:
        flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        global _OLLAMA_PROC
        _OLLAMA_PROC = subprocess.Popen(
            [ollama_exe, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )
        for _ in range(16):
            time.sleep(0.5)
            try:
                urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.0).read()
                return True
            except Exception:
                pass
        return True
    except Exception:
        return False


def shutdown_local_ollama() -> None:
    """When the app window closes, unload model from VRAM and stop Ollama process if we started it."""
    global _OLLAMA_PROC
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=b'{"model":"qwen3.5:4b","keep_alive":0}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass
    if _OLLAMA_PROC and _OLLAMA_PROC.poll() is None:
        try:
            _OLLAMA_PROC.terminate()
            _OLLAMA_PROC.wait(timeout=2)
        except Exception:
            try:
                _OLLAMA_PROC.kill()
            except Exception:
                pass
        _OLLAMA_PROC = None


def warmup_ollama_model() -> None:
    """Preload model into RAM/VRAM with 24h keep-alive so the first chat message responds instantly."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=b'{"model":"qwen3.5:4b","keep_alive":"24h"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=35).read()
    except Exception:
        pass


def _ollama_startup_and_warmup() -> None:
    if ensure_local_ollama():
        warmup_ollama_model()


def serve() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


_ICON_HANDLES: list[int] = []


def apply_window_icon() -> None:
    """Set the native Windows title-bar/taskbar icon after pywebview creates its HWND."""
    try:
        import win32con
        import win32gui

        icon_path = ROOT / "app" / "ui" / "assets" / "ai-office.ico"
        if not icon_path.exists():
            return
        for _ in range(40):
            hwnd = win32gui.FindWindow(None, "AI Office")
            if hwnd:
                flags = win32con.LR_LOADFROMFILE
                small_icon = win32gui.LoadImage(0, str(icon_path), win32con.IMAGE_ICON, 32, 32, flags)
                large_icon = win32gui.LoadImage(0, str(icon_path), win32con.IMAGE_ICON, 256, 256, flags)
                win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, small_icon)
                win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, large_icon)
                # Give this HWND the same shell identity as its branded shortcuts.
                try:
                    from win32com.propsys import propsys, pscon
                    store = propsys.SHGetPropertyStoreForWindow(hwnd, propsys.IID_IPropertyStore)
                    store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(APP_USER_MODEL_ID, 31))
                    store.Commit()
                except Exception:
                    pass
                _ICON_HANDLES.extend([small_icon, large_icon])
                return
            time.sleep(0.25)
    except Exception:
        # The branded image remains in the UI and shortcut if native icon APIs fail.
        return


def main() -> None:
    # 1. Single Instance Check: if already running, focus existing window and exit cleanly
    if focus_existing_instance():
        return

    allow_elevated = "--allow-elevated" in sys.argv[1:]
    # Keep WebView2 at the same integrity level as UniKey/EVKey unless explicitly opted into Admin for elevated games.
    if is_elevated() and not allow_elevated:
        already_attempted = False
        try:
            if RELAUNCH_GUARD.exists():
                age = time.time() - RELAUNCH_GUARD.stat().st_mtime
                if age < 30:
                    already_attempted = True
        except Exception:
            pass

        if not already_attempted:
            try:
                RELAUNCH_GUARD.parent.mkdir(parents=True, exist_ok=True)
                RELAUNCH_GUARD.write_text(str(time.time()), encoding="utf-8")
            except Exception:
                pass
            if relaunch_without_elevation():
                return
        # If de-elevation was already attempted once or relaunch failed, do not loop endlessly.
        # Proceed with execution; the UI handles elevated mode and shows the admin-ime-warning.

    # Must be set before creating the native WebView window so Windows uses
    # the AI Office identity instead of grouping it under pythonw.exe.
    set_app_user_model_id()
    init_db()
    threading.Thread(target=_ollama_startup_and_warmup, daemon=True).start()
    if not server_is_running():
        threading.Thread(target=serve, daemon=True).start()
        for _ in range(60):
            if server_is_running():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("AI Office backend did not start on 127.0.0.1:8765")

    webview.create_window(
        "AI Office",
        "http://127.0.0.1:8765",
        width=1440,
        height=900,
        min_size=(800, 560),
        maximized=True,
    )
    threading.Thread(target=apply_window_icon, daemon=True).start()
    try:
        webview.start(gui="edgechromium")
    finally:
        shutdown_local_ollama()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write("\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            traceback.print_exc(file=handle)
        raise
