"""Centralized configuration for AI Office paths, engines, and security."""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
DATA_DIR = Path(os.getenv("AI_OFFICE_DATA_DIR", str(ROOT_DIR / "data")))
ENGINE_DIR = Path(os.getenv("AI_OFFICE_ENGINE_DIR", str(ROOT_DIR / "engine")))
EXPORT_DIR = Path(os.getenv("AI_OFFICE_EXPORT_DIR", str(ROOT_DIR / "Export")))

COMFY_DIR = Path(os.getenv("COMFYUI_PATH", str(ENGINE_DIR / "ComfyUI")))
COMFY_URL = os.getenv("COMFYUI_URL", os.getenv("COMFYUI_HOST", "http://127.0.0.1:8188")).rstrip("/")
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("AI_OFFICE_MODEL", "qwen3.5:4b")

# Optional LAN token for mobile/remote access when binding 0.0.0.0
MOBILE_LAN_TOKEN = os.getenv("AI_OFFICE_LAN_TOKEN", "").strip()

# Hardware limits
VRAM_LIMIT_MB = int(os.getenv("AI_OFFICE_VRAM_LIMIT_MB", "6144"))
RAM_LIMIT_MB = int(os.getenv("AI_OFFICE_RAM_LIMIT_MB", "12288"))
DEFAULT_NUM_CTX = int(os.getenv("AI_OFFICE_NUM_CTX", "4096"))
