from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from app.security_guard import SecurityGuard
    from app.fast_calc import classify_prompt_speed
    from app.chat_orchestrator import classify_chat_complexity
except ImportError:
    from security_guard import SecurityGuard
    from fast_calc import classify_prompt_speed
    from chat_orchestrator import classify_chat_complexity

logger = logging.getLogger("model_provider")

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_LOCAL_MODEL = os.getenv("AI_OFFICE_MODEL", "qwen3.5:4b")


class ModelSettingsUpdate(BaseModel):
    provider: str | None = Field(default=None, pattern="^(local|cloud|hybrid)$")
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
            "local_num_ctx": 8192,
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
        defaults["local_num_ctx"] = max(2048, min(int(defaults.get("local_num_ctx") or 8192), 16384))
        defaults["cloud_enabled"] = bool(defaults.get("cloud_enabled", False))
        if defaults["provider"] not in {"local", "cloud", "hybrid"}:
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

    @staticmethod
    def _is_cloud_ready(cfg: dict[str, Any]) -> bool:
        return bool(
            cfg.get("cloud_enabled")
            and cfg.get("cloud_api_key")
            and cfg.get("cloud_base_url")
            and cfg.get("cloud_model")
        )

    @staticmethod
    def _extract_last_user_and_images(messages: list[dict[str, Any]]) -> tuple[str, bool]:
        last_user_text = ""
        has_images = False
        for m in messages:
            if m.get("images"):
                has_images = True
            content = m.get("content", "")
            if isinstance(content, list):
                if any(isinstance(p, dict) and p.get("type") == "image_url" for p in content):
                    has_images = True
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    last_user_text = content
                elif isinstance(content, list):
                    last_user_text = " ".join(
                        str(p.get("text", ""))
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ).strip()
                break
        return last_user_text, has_images

    def active_route(
        self,
        messages: list[dict[str, Any]] | None = None,
        *,
        task_type: str | None = None,
        prefer_local: bool = False,
        json_mode: bool = False,
        num_predict: int = 4096,
    ) -> dict[str, Any]:
        cfg = self.get_settings(include_secret=True)
        cloud_ready = self._is_cloud_ready(cfg)
        provider = cfg["provider"]
        reason = "configured_local"

        if provider == "cloud" and cloud_ready:
            mode = "cloud"
            model = cfg["cloud_model"]
            reason = "configured_cloud"
        elif provider == "hybrid":
            if not cloud_ready:
                mode = "local"
                model = cfg["local_model"]
                reason = "hybrid_cloud_unconfigured"
            elif messages is not None or task_type is not None or prefer_local:
                last_text, has_images = self._extract_last_user_and_images(messages or [])
                decision = classify_chat_complexity(
                    last_text,
                    has_images=has_images,
                    message_count=len(messages or []),
                    num_predict=num_predict,
                    json_mode=json_mode,
                    task_type=task_type,
                    prefer_local=prefer_local,
                )
                reason = decision["reason"]
                if decision["target"] == "cloud":
                    mode = "cloud"
                    model = cfg["cloud_model"]
                else:
                    mode = "local"
                    model = cfg["local_model"]
            else:
                mode = "hybrid"
                model = cfg["cloud_model"]
                reason = "hybrid_ready"
        else:
            mode = "local"
            model = cfg["local_model"]

        return {
            "mode": mode,
            "model": model,
            "provider": provider,
            "local_model": cfg["local_model"],
            "local_num_ctx": cfg["local_num_ctx"],
            "cloud_enabled": cfg["cloud_enabled"],
            "cloud_model": cfg["cloud_model"],
            "cloud_ready": cloud_ready,
            "route_reason": reason,
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
        if route["mode"] == "cloud" or (route["mode"] == "hybrid" and route["cloud_ready"]):
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

    def _sanitize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                cleaned = SecurityGuard.sanitize_input_text(content).cleaned_text
                sanitized.append({**msg, "content": cleaned})
            elif isinstance(content, list):
                # multi-part content
                clean_parts = []
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        text_val = p.get("text", "")
                        clean_parts.append({**p, "text": SecurityGuard.sanitize_input_text(text_val).cleaned_text})
                    else:
                        clean_parts.append(p)
                sanitized.append({**msg, "content": clean_parts})
            else:
                sanitized.append(msg)
        return sanitized

    @staticmethod
    def _build_local_options(ctx_size: int, num_predict: int, temperature: float, json_mode: bool = False) -> dict[str, Any]:
        # Long-form creative writing needs repeat_penalty and warmer temperature to avoid 4B verbatim paragraph loops.
        effective_temp = 0.65 if (not json_mode and num_predict >= 4096 and temperature <= 0.3) else temperature
        return {
            "num_ctx": max(2048, min(ctx_size, 16384)),
            "num_predict": max(128, min(int(num_predict), 16384)),
            "temperature": effective_temp,
            "repeat_penalty": 1.15,
            "repeat_last_n": 256,
        }

    async def _call_cloud_chat(
        self,
        cfg: dict[str, Any],
        clean_messages: list[dict[str, Any]],
        *,
        json_mode: bool,
        num_predict: int,
        temperature: float,
    ) -> str:
        endpoint = cfg["cloud_base_url"].rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": cfg["cloud_model"],
            "messages": self._to_openai_messages(clean_messages),
            "max_tokens": max(128, min(int(num_predict), 16384)),
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {cfg['cloud_api_key']}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=8.0)) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return ""
            return str(choices[0].get("message", {}).get("content", "") or "").strip()

    async def _call_local_chat(
        self,
        cfg: dict[str, Any],
        clean_messages: list[dict[str, Any]],
        *,
        json_mode: bool,
        num_predict: int,
        temperature: float,
        think: bool | None,
    ) -> str:
        ctx_size = int(cfg["local_num_ctx"])
        bounded_predict = min(num_predict, ctx_size // 2)
        model_name = str(cfg["local_model"]).lower()
        enable_think = think if think is not None else bool("r1" in model_name or "claude" in model_name)
        payload: dict[str, Any] = {
            "model": cfg["local_model"],
            "messages": clean_messages,
            "stream": False,
            "keep_alive": "24h",
            "think": enable_think,
            "options": self._build_local_options(ctx_size, bounded_predict, temperature, json_mode=json_mode),
        }
        if json_mode:
            payload["format"] = "json"
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=5.0)) as client:
                response = await client.post(f"{DEFAULT_OLLAMA_URL}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                return str(data.get("message", {}).get("content", "") or "").strip()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
        num_predict: int = 4096,
        num_ctx: int | None = None,
        temperature: float = 0.25,
        think: bool | None = None,
        task_type: str | None = None,
        prefer_local: bool = False,
    ) -> str:
        clean_messages = self._sanitize_messages(messages)

        # Check for instant math or fast-path greetings
        last_user_text, _ = self._extract_last_user_and_images(clean_messages)
        if last_user_text:
            decision = classify_prompt_speed(last_user_text)
            if decision.is_math and decision.math_result:
                return decision.math_result
            if decision.is_simple_query and think is None:
                think = False
                num_predict = min(num_predict, decision.recommended_num_predict)
            elif decision.recommended_num_predict > num_predict:
                num_predict = decision.recommended_num_predict

        cfg = self.get_settings(include_secret=True)
        route = self.active_route(
            clean_messages,
            task_type=task_type,
            prefer_local=prefer_local,
            json_mode=json_mode,
            num_predict=num_predict,
        )
        if route["mode"] == "cloud":
            try:
                return await self._call_cloud_chat(
                    cfg,
                    clean_messages,
                    json_mode=json_mode,
                    num_predict=num_predict,
                    temperature=temperature,
                )
            except Exception as exc:
                if cfg["provider"] != "hybrid":
                    raise
                logger.warning("Hybrid cloud chat failed (%s), falling back to local Ollama.", exc)

        return await self._call_local_chat(
            cfg,
            clean_messages,
            json_mode=json_mode,
            num_predict=num_predict,
            temperature=temperature,
            think=think,
        )

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
                    json={
                        "model": target_model,
                        "keep_alive": "24h",
                        "options": {"num_ctx": int(cfg["local_num_ctx"])},
                    },
                )
                return res.status_code == 200
        except Exception:
            return False

    async def _stream_cloud_chat(
        self,
        cfg: dict[str, Any],
        clean_messages: list[dict[str, Any]],
        *,
        num_predict: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        endpoint = cfg["cloud_base_url"].rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": cfg["cloud_model"],
            "messages": self._to_openai_messages(clean_messages),
            "max_tokens": max(128, min(int(num_predict), 16384)),
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {cfg['cloud_api_key']}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=8.0)) as client:
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

    async def _stream_local_chat(
        self,
        cfg: dict[str, Any],
        clean_messages: list[dict[str, Any]],
        *,
        num_predict: int,
        temperature: float,
        think: bool | None,
    ) -> AsyncGenerator[str, None]:
        ctx_size = int(cfg["local_num_ctx"])
        bounded_predict = min(num_predict, ctx_size // 2)
        model_name = str(cfg["local_model"]).lower()
        enable_think = think if think is not None else bool("r1" in model_name or "claude" in model_name)
        payload = {
            "model": cfg["local_model"],
            "messages": clean_messages,
            "stream": True,
            "keep_alive": "24h",
            "think": enable_think,
            "options": self._build_local_options(ctx_size, bounded_predict, temperature, json_mode=False),
        }
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=5.0)) as client:
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

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        num_predict: int = 4096,
        num_ctx: int | None = None,
        temperature: float = 0.25,
        think: bool | None = None,
        task_type: str | None = None,
        prefer_local: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens in real-time from local Ollama or OpenAI-compatible cloud."""
        clean_messages = self._sanitize_messages(messages)

        # Check for instant math or fast-path greetings
        last_user_text, _ = self._extract_last_user_and_images(clean_messages)
        if last_user_text:
            decision = classify_prompt_speed(last_user_text)
            if decision.is_math and decision.math_result:
                yield decision.math_result
                return
            if decision.is_simple_query and think is None:
                think = False
                num_predict = min(num_predict, decision.recommended_num_predict)
            elif decision.recommended_num_predict > num_predict:
                num_predict = decision.recommended_num_predict

        cfg = self.get_settings(include_secret=True)
        route = self.active_route(
            clean_messages,
            task_type=task_type,
            prefer_local=prefer_local,
            json_mode=False,
            num_predict=num_predict,
        )
        if route["mode"] == "cloud":
            yielded = False
            try:
                async for chunk in self._stream_cloud_chat(
                    cfg,
                    clean_messages,
                    num_predict=num_predict,
                    temperature=temperature,
                ):
                    yielded = True
                    yield chunk
                return
            except Exception as exc:
                if cfg["provider"] != "hybrid" or yielded:
                    raise
                logger.warning("Hybrid cloud stream failed (%s), falling back to local Ollama.", exc)

        async for chunk in self._stream_local_chat(
            cfg,
            clean_messages,
            num_predict=num_predict,
            temperature=temperature,
            think=think,
        ):
            yield chunk


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
