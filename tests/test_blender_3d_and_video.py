"""Unit tests for Blender 3D / Game Modding Pipeline and LowVRAM Video + De-AI Polish."""

from __future__ import annotations

import asyncio
import json
import struct
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.blender_3d as b3d
import app.video_generator as vgen


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def client_3d(tmp_path, monkeypatch):
    export_dir = tmp_path / "Export" / "3D"
    export_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(b3d, "EXPORT_3D_DIR", export_dir)

    app = FastAPI()
    b3d.register_routes(app)
    return TestClient(app), export_dir


@pytest.fixture
def client_video(tmp_path, monkeypatch):
    export_dir = tmp_path / "Export" / "Video"
    export_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(vgen, "EXPORT_VIDEO_DIR", export_dir)

    app = FastAPI()
    vgen.register_routes(app)
    return TestClient(app), export_dir


# ---------------------------------------------------------------------------
# Blender 3D & Game Modding Tests (Muc 8)
# ---------------------------------------------------------------------------
def test_export_3d_dir_default():
    assert b3d.EXPORT_3D_DIR.parts[-2:] == ("Export", "3D")


def test_find_blender_executable_env_override(tmp_path, monkeypatch):
    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_bytes(b"MZ")
    monkeypatch.setenv("BLENDER_PATH", str(fake_blender))
    assert b3d.find_blender_executable() == fake_blender


def test_generate_bpy_script_contains_headless_ops(tmp_path):
    script = b3d.generate_bpy_script(
        asset_type="sword",
        name="fire_sword",
        export_dir=tmp_path,
        export_format="both",
        scale=1.2,
    )
    assert "import bpy" in script
    assert "recalc_face_normals" in script
    assert "smart_project" in script
    assert "export_scene.gltf" in script
    assert "obj_export" in script


def test_generate_3d_asset_obj_and_glb_valid(tmp_path):
    res = b3d.generate_3d_asset(
        name="hero_sword",
        asset_type="sword",
        export_format="both",
        mod_preset="weapon",
        export_dir=tmp_path,
    )
    obj_path = Path(res["exported_files"]["obj"])
    glb_path = Path(res["exported_files"]["glb"])
    assert obj_path.is_file()
    assert glb_path.is_file()
    assert Path(res["bpy_script"]).is_file()
    assert Path(res["metadata_path"]).is_file()

    # Verify GLB magic header
    magic, version, _ = struct.unpack_from("<3I", glb_path.read_bytes(), 0)
    assert magic == 0x46546C67
    assert version == 2

    # Both OBJ and GLB must pass game-mod validation
    assert res["validation"]["valid"] is True
    assert res["validation"]["errors"] == []
    obj_val = b3d.validate_3d_asset(obj_path, mod_preset="weapon")
    assert obj_val.valid is True
    assert obj_val.stats["has_uv"] is True
    assert obj_val.stats["has_normals"] is True
    assert obj_val.stats["non_manifold_edges"] == 0


def test_validate_3d_asset_catches_non_manifold_and_missing_uv(tmp_path):
    bad_obj = tmp_path / "bad_nonmanifold.obj"
    # 3 triangles sharing edge (0, 1) -> non-manifold! And no UVs!
    bad_obj.write_text(
        "\n".join([
            "v 0 0 0",
            "v 1 0 0",
            "v 0 1 0",
            "v 0 -1 0",
            "v 0 0 1",
            "f 1 2 3",
            "f 1 2 4",
            "f 1 2 5",
        ]),
        encoding="utf-8",
    )
    val = b3d.validate_3d_asset(bad_obj, mod_preset="prop")
    assert val.valid is False
    assert val.stats["non_manifold_edges"] >= 1
    assert val.stats["has_uv"] is False
    assert any("Non-manifold" in e for e in val.errors)
    assert any("UV" in e for e in val.errors)


def test_validate_3d_asset_catches_duplicate_verts_and_inverted_normals(tmp_path):
    mesh = b3d.build_procedural_mesh("cube", "inv_cube")
    # Flip winding of every face -> inside-out normals
    flipped_faces = [list(reversed(f)) for f in mesh.faces]
    inv_mesh = b3d.MeshData(
        name="inv_cube",
        vertices=mesh.vertices + [mesh.vertices[0]],  # add 1 duplicate vertex
        uvs=mesh.uvs,
        normals=mesh.normals,
        faces=flipped_faces,
    )
    obj_path = tmp_path / "inv_cube.obj"
    b3d.export_mesh_obj(inv_mesh, obj_path)

    val = b3d.validate_3d_asset(obj_path, mod_preset="prop")
    assert val.valid is False
    assert val.stats["duplicate_vertices"] == 1
    assert val.stats["inverted_normals"] is True
    assert any("Inverted face normals" in e for e in val.errors)
    assert any("duplicate vertices" in w for w in val.warnings)


