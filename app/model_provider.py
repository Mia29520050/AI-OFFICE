from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_LOCAL_MODEL = os.getenv("AI_OFFICE_MODEL", "qwen3.5:4b")


class ModelSettingsUpdate(BaseModel):
    provider: str | None = Field(default=None, pattern="^(local|cloud)$")
    local_model: str | None = Field(default=None, min_length=1, max_length=120)
    local_num_ctx: int | None = Field(default=None, ge=2048, le=16384)
    cloud_enabled: bool | None = None
    cloud_base_url: str | None = Field(default=None, max_length=300)
    cloud_model: str | None = Field(default=None, max_length=120)
    cloud_api_key: str | None = Field(default=None, max_length=400)
    clear_cloud_api_key: bool = False


class ModelProviderManager:
    """Manage local Ollama inference and optional user-enabled OpenAI-compatible cloud Vision/LLM."""

    def __init__(self, db_getter: Any, semaphore: asyncio.Semaphore) -> None:
        self._db_getter = db_getter
        self._semaphore = semaphore

    def ensure_table(self) -> None:
        db = self._db_getter()
        try:
            with db:
                db.execute(
                    """CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )"""
                )
        finally:
            db.close()

    def get_settings(self, *, include_secret: bool = False) -> dict[str, Any]:
        self.ensure_table()
        defaults: dict[str, Any] = {
            "provider": "local",
            "local_model": DEFAULT_LOCAL_MODEL,
            "local_num_ctx": 2048,
            "cloud_enabled": False,
            "cloud_base_url": "https://api.openai.com/v1",
            "cloud_model": "gpt-4o-mini",
            "cloud_api_key": "",
        }
        db = self._db_getter()
        try:
            row = db.execute("SELECT value FROM app_settings WHERE key='model_config'").fetchone()
        finally:
            db.close()
        if row:
            try:
                stored = json.loads(row["value"])
                if isinstance(stored, dict):
                    defaults.update({k: stored[k] for k in defaults if k in stored})
            except json.JSONDecodeError:
                pass
        defaults["local_num_ctx"] = max(2048, min(int(defaults.get("local_num_ctx") or 2048), 16384))
        defaults["cloud_enabled"] = bool(defaults.get("cloud_enabled", False))
        if defaults["provider"] not in {"local", "cloud"}:
            defaults["provider"] = "local"
        if not include_secret:
            key = str(defaults.pop("cloud_api_key", "") or "")
            defaults["cloud_api_key_set"] = bool(key)
            defaults["cloud_api_key_preview"] = (key[:4] + "..." + key[-3:]) if len(key) >= 10 else ("***" if key else "")
        return defaults

    def update_settings(self, patch: ModelSettingsUpdate) -> dict[str, Any]:
        current = self.get_settings(include_secret=True)
        if patch.provider is not None:
            current["provider"] = patch.provider
        if patch.local_model is not None:
            current["local_model"] = patch.local_model.strip() or DEFAULT_LOCAL_MODEL
        if patch.local_num_ctx is not None:
            current["local_num_ctx"] = max(2048, min(int(patch.local_num_ctx), 16384))
        if patch.cloud_enabled is not None:
            current["cloud_enabled"] = bool(patch.cloud_enabled)
        if patch.cloud_base_url is not None:
            url = patch.cloud_base_url.strip().rstrip("/")
            if url and not url.startswith(("https://", "http://")):
                raise HTTPException(400, "Cloud Base URL phải bắt đầu bằng https:// hoặc http://.")
            current["cloud_base_url"] = url
        if patch.cloud_model is not None:
            current["cloud_model"] = patch.cloud_model.strip()
        if patch.clear_cloud_api_key:
            current["cloud_api_key"] = ""
        elif patch.cloud_api_key is not None and patch.cloud_api_key.strip():
            current["cloud_api_key"] = patch.cloud_api_key.strip()

        if current["provider"] == "cloud" and not current["cloud_enabled"]:
            current["cloud_enabled"] = True
        if current["cloud_enabled"] and (not current["cloud_base_url"] or not current["cloud_model"] or not current["cloud_api_key"]):
            raise HTTPException(400, "Để bật Cloud Vision/LLM cần điền đủ Base URL, Model và API Key.")

        self.ensure_table()
        db = self._db_getter()
        try:
            with db:
                db.execute(
                    "INSERT INTO app_settings(key, value) VALUES('model_config', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (json.dumps(current, ensure_ascii=False),),
                )
        finally:
            db.close()
        return self.get_settings(include_secret=False)

    def active_route(self) -> dict[str, Any]:
        cfg = self.get_settings(include_secret=True)
        use_cloud = bool(cfg["cloud_enabled"] and cfg["provider"] == "cloud" and cfg["cloud_api_key"] and cfg["cloud_base_url"] and cfg["cloud_model"])
        return {
            "mode": "cloud" if use_cloud else "local",
            "model": cfg["cloud_model"] if use_cloud else cfg["local_model"],
            "local_model": cfg["local_model"],
            "local_num_ctx": cfg["local_num_ctx"],
            "cloud_enabled": cfg["cloud_enabled"],
        }

    async def ollama_status(self) -> dict[str, Any]:
        cfg = self.get_settings(include_secret=True)
        target_model = cfg["local_model"]
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(f"{DEFAULT_OLLAMA_URL}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
                names = [m.get("name") for m in models if m.get("name")]
                ready = any(name == target_model or name.startswith(target_model) for name in names)
                return {
                    "online": True,
                    "model": target_model,
                    "model_ready": ready,
                    "models": names,
                    "active_mode": self.active_route()["mode"],
                    "active_model": self.active_route()["model"],
                }
        except Exception as exc:
            route = self.active_route()
            return {
                "online": False,
                "model": target_model,
                "model_ready": False,
                "models": [],
                "error": str(exc),
                "active_mode": route["mode"],
                "active_model": route["model"],
            }

    async def runtime_ready(self) -> tuple[bool, str]:
        route = self.active_route()
        if route["mode"] == "cloud":
            return True, ""
        state = await self.ollama_status()
        if not state["online"] or not state["model_ready"]:
            return False, "Model local chưa sẵn sàng. Kiểm tra Ollama hoặc bật Cloud API trong Cài đặt."
        return True, ""

    @staticmethod
    def _to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for msg in messages:
            role = str(msg.get("role", "user"))
            text = str(msg.get("content", ""))
            images = msg.get("images") or []
            if not images:
                converted.append({"role": role, "content": text})
                continue
            parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
            for img_b64 in images:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                })
            converted.append({"role": role, "content": parts})
        return converted

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
        num_predict: int = 800,
        num_ctx: int | None = None,
        temperature: float = 0.25,
    ) -> str:
        cfg = self.get_settings(include_secret=True)
        use_cloud = bool(cfg["cloud_enabled"] and cfg["provider"] == "cloud" and cfg["cloud_api_key"] and cfg["cloud_base_url"] and cfg["cloud_model"])
        if use_cloud:
            endpoint = cfg["cloud_base_url"].rstrip("/") + "/chat/completions"
            payload: dict[str, Any] = {
                "model": cfg["cloud_model"],
                "messages": self._to_openai_messages(messages),
                "max_tokens": max(128, min(int(num_predict), 2048)),
                "temperature": temperature,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            headers = {
                "Authorization": f"Bearer {cfg['cloud_api_key']}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=8.0)) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    return ""
                return str(choices[0].get("message", {}).get("content", "") or "").strip()

        ctx_size = int(num_ctx if num_ctx is not None else cfg["local_num_ctx"])
        payload = {
            "model": cfg["local_model"],
            "messages": messages,
            "stream": False,
            "keep_alive": "24h",
            "think": False,
            "options": {
                "num_ctx": max(2048, min(ctx_size, 16384)),
                "num_predict": max(128, min(int(num_predict), 2048)),
                "temperature": temperature,
            },
        }
        if json_mode:
            payload["format"] = "json"
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
                response = await client.post(f"{DEFAULT_OLLAMA_URL}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                return str(data.get("message", {}).get("content", "") or "").strip()

    async def warmup(self) -> bool:
        """Preload active local model into memory with 24h keep-alive."""
        cfg = self.get_settings(include_secret=True)
        if cfg["cloud_enabled"] and cfg["provider"] == "cloud":
            return True
        target_model = cfg["local_model"]
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.post(
                    f"{DEFAULT_OLLAMA_URL}/api/generate",
                    json={"model": target_model, "keep_alive": "24h"},
                )
                return res.status_code == 200
        except Exception:
            return False

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        num_predict: int = 1000,
        num_ctx: int | None = None,
        temperature: float = 0.25,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens in real-time from local Ollama or OpenAI-compatible cloud."""
        cfg = self.get_settings(include_secret=True)
        use_cloud = bool(cfg["cloud_enabled"] and cfg["provider"] == "cloud" and cfg["cloud_api_key"] and cfg["cloud_base_url"] and cfg["cloud_model"])
        if use_cloud:
            endpoint = cfg["cloud_base_url"].rstrip("/") + "/chat/completions"
            payload: dict[str, Any] = {
                "model": cfg["cloud_model"],
                "messages": self._to_openai_messages(messages),
                "max_tokens": max(128, min(int(num_predict), 2048)),
                "temperature": temperature,
                "stream": True,
            }
            headers = {
                "Authorization": f"Bearer {cfg['cloud_api_key']}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=8.0)) as client:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            data = json.loads(raw)
                            choices = data.get("choices") or []
                            if choices:
                                delta = choices[0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    yield chunk
                        except Exception:
                            continue
            return

        ctx_size = int(num_ctx if num_ctx is not None else cfg["local_num_ctx"])
        payload = {
            "model": cfg["local_model"],
            "messages": messages,
            "stream": True,
            "keep_alive": "24h",
            "think": False,
            "options": {
                "num_ctx": max(2048, min(ctx_size, 16384)),
                "num_predict": max(128, min(int(num_predict), 2048)),
                "temperature": temperature,
            },
        }
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
                async with client.stream("POST", f"{DEFAULT_OLLAMA_URL}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                            if data.get("done"):
                                break
                        except Exception:
                            continue


def register_routes(app: FastAPI, manager: ModelProviderManager) -> None:
    @app.get("/api/settings/model")
    async def get_model_settings() -> dict[str, Any]:
        return manager.get_settings(include_secret=False)

    @app.post("/api/settings/model")
    async def update_model_settings(req: ModelSettingsUpdate) -> dict[str, Any]:
        return manager.update_settings(req)

    @app.post("/api/settings/model/test")
    async def test_model_connection() -> dict[str, Any]:
        route = manager.active_route()
        try:
            reply = await manager.chat(
                [{"role": "user", "content": "Reply with OK only."}],
                num_predict=64,
                temperature=0.0,
            )
            return {"ok": True, "mode": route["mode"], "model": route["model"], "reply": reply[:120]}
        except Exception as exc:
            raise HTTPException(502, f"Kiểm tra model thất bại ({route['mode']}/{route['model']}): {str(exc)[:260]}")
