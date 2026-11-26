"""Unit tests for AI Office Long-Term & Self-Learning Memory Engine.

Tests SQLite WAL initialization, auto-deduplication, intent extraction from chat turns,
relevance scoring, compact prompt block generation (< 500 chars), and FastAPI routes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.memory_engine import (
    build_memory_context_block,
    delete_memory,
    detect_and_learn_from_turn,
    get_connection,
    init_memory_db,
    learn_fact,
    list_memories,
    recall_relevant_memories,
    register_routes,
    VALID_CATEGORIES,
)


@pytest.fixture
def temp_db(tmp_path: Path):
    """Provide a temporary database path for test isolation."""
    db_file = tmp_path / "test_office.db"
    init_memory_db(db_file)
    return db_file


def test_sqlite_wal_init(temp_db: Path):
    """Verify SQLite WAL mode and table schema creation."""
    conn = get_connection(temp_db)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode;")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_memories';")
        assert cur.fetchone() is not None

        # Verify indexes
        cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = [r[0] for r in cur.fetchall()]
        assert "idx_learned_memories_cat" in indexes
        assert "idx_learned_memories_imp" in indexes
    finally:
        conn.close()


def test_learn_fact_and_deduplication(temp_db: Path):
    """Test saving memories and automatic deduplication/update."""
    # 1. Insert new fact
    mem1 = learn_fact(
        content="Anh thích màu xanh lam đậm",
        category="preference",
        source="chat",
        importance=3,
        db_path=temp_db,
    )
    assert mem1 is not None
    assert mem1["id"] is not None
    assert mem1["category"] == "preference"
    assert mem1["importance"] == 3
    assert "xanh" in mem1["keywords"] or "lam" in mem1["keywords"]

    # 2. Re-insert same content with higher importance -> should update, not create duplicate
    mem2 = learn_fact(
        content="  anh thích màu xanh lam đậm   ",
        category="preference",
        source="chat",
        importance=5,
        db_path=temp_db,
    )
    assert mem2["id"] == mem1["id"]
    assert mem2["importance"] == 5

    # Check total count in DB is still 1
    all_mems = list_memories(db_path=temp_db)
    assert len(all_mems) == 1

    # 3. Invalid category defaults to 'fact'
    mem3 = learn_fact(
        content="Sự kiện ra mắt sản phẩm",
        category="invalid_category_test",
        db_path=temp_db,
    )
    assert mem3["category"] == "fact"

    # 4. Empty content returns None
    assert learn_fact("   ", db_path=temp_db) is None


def test_detect_and_learn_from_turn_preference(temp_db: Path):
    """Test extracting user preferences from natural conversational phrases."""
    user_msg = "Chào em, anh thích phong cách cyberpunk tương lai với ánh sáng neon."
    learned = detect_and_learn_from_turn(user_msg, "", db_path=temp_db)
    assert len(learned) >= 1
    found = any(m["category"] == "preference" and "cyberpunk" in m["content"].lower() for m in learned)
    assert found


def test_detect_and_learn_from_turn_correction(temp_db: Path):
    """Test extracting user rules and corrections."""
    user_msg = "Từ nay đừng bao giờ trả lời quá 3 câu, hãy luôn tóm tắt thật ngắn."
    learned = detect_and_learn_from_turn(user_msg, "", db_path=temp_db)
    assert len(learned) >= 1
    assert any(m["category"] == "correction" for m in learned)


def test_detect_and_learn_from_turn_explicit_remember(temp_db: Path):
    """Test extracting explicit remember triggers."""
    user_msg = "Nhớ giúp anh là server staging chạy ở port 9090."
    learned = detect_and_learn_from_turn(user_msg, "", db_path=temp_db)
    assert len(learned) >= 1
    assert any("port 9090" in m["content"] for m in learned)


def test_detect_and_learn_from_turn_character_style(temp_db: Path):
    """Test extracting character / art style notes."""
    user_msg = "Style của nhân vật là: kimono đen truyền thống, mắt hổ phách, tóc bạch kim dài."
    learned = detect_and_learn_from_turn(user_msg, "", db_path=temp_db)
    assert len(learned) >= 1
    assert any(m["category"] == "character_style" for m in learned)


def test_detect_and_learn_web_knowledge(temp_db: Path):
    """Test learning from assistant turns containing web research citations."""
    user_msg = "Cập nhật giá card RTX 4060 hiện nay?"
    assistant_msg = (
        "🔍 Tìm kiếm: Giá card đồ họa RTX 4060 tháng 11/2026\n"
        "[Nguồn tra cứu: Phong Vũ, GearVN]\n"
        "- Giá tham khảo RTX 4060 8GB dao động từ 7.8 triệu đến 8.5 triệu VNĐ.\n"
        "- Bản 16GB có mức giá khoảng 11 triệu VNĐ."
    )
    learned = detect_and_learn_from_turn(user_msg, assistant_msg, db_path=temp_db)
    assert len(learned) >= 1
    web_mem = next((m for m in learned if m["category"] == "web_knowledge"), None)
    assert web_mem is not None
    assert "RTX 4060" in web_mem["content"]
    assert web_mem["source"] == "web_search"


def test_recall_relevant_memories(temp_db: Path):
    """Test keyword matching, ranking, and scoring."""
    learn_fact("Thích phong cách vẽ manga shoujo lãng mạn", "preference", importance=4, db_path=temp_db)
    learn_fact("Thích uống cà phê espresso không đường", "preference", importance=3, db_path=temp_db)
    learn_fact("Quy tắc: Luôn code bằng Python 3.12+ và dùng type annotations", "correction", importance=5, db_path=temp_db)
    learn_fact("Nhân vật Raiden Shogun dùng naginata lôi điện", "character_style", importance=4, db_path=temp_db)

    # Search for coffee
    results = recall_relevant_memories("cà phê", limit=2, db_path=temp_db)
    assert len(results) >= 1
    assert "cà phê" in results[0]["content"].lower()

    # Search for Raiden
    raiden_res = recall_relevant_memories("Raiden Shogun", limit=2, db_path=temp_db)
    assert len(raiden_res) >= 1
    assert "raiden" in raiden_res[0]["content"].lower()

    # Generic or wildcard recall
    all_res = recall_relevant_memories("", limit=10, db_path=temp_db)
    assert len(all_res) == 4
    # Highest importance (5) should be first
    assert all_res[0]["importance"] == 5


def test_build_memory_context_block_compact(temp_db: Path):
    """Verify memory context block formatting and strict < 500 chars limit."""
    # When no memories match
    empty_block = build_memory_context_block("máy bay phản lực siêu thanh", limit=5, db_path=temp_db)
    assert empty_block == ""

    # Populate several memories
    for i in range(10):
        learn_fact(
            f"Thông tin quan trọng số {i}: Người dùng đang nghiên cứu giải thuật AI deep learning tối ưu VRAM cho model 4B.",
            category="fact",
            importance=4,
            db_path=temp_db,
        )

    block = build_memory_context_block("AI", limit=8, db_path=temp_db)
    assert len(block) > 0
    assert len(block) <= 500
    assert "[Ký ức & Sở thích người dùng]:" in block


def test_fastapi_routes(temp_db: Path, monkeypatch):
    """Test GET, POST, and DELETE memory routes."""
    # Redirect default DB to temp_db
    monkeypatch.setattr("app.memory_engine.get_db_path", lambda: temp_db)

    test_app = FastAPI()
    register_routes(test_app)
    client = TestClient(test_app)

    # 1. POST /api/memory/learn
    post_res = client.post(
        "/api/memory/learn",
        json={
            "content": "Luôn giải thích mã nguồn bằng tiếng Việt",
            "category": "preference",
            "source": "api_test",
            "importance": 5,
        },
    )
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["status"] == "success"
    item_id = data["memory"]["id"]
    assert item_id is not None

    # 2. GET /api/memory
    get_res = client.get("/api/memory")
    assert get_res.status_code == 200
    mems = get_res.json()["memories"]
    assert len(mems) == 1
    assert mems[0]["id"] == item_id

    # 3. GET /api/memory with search query
    search_res = client.get("/api/memory?query=tiếng+Việt")
    assert search_res.status_code == 200
    assert len(search_res.json()["memories"]) == 1

    # 4. DELETE /api/memory/{item_id}
    del_res = client.delete(f"/api/memory/{item_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # 5. DELETE again -> 404
    del_404 = client.delete(f"/api/memory/{item_id}")
    assert del_404.status_code == 404

    # 6. POST with empty content -> 400
    post_empty = client.post("/api/memory/learn", json={"content": "  "})
    assert post_empty.status_code == 422 or post_empty.status_code == 400
