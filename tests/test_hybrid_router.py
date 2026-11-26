# -*- coding: utf-8 -*-
"""Unit tests for Hybrid Routing in app/model_provider.py and app/chat_orchestrator.py."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app import chat_orchestrator, model_provider


def _make_manager(tmp_path: Path) -> model_provider.ModelProviderManager:
    db_path = tmp_path / "hybrid_test.db"

    def connect():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    return model_provider.ModelProviderManager(connect, asyncio.Semaphore(1))


def _enable_hybrid(mgr: model_provider.ModelProviderManager, *, with_cloud: bool = True) -> dict:
    if with_cloud:
        return mgr.update_settings(
            model_provider.ModelSettingsUpdate(
                provider="hybrid",
                cloud_enabled=True,
                cloud_base_url="https://api.example.com/v1",
                cloud_model="gpt-4o-mini",
                cloud_api_key="sk-hybrid-test-key-9999",
            )
        )
    return mgr.update_settings(
        model_provider.ModelSettingsUpdate(
            provider="hybrid",
            cloud_enabled=False,
        )
    )


# ---------------------------------------------------------------------------
# 1. Settings & Active Route Tests
# ---------------------------------------------------------------------------
def test_hybrid_provider_settings_and_active_route(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    updated = _enable_hybrid(mgr, with_cloud=True)
    assert updated["provider"] == "hybrid"
    assert updated["cloud_enabled"] is True

    route = mgr.active_route()
    assert route["mode"] == "hybrid"
    assert route["provider"] == "hybrid"
    assert route["cloud_ready"] is True
    assert route["local_model"] == model_provider.DEFAULT_LOCAL_MODEL
    assert route["cloud_model"] == "gpt-4o-mini"


def test_hybrid_unconfigured_cloud_falls_back_to_local(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    _enable_hybrid(mgr, with_cloud=False)

    route = mgr.active_route(
        [{"role": "user", "content": "Hãy lập kế hoạch kiến trúc microservices chi tiết"}]
    )
    assert route["mode"] == "local"
    assert route["model"] == model_provider.DEFAULT_LOCAL_MODEL
    assert route["cloud_ready"] is False


def test_hybrid_invalid_cloud_config_still_validated(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        mgr.update_settings(
            model_provider.ModelSettingsUpdate(provider="hybrid", cloud_enabled=True)
        )
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 2. Complexity & Privacy Classifier Tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "msg, expected_target",
    [
        ("xin chào", "local"),
        ("2 + 2 * 5", "local"),
        ("Mật khẩu wifi nhà tôi là gì, giữ riêng tư local only nhé", "local"),
        ("Đây là API key của tôi: sk-abc1234567890xyz, kiểm tra giúp", "local"),
        ("Lập kế hoạch kiến trúc hệ thống AI Office 6GB VRAM", "cloud"),
        ("Phân tích và so sánh trade-off giữa SQLite và PostgreSQL", "cloud"),
        ("Hãy review và QA đoạn code này tìm edge case", "cloud"),
    ],
)
def test_classify_chat_complexity(msg: str, expected_target: str):
    res = chat_orchestrator.classify_chat_complexity(msg)
    assert res["target"] == expected_target


def test_hybrid_active_route_per_message(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    _enable_hybrid(mgr, with_cloud=True)

    simple_route = mgr.active_route([{"role": "user", "content": "xin chào bạn"}])
    assert simple_route["mode"] == "local"
    assert simple_route["model"] == model_provider.DEFAULT_LOCAL_MODEL

    private_route = mgr.active_route(
        [{"role": "user", "content": "Phân tích file .env bí mật này giúp tôi (private)"}]
    )
    assert private_route["mode"] == "local"

    complex_route = mgr.active_route(
        [{"role": "user", "content": "Hãy lập kế hoạch QA và phân tích root cause lỗi VRAM"}]
    )
    assert complex_route["mode"] == "cloud"
    assert complex_route["model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# 3. End-to-End Routing & Cloud->Local Fallback Tests (Mocked HTTP)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hybrid_chat_routes_complex_to_cloud_and_simple_to_local(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    _enable_hybrid(mgr, with_cloud=True)

    called_urls: list[str] = []

    async def fake_post(self, url: str, **kwargs):
        called_urls.append(url)
        req = httpx.Request("POST", url)
        if "/chat/completions" in url:
            return httpx.Response(
                200,
                request=req,
                json={"choices": [{"message": {"content": "cloud-plan-reply"}}]},
            )
        return httpx.Response(
            200,
            request=req,
            json={"message": {"content": "local-fast-reply"}},
        )

    with patch.object(httpx.AsyncClient, "post", fake_post):
        complex_ans = await mgr.chat(
            [{"role": "user", "content": "Lập kế hoạch kiến trúc hệ thống và QA checklist"}]
        )
        simple_ans = await mgr.chat(
            [{"role": "user", "content": "hôm nay trời thế nào"}]
        )

    assert complex_ans == "cloud-plan-reply"
    assert simple_ans == "local-fast-reply"
    assert any("/chat/completions" in u for u in called_urls)
    assert any("/api/chat" in u for u in called_urls)


@pytest.mark.asyncio
async def test_hybrid_chat_falls_back_to_local_when_cloud_fails(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    _enable_hybrid(mgr, with_cloud=True)

    called_urls: list[str] = []

    async def fake_post(self, url: str, **kwargs):
        called_urls.append(url)
        req = httpx.Request("POST", url)
        if "/chat/completions" in url:
            raise httpx.ConnectError("Cloud unreachable", request=req)
        return httpx.Response(
            200,
            request=req,
            json={"message": {"content": "local-fallback-reply"}},
        )

    with patch.object(httpx.AsyncClient, "post", fake_post):
        ans = await mgr.chat(
            [{"role": "user", "content": "Phân tích kiến trúc và lập kế hoạch kiểm thử"}]
        )

    assert ans == "local-fallback-reply"
    assert len(called_urls) == 2
    assert "/chat/completions" in called_urls[0]
    assert "/api/chat" in called_urls[1]


@pytest.mark.asyncio
async def test_hybrid_chat_stream_falls_back_to_local_when_cloud_fails(tmp_path: Path):
    mgr = _make_manager(tmp_path)
    _enable_hybrid(mgr, with_cloud=True)

    class FakeStreamResponse:
        def __init__(self, lines: list[str], fail: bool = False):
            self._lines = lines
            self._fail = fail

        async def __aenter__(self):
            if self._fail:
                raise httpx.ConnectError("Cloud stream down")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in self._lines:
                yield line

    def fake_stream(self, method: str, url: str, **kwargs):
        if "/chat/completions" in url:
            return FakeStreamResponse([], fail=True)
        return FakeStreamResponse(
            [json.dumps({"message": {"content": "local-stream-ok"}, "done": True})]
        )

    with patch.object(httpx.AsyncClient, "stream", fake_stream):
        chunks = [
            c
            async for c in mgr.chat_stream(
                [{"role": "user", "content": "Hãy phân tích và review kế hoạch này"}]
            )
        ]

    assert chunks == ["local-stream-ok"]
