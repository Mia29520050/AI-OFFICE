"""Utilities for running hidden subprocesses without console window flashing on Windows."""
from __future__ import annotations

import os
import subprocess
from typing import Any

NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0


def run_hidden(cmd: list[str] | str, **kw: Any) -> subprocess.CompletedProcess[Any]:
    """Run subprocess.run with CREATE_NO_WINDOW + SW_HIDE on Windows."""
    kw["creationflags"] = kw.get("creationflags", 0) | NO_WIN
    if os.name == "nt" and "startupinfo" not in kw:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kw["startupinfo"] = si
    return subprocess.run(cmd, **kw)
