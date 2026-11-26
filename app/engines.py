"""EngineManager: Lazy-start and Windows Job-Object lifecycle management for Ollama & ComfyUI."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from app.config import COMFY_DIR, COMFY_URL, DATA_DIR, ENGINE_DIR, OLLAMA_URL

logger = logging.getLogger("engines")
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


class EngineManager:
    """Manages child AI engines (Ollama, ComfyUI) inside a Windows Job Object.

    When the parent AI Office process exits or closes, Windows automatically
    terminates every child process assigned to the Job Object.
    """

    def __init__(self) -> None:
        self.procs: dict[str, subprocess.Popen[bytes]] = {}
        self.logs_dir = DATA_DIR / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.job = self._make_job()

    def _make_job(self) -> Any:
        if os.name != "nt":
            return None
        try:
            import win32job

            job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation
            )
            info["BasicLimitInformation"]["LimitFlags"] |= (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            win32job.SetInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation, info
            )
            return job
        except Exception as exc:
            logger.warning("Could not create Windows Job Object: %s", exc)
            return None

    def _assign_to_job(self, pid: int) -> None:
        if not self.job or os.name != "nt":
            return
        try:
            import win32api
            import win32job

            handle = win32api.OpenProcess(0x1F0FFF, False, pid)
            win32job.AssignProcessToJobObject(self.job, handle)
        except Exception as exc:
            logger.warning("Failed to assign PID %s to Job Object: %s", pid, exc)

    def _alive(self, url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def ensure(
        self,
        name: str,
        cmd: list[str],
        cwd: str | Path,
        health_url: str,
        env: dict[str, str] | None = None,
        wait_secs: float = 0.0,
    ) -> bool:
        """Start engine hidden if not already listening on health_url."""
        if self._alive(health_url):
            return True

        existing = self.procs.get(name)
        if existing is not None and existing.poll() is None:
            return self._alive(health_url)

        log_path = self.logs_dir / f"{name}.log"
        log_file = open(log_path, "ab")
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            env=proc_env,
            creationflags=NO_WIN if os.name == "nt" else 0,
        )
        self.procs[name] = proc
        self._assign_to_job(proc.pid)

        if wait_secs > 0:
            deadline = time.monotonic() + wait_secs
            while time.monotonic() < deadline:
                if self._alive(health_url):
                    return True
                if proc.poll() is not None:
                    return False
                time.sleep(0.5)
        return self._alive(health_url)

    def ensure_ollama(self, wait_secs: float = 10.0) -> bool:
        models_dir = ENGINE_DIR / "MOSS-Image" / "ollama-models"
        env = {"OLLAMA_MODELS": str(models_dir)} if models_dir.exists() else {}
        return self.ensure(
            name="ollama",
            cmd=["ollama", "serve"],
            cwd=ENGINE_DIR,
            health_url=f"{OLLAMA_URL}/api/tags",
            env=env,
            wait_secs=wait_secs,
        )

    def ensure_comfy(self, wait_secs: float = 45.0) -> bool:
        comfy_py = COMFY_DIR / ".venv" / "Scripts" / "python.exe"
        py_exec = str(comfy_py if comfy_py.exists() else sys.executable)
        cmd = [
            py_exec,
            "main.py",
            "--lowvram",
            "--cpu-vae",
            "--reserve-vram",
            "1.0",
            "--preview-method",
            "auto",
            "--listen",
            "127.0.0.1",
            "--port",
            "8188",
        ]
        return self.ensure(
            name="comfy",
            cmd=cmd,
            cwd=COMFY_DIR,
            health_url=f"{COMFY_URL}/system_stats",
            wait_secs=wait_secs,
        )

    def shutdown(self) -> None:
        """Terminate all managed child engines."""
        for name, proc in list(self.procs.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception as exc:
                logger.warning("Error terminating %s: %s", name, exc)
        self.procs.clear()
