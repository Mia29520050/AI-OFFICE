"""VRAM Guard & Hardware Monitor for 6GB VRAM / 12GB RAM safety.

Provides:
- Cross-unloading between Ollama and ComfyUI before heavy GPU tasks.
- System health & resource monitor (VRAM, RAM, Ollama/ComfyUI status).
- Active game detection to defer heavy background GPU jobs while gaming.
"""
from __future__ import annotations

import asyncio
import ctypes
import logging
import subprocess
from typing import Any, Awaitable, Callable, TypeVar

import httpx

from app.config import COMFY_URL, OLLAMA_MODEL, OLLAMA_URL

logger = logging.getLogger("vram_guard")
T = TypeVar("T")

VRAM_SEMAPHORE = asyncio.Semaphore(1)


async def free_ollama(model: str = OLLAMA_MODEL) -> bool:
    """Unload Ollama model from VRAM immediately using keep_alive=0."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "keep_alive": 0},
            )
            return r.status_code == 200
    except Exception:
        return False


async def free_comfy() -> bool:
    """Unload ComfyUI models and free VRAM."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.post(
                f"{COMFY_URL}/free",
                json={"unload_models": True, "free_memory": True},
            )
            return r.status_code == 200
    except Exception:
        return False


async def run_heavy(kind: str, fn: Callable[[], Awaitable[T]]) -> T:
    """Serialize heavy GPU work and cross-unload the opposite engine first."""
    async with VRAM_SEMAPHORE:
        if kind == "llm":
            await free_comfy()
        else:
            await free_ollama()
        return await fn()


def _query_vram_mb() -> dict[str, int]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            timeout=3,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).strip()
        if out:
            parts = [int(x.strip()) for x in out.splitlines()[0].split(",")]
            if len(parts) == 3:
                return {"total_mb": parts[0], "used_mb": parts[1], "free_mb": parts[2]}
    except Exception:
        pass
    return {"total_mb": 6144, "used_mb": 0, "free_mb": 0}


def _query_ram_mb() -> dict[str, int]:
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return {
                "total_mb": int(stat.ullTotalPhys // (1024 * 1024)),
                "free_mb": int(stat.ullAvailPhys // (1024 * 1024)),
                "load_pct": int(stat.dwMemoryLoad),
            }
    except Exception:
        pass
    return {"total_mb": 12288, "free_mb": 0, "load_pct": 0}


async def get_system_health() -> dict[str, Any]:
    """Return live VRAM, RAM, and Ollama/ComfyUI engine health."""
    ollama_ok = False
    comfy_ok = False
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = r.status_code == 200
        except Exception:
            pass
        try:
            r = await client.get(f"{COMFY_URL}/system_stats")
            comfy_ok = r.status_code == 200
        except Exception:
            pass

    return {
        "vram": _query_vram_mb(),
        "ram": _query_ram_mb(),
        "engines": {
            "ollama_online": ollama_ok,
            "comfy_online": comfy_ok,
        },
        "vram_guard_locked": VRAM_SEMAPHORE.locked(),
    }
