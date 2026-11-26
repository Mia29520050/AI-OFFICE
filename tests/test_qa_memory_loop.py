"""Unit tests for Self-Learning Golden Templates & Auto-QA Loop."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import chat_image_handler, memory_engine


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch) -> Path:
    """Isolated SQLite DB for memory_engine tests."""
    db_file = tmp_path / "qa_memory_test.db"
    memory_engine.init_memory_db(db_file)
    monkeypatch.setattr(memory_engine, "get_db_path", lambda: db_file)
    return db_file


def _make_valid_png(path: Path, width: int = 768, height: int = 1024) -> Path:
    """Create a non-blank valid PNG image for PIL QA checks."""
    img = Image.new("RGB", (width, height), color=(30, 40, 60))
    draw = ImageDraw.Draw(img)
    draw.rectangle([width // 4, height // 4, width * 3 // 4, height * 3 // 4], fill=(220, 120, 80))
    img.save(path, format="PNG")
    return path


def _make_blank_png(path: Path, width: int = 768, height: int = 1024) -> Path:
    """Create a completely uniform blank PNG image that should fail Auto-QA."""
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    img.save(path, format="PNG")
    return path


def test_golden_template_save_recall_and_priority(temp_db: Path):
    """Golden Templates should deduplicate, track success_count, and outrank normal facts."""
    memory_engine.learn_fact(
        content="Hu Tao là nhân vật trong Genshin Impact.",
        category="fact",
        importance=3,
        db_path=temp_db,
    )
    tpl1 = memory_engine.save_golden_template(
        task_key="Hu Tao",
        template_content="1girl, Hu Tao, twintails, flower-shaped pupils, vibrant anime, cel shading",
        metadata={"steps": 25, "cfg": 4.5, "aspect_ratio": "3:4"},
        db_path=temp_db,
    )
    assert tpl1 is not None
    assert tpl1["category"] == "golden_template"
    assert tpl1["importance"] == 5
    assert tpl1["success_count"] == 1

    # Reinforce same template -> same row, success_count == 2
    tpl2 = memory_engine.save_golden_template(
        task_key="Hu Tao",
        template_content="1girl, Hu Tao, twintails, flower-shaped pupils, vibrant anime, cel shading",
        db_path=temp_db,
    )
    assert tpl2 is not None
    assert tpl2["id"] == tpl1["id"]
    assert tpl2["success_count"] == 2
    assert json.loads(tpl2["metadata_json"])["steps"] == 25

    recalled = memory_engine.recall_relevant_memories("Hu Tao", limit=5, db_path=temp_db)
    assert len(recalled) >= 2
    assert recalled[0]["category"] == "golden_template"

    templates = memory_engine.recall_golden_templates("Hu Tao", limit=3, db_path=temp_db)
    assert len(templates) == 1
    assert templates[0]["id"] == tpl1["id"]

    block = memory_engine.build_memory_context_block("Hu Tao", limit=5, db_path=temp_db)
    assert "[Mẫu chuẩn]" in block
    assert len(block) <= 500


def test_record_qa_feedback_promotes_and_demotes(temp_db: Path):
    """Pass feedback promotes Golden Templates; repeated fail feedback demotes them."""
    tpl = memory_engine.record_qa_feedback(
        task_key="Raiden Shogun",
        success=True,
        details="Passed on attempt 1",
        template_content="1girl, Raiden Shogun, purple braid, electro aura, masterpiece",
        metadata={"steps": 25, "cfg": 4.5},
        db_path=temp_db,
    )
    assert tpl is not None
    assert tpl["category"] == "golden_template"
    assert tpl["success_count"] == 1
    assert tpl["importance"] == 5

    # Record two failures against the same template -> fail_count=2 > success_count=1 -> demoted
    memory_engine.record_qa_feedback(
        task_key="Raiden Shogun",
        success=False,
        details="blank_or_uniform_image",
        template_content="1girl, Raiden Shogun, purple braid, electro aura, masterpiece",
        db_path=temp_db,
    )
    fail_rec = memory_engine.record_qa_feedback(
        task_key="Raiden Shogun",
        success=False,
        details="blank_or_uniform_image",
        template_content="1girl, Raiden Shogun, purple braid, electro aura, masterpiece",
        db_path=temp_db,
    )
    assert fail_rec is not None
    assert fail_rec["category"] == "qa_feedback"
    assert fail_rec["fail_count"] >= 1

    # Demoted template should be filtered out by recall_golden_templates (net score = 1 - 2 = -1,
    # wait: default min_net_score=-1 allows -1, so let's record one more fail to drop to -2)
    memory_engine.record_qa_feedback(
        task_key="Raiden Shogun",
        success=False,
        details="corrupt_image",
        template_content="1girl, Raiden Shogun, purple braid, electro aura, masterpiece",
        db_path=temp_db,
    )
    reliable = memory_engine.recall_golden_templates("Raiden Shogun", limit=3, db_path=temp_db)
    assert reliable == []


def test_golden_template_fastapi_routes(temp_db: Path):
    """Test GET and POST /api/memory/templates routes."""
    app = FastAPI()
    memory_engine.register_routes(app)
    client = TestClient(app)

    post_res = client.post(
        "/api/memory/templates",
        json={
            "task_key": "Furina",
            "template_content": "1girl, Furina, blue hair, heterochromia, top hat, anime",
            "importance": 5,
            "metadata": {"aspect_ratio": "3:4", "steps": 25},
        },
    )
    assert post_res.status_code == 200
    assert post_res.json()["template"]["category"] == "golden_template"

    get_res = client.get("/api/memory/templates?query=Furina")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["count"] == 1
    assert "Furina" in data["templates"][0]["content"]


def test_validate_generated_image_qa_cases(tmp_path: Path):
    """Validate Auto-QA checks for valid, blank, empty, corrupt, and stub images."""
    valid_png = _make_valid_png(tmp_path / "valid.png", 768, 1024)
    res_ok = chat_image_handler.validate_generated_image_qa(
        image_path=valid_png,
        expected_width=768,
        expected_height=1024,
        positive_prompt="1girl, Hu Tao, masterpiece, best quality",
    )
    assert res_ok["passed"] is True
    assert res_ok["score"] == 1.0
    assert res_ok["issues"] == []

    blank_png = _make_blank_png(tmp_path / "blank.png", 768, 1024)
    res_blank = chat_image_handler.validate_generated_image_qa(
        image_path=blank_png,
        expected_width=768,
        expected_height=1024,
        positive_prompt="1girl, Hu Tao, masterpiece",
    )
    assert res_blank["passed"] is False
    assert "blank_or_uniform_image" in res_blank["issues"]

    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")
    res_empty = chat_image_handler.validate_generated_image_qa(
        image_path=empty_file,
        expected_width=768,
        expected_height=1024,
        positive_prompt="1girl, Hu Tao, masterpiece",
    )
    assert res_empty["passed"] is False
    assert "empty_output_file" in res_empty["issues"]

    bad_sig = tmp_path / "bad.png"
    bad_sig.write_bytes(b"<html>error</html>" * 20)
    res_sig = chat_image_handler.validate_generated_image_qa(
        image_path=bad_sig,
        expected_width=768,
        expected_height=1024,
        positive_prompt="1girl, Hu Tao, masterpiece",
    )
    assert res_sig["passed"] is False
    assert "invalid_image_signature" in res_sig["issues"]

    # Synthetic stub (<256 bytes with valid PNG header) should pass
    stub_png = tmp_path / "stub.png"
    stub_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    res_stub = chat_image_handler.validate_generated_image_qa(
        image_path=stub_png,
        expected_width=768,
        expected_height=1024,
        positive_prompt="1girl, Hu Tao, masterpiece",
    )
    assert res_stub["passed"] is True
    assert res_stub["metrics"].get("stub_image") is True


@pytest.mark.asyncio
async def test_run_comfy_with_auto_qa_bounded_retry(tmp_path: Path, temp_db: Path):
    """Auto-QA should retry once on blank output, adjust steps/cfg, and record pass/fail."""
    blank_png = _make_blank_png(tmp_path / "attempt1_blank.png", 768, 1024)
    valid_png = _make_valid_png(tmp_path / "attempt2_valid.png", 768, 1024)

    calls = []

    async def _fake_run_comfy(**kwargs):
        calls.append(kwargs)
        return blank_png if len(calls) == 1 else valid_png

    with patch.object(chat_image_handler, "run_comfy_workflow", side_effect=_fake_run_comfy):
        out_path, qa = await chat_image_handler.run_comfy_with_auto_qa(
            positive_prompt="1girl, Citlali, anime style",
            negative_prompt="bad quality",
            task_key="Citlali",
            max_retries=2,
            width=768,
            height=1024,
            steps=25,
            cfg=4.5,
        )

    assert out_path == valid_png
    assert len(calls) == 2
    assert calls[1]["steps"] > calls[0]["steps"]
    assert calls[1]["cfg"] > calls[0]["cfg"]
    assert qa["passed"] is True
    assert qa["attempts"] == 2
    assert qa["retried"] is True

    # Verify both fail feedback and golden_template pass were recorded in memory_engine
    fails = memory_engine.list_memories(category="qa_feedback", db_path=temp_db)
    templates = memory_engine.recall_golden_templates("Citlali", db_path=temp_db)
    assert len(fails) == 1
    assert fails[0]["fail_count"] == 1
    assert len(templates) == 1
    assert templates[0]["success_count"] == 1


@pytest.mark.asyncio
async def test_run_comfy_with_auto_qa_respects_max_retries_bound(tmp_path: Path, temp_db: Path):
    """Even if max_retries=99 is passed, retries are bounded to max 2 (3 total attempts)."""
    call_count = 0

    async def _always_fail(**kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("ComfyUI temporary error")

    with patch.object(chat_image_handler, "run_comfy_workflow", side_effect=_always_fail):
        with pytest.raises(RuntimeError, match="ComfyUI temporary error"):
            await chat_image_handler.run_comfy_with_auto_qa(
                positive_prompt="1girl, Aether, anime",
                negative_prompt="bad quality",
                task_key="Aether",
                max_retries=99,
            )

    assert call_count == 3  # 1 initial + 2 bounded retries


@pytest.mark.asyncio
async def test_handle_chat_image_generation_recalls_golden_template_and_records_qa(tmp_path: Path, temp_db: Path, monkeypatch):
    """End-to-end handle_chat_image_generation uses Golden Templates and records Auto-QA pass."""
    export_dir = tmp_path / "Export" / "Images"
    export_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(chat_image_handler, "EXPORT_IMAGES_DIR", export_dir)

    # Pre-seed a Golden Template for Nahida
    memory_engine.save_golden_template(
        task_key="Nahida",
        template_content="glowing dendro aura, crisp cel shading",
        db_path=temp_db,
    )

    valid_png = _make_valid_png(tmp_path / "nahida_gen.png", 768, 1024)
    captured_kwargs = {}

    async def _fake_run_comfy(**kwargs):
        captured_kwargs.update(kwargs)
        return valid_png

    fake_char = SimpleNamespace(
        display_name="Nahida",
        franchise="Genshin Impact",
        hair_tags="white hair, green tips",
        eye_tags="green eyes",
        face_tags="gentle smile",
        outfit_tags="white and green dress",
        weapon_tags="dendro catalyst",
        danbooru_prompt="1girl, nahida, white hair, green eyes",
        negative_prompt="bad anatomy",
    )

    with patch.object(chat_image_handler, "auto_research_character", return_value=fake_char), \
         patch.object(chat_image_handler, "ensure_comfy_online", return_value=True), \
         patch.object(chat_image_handler, "run_comfy_workflow", side_effect=_fake_run_comfy):
        res = await chat_image_handler.handle_chat_image_generation("vẽ ảnh Nahida")

    assert res["success"] is True
    assert "glowing dendro aura" in captured_kwargs["positive_prompt"]
    assert res["qa"]["passed"] is True
    assert res["qa"]["attempts"] == 1