def test_validate_3d_asset_catches_polycount_and_missing_texture(tmp_path):
    mesh = b3d.build_procedural_mesh("pillar", "tall_pillar")
    obj_path = tmp_path / "tall_pillar.obj"
    b3d.export_mesh_obj(mesh, obj_path, texture_path="missing_diffuse.png")

    val = b3d.validate_3d_asset(obj_path, max_polycount=4, check_textures=True)
    assert val.valid is False
    assert val.stats["polycount_ok"] is False
    assert "missing_diffuse.png" in val.stats["missing_textures"]
    assert any("exceeds" in e for e in val.errors)
    assert any("Missing texture" in e for e in val.errors)


def test_3d_api_routes(client_3d):
    client, export_dir = client_3d

    st = client.get("/api/3d/status")
    assert st.status_code == 200
    assert "supported_formats" in st.json()

    gen = client.post(
        "/api/3d/generate-asset",
        json={"name": "api_crystal", "asset_type": "crystal", "export_format": "both", "mod_preset": "prop"},
    )
    assert gen.status_code == 200
    data = gen.json()
    assert data["success"] is True
    assert data["validation"]["valid"] is True

    val = client.post(
        "/api/3d/validate-mod",
        json={"file_path": data["exported_files"]["glb"], "mod_preset": "prop"},
    )
    assert val.status_code == 200
    assert val.json()["valid"] is True

    exps = client.get("/api/3d/exports")
    assert exps.status_code == 200
    assert exps.json()["count"] >= 3  # obj, glb, _bpy.py, _metadata.json


# ---------------------------------------------------------------------------
# LowVRAM Video & De-AI Polish Tests (Muc 12)
# ---------------------------------------------------------------------------
def test_export_video_dir_default():
    assert vgen.EXPORT_VIDEO_DIR.parts[-2:] == ("Export", "Video")


def test_inspect_wan_workflow_and_prompt_builder():
    info = vgen.inspect_wan_workflow()
    assert "workflow_path" in info
    if info["workflow_exists"]:
        assert info["node_count"] >= 10
        assert info["unet_name"] == "wan_1.3B_exp_e14.safetensors"

    graph = vgen.build_wan_comfy_prompt(
        prompt="cinematic samurai walking in rain",
        width=480,
        height=272,
        frames=17,
        fps=16,
        steps=20,
        cfg=6.0,
        seed=42,
    )
    assert graph["37"]["inputs"]["unet_name"] == "wan_1.3B_exp_e14.safetensors"
    assert graph["40"]["inputs"]["width"] == 480
    assert graph["40"]["inputs"]["height"] == 272
    assert graph["3"]["inputs"]["seed"] == 42
    assert graph["49"]["inputs"]["fps"] == 16


def test_build_de_ai_filtergraph():
    vf = vgen.build_de_ai_filtergraph(
        target_fps=24,
        motion_smooth=True,
        grain_strength=7,
        saturation=0.86,
        contrast=1.06,
    )
    assert "minterpolate=fps=24" in vf
    assert "eq=saturation=0.86:contrast=1.06" in vf
    assert "colorbalance=" in vf
    assert "noise=alls=7:allf=t+u" in vf
    assert "format=yuv420p" in vf


def test_generate_video_offline_and_de_ai_enhance(tmp_path):
    res = asyncio.run(
        vgen.generate_video(
            prompt="test offline video",
            width=160,
            height=120,
            frames=16,
            fps=16,
            apply_de_ai=True,
            motion_smooth=False,  # fast in unit test while still testing grain + colorbalance
            output_name="unit_test_vid",
            use_comfy=False,
            export_dir=tmp_path,
        )
    )
    vid_path = Path(res["video_path"])
    assert vid_path.is_file()
    assert vid_path.stat().st_size > 1000
    assert res["de_ai_applied"] is True
    assert "noise=alls=" in res["de_ai_info"]["filtergraph"]
    assert Path(res["metadata_path"]).is_file()


def test_video_api_routes(client_video):
    client, export_dir = client_video

    st = client.get("/api/video/status")
    assert st.status_code == 200
    st_json = st.json()
    assert st_json["ffmpeg_available"] is True
    assert "cinematic" in st_json["de_ai_presets"]

    gen = client.post(
        "/api/video/generate",
        json={
            "prompt": "api offline test",
            "width": 160,
            "height": 120,
            "frames": 16,
            "fps": 16,
            "apply_de_ai": True,
            "motion_smooth": False,
            "output_name": "api_vid",
            "use_comfy": False,
        },
    )
    assert gen.status_code == 200
    data = gen.json()
    assert data["success"] is True
    assert Path(data["video_path"]).is_file()

    enh = client.post(
        "/api/video/de-ai-enhance",
        json={
            "input_path": data["video_path"],
            "preset": "subtle",
            "motion_smooth": False,
            "output_name": "api_vid_polished",
        },
    )
    assert enh.status_code == 200
    assert Path(enh.json()["output_path"]).is_file()

    exps = client.get("/api/video/exports")
    assert exps.status_code == 200
    assert exps.json()["count"] >= 2
