from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path

import pytest
from PIL import Image

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from manga_comfy import (
    ComfyAdapter,
    PanelArtRequest,
    PanelArtResult,
    JobStatus,
    GenerationMode,
    MockReason,
    ResourceScheduler,
    ModelRegistryManager,
    WorkflowDiscovery,
    MockPanelGenerator,
    register_comfy_routes,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def temp_env(tmp_path: Path):
    db_file = tmp_path / "test_office.db"
    manga_dir = tmp_path / "manga"
    fake_comfy = tmp_path / "comfy"

    # Set up mock ComfyUI model dirs
    (fake_comfy / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    (fake_comfy / "models" / "diffusion_models").mkdir(parents=True, exist_ok=True)
    (fake_comfy / "models" / "loras").mkdir(parents=True, exist_ok=True)
    (fake_comfy / "models" / "vae").mkdir(parents=True, exist_ok=True)
    (fake_comfy / "user" / "default" / "workflows").mkdir(parents=True, exist_ok=True)

    adapter = ComfyAdapter(
        base_url="http://127.0.0.1:58188",
        comfy_path=fake_comfy,
        manga_dir=manga_dir,
        db_path=db_file,
    )
    return {
        "adapter": adapter,
        "db_file": db_file,
        "manga_dir": manga_dir,
        "fake_comfy": fake_comfy,
    }


def test_tables_and_initialization(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    with adapter.get_db() as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "manga_art_jobs" in tables
        assert "manga_assets" in tables


def test_workflow_discovery_builtins(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    workflows = adapter.discover_workflows()
    wf_ids = {w.id for w in workflows}
    assert "builtin_manga_bw" in wf_ids
    assert "builtin_manga_color" in wf_ids
    assert "builtin_wan_video_preview" in wf_ids
    assert "builtin_anima_turbo_gguf" in wf_ids
    assert "builtin_anima_ref_adapter" in wf_ids
    assert "builtin_z_anime_lowvram" in wf_ids

    bw_wf = next(w for w in workflows if w.id == "builtin_manga_bw")
    assert bw_wf.category == "manga_bw"
    assert bw_wf.is_builtin is True

    anima_ref = next(w for w in workflows if w.id == "builtin_anima_ref_adapter")
    assert anima_ref.category == "character_consistency"
    assert "AnimaRefAdapterApply" in anima_ref.required_models


def test_anime_architecture_profiles_and_budget(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    profiles = adapter.get_anime_architecture_profiles()
    assert "anima_turbo_gguf_q4" in profiles
    assert "anima_ref_adapter_kv" in profiles
    assert "z_anime_6b_q4" in profiles
    assert "qwen_anime_20b_fp16" in profiles

    # Anima-Turbo Q4 on 6GB VRAM must evaluate as OPTIMAL
    eval_turbo = adapter.evaluate_hardware_budget("anima_turbo_gguf_q4", vram_mb=6144.0)
    assert eval_turbo["status"] == "OPTIMAL"
    assert eval_turbo["feasibility_6gb_vram"] == "EXCELLENT"
    assert eval_turbo["vram_headroom_mb"] > 2000.0

    # Z-Anime 6B must evaluate as CONSTRAINED
    eval_z = adapter.evaluate_hardware_budget("z_anime_6b_q4", vram_mb=6144.0)
    assert eval_z["status"] == "CONSTRAINED"
    assert eval_z["feasibility_6gb_vram"] == "BORDERLINE"

    # Qwen-Anime 20B must evaluate as EXCEEDS_HARDWARE
    eval_qwen = adapter.evaluate_hardware_budget("qwen_anime_20b_fp16", vram_mb=6144.0)
    assert eval_qwen["status"] == "EXCEEDS_HARDWARE"
    assert eval_qwen["feasibility_6gb_vram"] == "INCOMPATIBLE"


def test_anima_ref_adapter_prompt_graph_builder(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    req = PanelArtRequest(
        panel_id="panel_ref_test",
        prompt="Minh walking through school hallway wearing dark blazer",
        seed=101010,
        character_refs=[{"image_path": "data/manga/projects/test/characters/minh.png"}],
    )
    graph = adapter.workflow_discovery.build_prompt_graph(
        req, model_name="anima-turbo-q4_k_m.gguf", workflow_id="builtin_anima_ref_adapter"
    )
    assert "8" in graph
    assert graph["8"]["class_type"] == "AnimaRefAdapterApply"
    assert graph["8"]["inputs"]["rope_offset_x"] == 1000
    assert graph["8"]["inputs"]["cache_kv"] is True
    assert graph["11"]["class_type"] == "VAEDecodeTiled"


def test_model_registry_without_checkpoints(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    registry = adapter.get_model_registry()
    assert registry.has_2d_manga_checkpoint is False
    assert len(registry.checkpoints) == 0


def test_model_registry_with_2d_checkpoints(temp_env):
    fake_comfy: Path = temp_env["fake_comfy"]
    ckpt_dir = fake_comfy / "models" / "checkpoints"
    (ckpt_dir / "animagine_xl_3.1.safetensors").write_bytes(b"dummy")
    (ckpt_dir / "photoreal_v1.safetensors").write_bytes(b"dummy")

    diff_dir = fake_comfy / "models" / "diffusion_models"
    (diff_dir / "wan_1.3B_exp_e14.safetensors").write_bytes(b"dummy")

    adapter: ComfyAdapter = temp_env["adapter"]
    registry = adapter.get_model_registry()
    assert registry.has_2d_manga_checkpoint is True
    assert registry.active_checkpoint == "animagine_xl_3.1.safetensors"
    assert len(registry.checkpoints) == 2
    assert len(registry.diffusion_models) == 1


def test_offline_system_stats(temp_env):
    async def _run():
        adapter: ComfyAdapter = temp_env["adapter"]
        stats = await adapter.get_system_stats()
        assert stats.is_online is False
        assert stats.recommended_mode == "mock"
        assert "offline" in stats.hardware_warning.lower()

    asyncio.run(_run())


def test_resource_scheduler_strict_concurrency():
    async def _run():
        scheduler = ResourceScheduler(max_concurrent=1)
        concurrent_count = 0
        max_observed = 0

        async def worker(job_id: str):
            nonlocal concurrent_count, max_observed
            async with scheduler.acquire(job_id, timeout_secs=10.0):
                concurrent_count += 1
                max_observed = max(max_observed, concurrent_count)
                await asyncio.sleep(0.05)
                concurrent_count -= 1

        await asyncio.gather(
            worker("job1"),
            worker("job2"),
            worker("job3"),
        )
        assert max_observed == 1

    asyncio.run(_run())


def test_resource_scheduler_external_semaphore():
    async def _run():
        external_sem = asyncio.Semaphore(1)
        scheduler = ResourceScheduler(max_concurrent=1, external_semaphore=external_sem)

        # Acquire external semaphore first
        await external_sem.acquire()
        assert external_sem.locked()

        # Attempting to acquire scheduler lock with short timeout must fail cleanly
        with pytest.raises(TimeoutError):
            async with scheduler.acquire("job_timeout", timeout_secs=0.2):
                pass

        external_sem.release()

        # Now it should succeed
        acquired = False
        async with scheduler.acquire("job_ok", timeout_secs=2.0):
            acquired = True
        assert acquired is True

    asyncio.run(_run())


def test_mock_panel_generator_bw(temp_env, tmp_path: Path):
    generator = MockPanelGenerator()
    req = PanelArtRequest(
        panel_id="p01",
        series_id="s_test",
        chapter_id="c01",
        page_id="pg01",
        prompt="Ren stands in front of the classroom window with sakura petals drifting in the wind",
        seed=424242,
        width=512,
        height=768,
        art_style="manga_bw",
    )
    out_file = tmp_path / "panel_bw.png"
    saved_path, checksum, file_size = generator.generate(req, out_file, MockReason.OFFLINE)

    assert saved_path.exists()
    assert file_size > 0
    assert len(checksum) == 64

    # Verify PIL can open and dimensions match
    with Image.open(saved_path) as im:
        assert im.size == (512, 768)
        assert im.mode == "RGB"


def test_mock_panel_generator_color(temp_env, tmp_path: Path):
    generator = MockPanelGenerator()
    req = PanelArtRequest(
        panel_id="p02",
        series_id="s_test",
        chapter_id="c01",
        page_id="pg01",
        prompt="Sunset over the academy rooftop, vivid anime sky, warm glowing light",
        seed=12345,
        width=600,
        height=800,
        art_style="manga_color",
    )
    out_file = tmp_path / "panel_color.png"
    saved_path, checksum, file_size = generator.generate(req, out_file, MockReason.NO_CHECKPOINT)

    assert saved_path.exists()
    with Image.open(saved_path) as im:
        assert im.size == (600, 800)


def test_generate_panel_art_offline_fallback(temp_env):
    async def _run():
        adapter: ComfyAdapter = temp_env["adapter"]
        req = PanelArtRequest(
            panel_id="panel_test_101",
            series_id="moonlight",
            chapter_id="ch01",
            page_id="page01",
            prompt="High school detective inspecting mysterious chalk drawing on blackboard",
            seed=999,
            width=512,
            height=512,
            art_style="manga_bw",
        )
        result: PanelArtResult = await adapter.generate_panel_art(req)

        assert result.status == JobStatus.COMPLETED.value
        assert result.mode == GenerationMode.MOCK.value
        assert result.mock_reason == MockReason.OFFLINE.value
        assert Path(result.image_path).exists()
        assert result.checksum != ""
        assert result.seed == 999

        # Verify recorded in DB
        job = adapter.get_job(result.job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED.value
        assert job.mode == GenerationMode.MOCK.value
        assert job.seed == 999
        assert job.width == 512
        assert job.output_asset_path == result.image_path

    asyncio.run(_run())


def test_job_recovery_across_restarts(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    req = PanelArtRequest(
        panel_id="p_hang",
        series_id="s01",
        prompt="Hanging panel test",
    )
    job = adapter.create_job(req)
    # Simulate a crash leaving the job in running state
    adapter.update_job(job.id, status=JobStatus.RUNNING.value)

    # Recovery
    recovered = adapter.recover_interrupted_jobs()
    assert len(recovered) == 1
    assert recovered[0].id == job.id
    assert recovered[0].status == JobStatus.INTERRUPTED.value
    assert "Interrupted" in recovered[0].error_text


def test_fastapi_comfy_routes(temp_env):
    adapter: ComfyAdapter = temp_env["adapter"]
    app = FastAPI()
    register_comfy_routes(app, adapter=adapter)

    client = TestClient(app)

    # 1. Status
    res = client.get("/api/manga/comfy/status")
    assert res.status_code == 200
    assert res.json()["is_online"] is False

    # 2. Models
    res = client.get("/api/manga/comfy/models")
    assert res.status_code == 200

    # 3. Workflows
    res = client.get("/api/manga/comfy/workflows")
    assert res.status_code == 200
    assert len(res.json()) >= 3

    # 4. Generate
    payload = {
        "panel_id": "api_p1",
        "prompt": "Detective discovering secret passage behind bookshelf",
        "seed": 777,
        "width": 512,
        "height": 512,
        "art_style": "manga_bw",
    }
    res = client.post("/api/manga/comfy/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "mock"
    assert data["status"] == "completed"
    assert Path(data["image_path"]).is_file()


def test_auto_attach_character_refs_from_refs_and_characters_dir(tmp_path: Path):
    db_file = tmp_path / "refs_test.db"
    manga_dir = tmp_path / "manga"
    fake_comfy = tmp_path / "comfy"
    refs_dir = tmp_path / "refs"
    chars_dir = tmp_path / "data" / "characters"
    (fake_comfy / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    (fake_comfy / "input").mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)
    chars_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy Elara reference sheet in refs/
    elara_ref = refs_dir / "elara_sheet.png"
    Image.new("RGB", (256, 256), (200, 210, 220)).save(elara_ref)

    adapter = ComfyAdapter(
        base_url="http://127.0.0.1:58188",
        comfy_path=fake_comfy,
        manga_dir=manga_dir,
        db_path=db_file,
        refs_dir=refs_dir,
        characters_dir=chars_dir,
    )

    async def _run():
        # Panel 1 mentions Elara -> auto-attaches elara_sheet.png even when character_refs is empty
        req1 = PanelArtRequest(
            panel_id="elara_p1",
            series_id="elara_chronicles",
            chapter_id="ch01",
            prompt="Elara standing on cathedral balcony, silver hair, crimson eyes",
            seed=111,
            width=512,
            height=512,
        )
        res1 = await adapter.generate_panel_art(req1)
        assert res1.status == JobStatus.COMPLETED.value
        assert res1.mode == GenerationMode.MOCK.value
        assert len(res1.metadata.get("character_refs", [])) >= 1
        assert res1.metadata["character_refs"][0]["image_path"] == str(elara_ref)

        # Build prompt graph with auto-attached ref -> routes through AnimaRefAdapterApply
        graph = adapter.workflow_discovery.build_prompt_graph(
            req1, model_name="anima-turbo-q4_k_m.gguf"
        )
        assert "8" in graph
        assert graph["8"]["class_type"] == "AnimaRefAdapterApply"
        # Reference image was staged into ComfyUI input/
        assert (fake_comfy / "input" / "ref_elara_sheet.png").is_file()

        # Panel 2 in a series without static refs chains Panel 1 automatically
        req2_p1 = PanelArtRequest(
            panel_id="chain_p1",
            series_id="chain_series",
            chapter_id="ch01",
            prompt="1girl heroine looking at the moon",
            seed=222,
            width=512,
            height=512,
        )
        res_chain_1 = await adapter.generate_panel_art(req2_p1)
        assert res_chain_1.metadata.get("character_refs") is None

        req2_p2 = PanelArtRequest(
            panel_id="chain_p2",
            series_id="chain_series",
            chapter_id="ch01",
            prompt="1girl heroine drawing her sword",
            seed=223,
            width=512,
            height=512,
        )
        res_chain_2 = await adapter.generate_panel_art(req2_p2)
        chained = res_chain_2.metadata.get("character_refs", [])
        assert len(chained) == 1
        assert chained[0]["source"] == "series_first_panel_anchor"
        assert chained[0]["image_path"] == res_chain_1.image_path

    asyncio.run(_run())
