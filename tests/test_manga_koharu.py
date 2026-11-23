from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.manga_koharu import KoharuSidecarClient, KoharuHealthStatus


@pytest.mark.asyncio
async def test_koharu_health_offline():
    client = KoharuSidecarClient(base_url="http://127.0.0.1:9999")
    status = await client.get_health()
    assert status.is_online is False


@pytest.mark.asyncio
async def test_koharu_health_online():
    client = KoharuSidecarClient()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "version": "1.2.0",
        "device": "cuda:0",
        "vram_usage_mb": 1420.5,
        "models_loaded": ["comic-text-detector", "lama"],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        status = await client.get_health()
        assert status.is_online is True
        assert status.version == "1.2.0"
        assert status.device == "cuda:0"
        assert status.vram_usage_mb == 1420.5


@pytest.mark.asyncio
async def test_koharu_inpaint_scheduler_lock():
    # Verify ResourceScheduler lock is properly acquired
    mock_scheduler = MagicMock()
    mock_lock_ctx = AsyncMock()
    mock_scheduler.acquire.return_value = mock_lock_ctx

    client = KoharuSidecarClient(scheduler=mock_scheduler)

    with patch.object(client, "get_health", return_value=KoharuHealthStatus(is_online=True)):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(status_code=200, content=b"inpainted_png")
            res = await client.inpaint(b"raw_image", b"mask_image")
            assert res == b"inpainted_png"
            mock_scheduler.acquire.assert_called_once_with("koharu_inpaint")
