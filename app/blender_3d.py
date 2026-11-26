"""Blender 3D & Bug-Free Game Modding Pipeline (Muc 8).

Features:
- Auto-detects local ``blender.exe`` and generates headless ``bpy`` scripts
  (``blender --background --python ...``).
- Built-in pure-Python 3D mesh generator and exporter (``.obj`` and binary
  ``.glb`` glTF 2.0) + metadata JSON when running headless/offline without Blender.
- ``validate_3d_asset()`` topology & game-modding validator:
  * Duplicate vertices detection
  * Non-manifold edge & open-boundary checks
  * Face normal presence, degenerate faces, and outward winding checks
  * UV map presence and bounds checks
  * Polycount limits per game-mod preset
  * Texture path verification (missing or non-portable absolute paths)
- Saves all outputs into ``F:\\AI-Office\\Export\\3D\\``.
- Exposes FastAPI routes via ``register_routes(app)``.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import struct
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("blender_3d")

ROOT_DIR = Path(__file__).resolve().parents[1]
EXPORT_3D_DIR = Path(
    os.environ.get("AI_OFFICE_EXPORT_3D_DIR", str(ROOT_DIR / "Export" / "3D"))
)
EXPORT_3D_DIR.mkdir(parents=True, exist_ok=True)

GAME_MOD_PRESETS: Dict[str, Dict[str, Any]] = {
    "prop": {"max_polys": 5000, "allow_open_boundaries": False, "description": "Static game prop / crate / furniture"},
    "weapon": {"max_polys": 15000, "allow_open_boundaries": False, "description": "Melee or ranged weapon mod"},
    "character": {"max_polys": 60000, "allow_open_boundaries": True, "description": "Character / armor / outfit mod"},
    "environment": {"max_polys": 100000, "allow_open_boundaries": True, "description": "Architecture / terrain chunk"},
    "custom": {"max_polys": 50000, "allow_open_boundaries": False, "description": "Custom polycount limit"},
}

SUPPORTED_ASSET_TYPES = ("cube", "crate", "sword", "shield", "pillar", "crystal", "plane")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_stem(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", (name or "").strip()).strip("_")
    return cleaned or f"asset_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Blender Executable Discovery
# ---------------------------------------------------------------------------
def find_blender_executable() -> Optional[Path]:
    """Locate ``blender.exe`` on Windows / PATH if installed."""
    env_path = os.environ.get("BLENDER_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    which_blender = shutil.which("blender")
    if which_blender:
        p = Path(which_blender)
        if p.is_file():
            return p

    search_roots = [
        Path(r"C:\Program Files\Blender Foundation"),
        Path(r"D:\Program Files\Blender Foundation"),
        Path(r"F:\Program Files\Blender Foundation"),
        Path(r"F:\Blender"),
    ]
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app:
        search_roots.append(Path(local_app) / "Programs" / "Blender Foundation")

    for root in search_roots:
        if not root.exists():
            continue
        direct = root / "blender.exe"
        if direct.is_file():
            return direct
        try:
            candidates = sorted(root.glob("Blender*/blender.exe"), reverse=True)
            for cand in candidates:
                if cand.is_file():
                    return cand
        except OSError:
            continue

    return None


# ---------------------------------------------------------------------------
# Mesh Data Structure & Pure-Python Procedural Primitives
# ---------------------------------------------------------------------------
@dataclass
class MeshData:
    """In-memory triangulated/polygonal 3D mesh with UVs and normals."""

    name: str
    vertices: List[Tuple[float, float, float]]
    uvs: List[Tuple[float, float]]
    normals: List[Tuple[float, float, float]]
    # Each face is a list of (v_idx, vt_idx, vn_idx) 0-based tuples
    faces: List[List[Tuple[int, int, int]]]


def _sub(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1e-12:
        return (0.0, 0.0, 1.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _make_box_mesh(
    name: str,
    hx: float = 0.5,
    hy: float = 0.5,
    hz: float = 0.5,
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> MeshData:
    """Create a watertight, outward-facing, UV-mapped box mesh with 8 unique vertices."""
    ox, oy, oz = offset
    vertices = [
        (ox - hx, oy - hy, oz - hz),  # 0: -X -Y -Z
        (ox + hx, oy - hy, oz - hz),  # 1: +X -Y -Z
        (ox + hx, oy + hy, oz - hz),  # 2: +X +Y -Z
        (ox - hx, oy + hy, oz - hz),  # 3: -X +Y -Z
        (ox - hx, oy - hy, oz + hz),  # 4: -X -Y +Z
        (ox + hx, oy - hy, oz + hz),  # 5: +X -Y +Z
        (ox + hx, oy + hy, oz + hz),  # 6: +X +Y +Z
        (ox - hx, oy + hy, oz + hz),  # 7: -X +Y +Z
    ]
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    normals = [
        (0.0, 0.0, -1.0),  # 0: bottom (-Z)
        (0.0, 0.0, 1.0),   # 1: top (+Z)
        (0.0, -1.0, 0.0),  # 2: front (-Y)
        (0.0, 1.0, 0.0),   # 3: back (+Y)
        (-1.0, 0.0, 0.0),  # 4: left (-X)
        (1.0, 0.0, 0.0),   # 5: right (+X)
    ]
    # All triangles wound CCW when viewed from outside
    tri_defs = [
        # Bottom (-Z)
        ((0, 0, 0), (3, 3, 0), (2, 2, 0)),
        ((0, 0, 0), (2, 2, 0), (1, 1, 0)),
        # Top (+Z)
        ((4, 0, 1), (5, 1, 1), (6, 2, 1)),
        ((4, 0, 1), (6, 2, 1), (7, 3, 1)),
        # Front (-Y)
        ((0, 0, 2), (1, 1, 2), (5, 2, 2)),
        ((0, 0, 2), (5, 2, 2), (4, 3, 2)),
        # Back (+Y)
        ((2, 0, 3), (3, 1, 3), (7, 2, 3)),
        ((2, 0, 3), (7, 2, 3), (6, 3, 3)),
        # Left (-X)
        ((3, 0, 4), (0, 1, 4), (4, 2, 4)),
        ((3, 0, 4), (4, 2, 4), (7, 3, 4)),
        # Right (+X)
        ((1, 0, 5), (2, 1, 5), (6, 2, 5)),
        ((1, 0, 5), (6, 2, 5), (5, 3, 5)),
    ]
    faces = [[a, b, c] for (a, b, c) in tri_defs]
    return MeshData(name=name, vertices=vertices, uvs=uvs, normals=normals, faces=faces)


def _merge_meshes(name: str, parts: List[MeshData]) -> MeshData:
    vertices: List[Tuple[float, float, float]] = []
    uvs: List[Tuple[float, float]] = []
    normals: List[Tuple[float, float, float]] = []
    faces: List[List[Tuple[int, int, int]]] = []

    for part in parts:
        v_off = len(vertices)
        vt_off = len(uvs)
        vn_off = len(normals)
        vertices.extend(part.vertices)
        uvs.extend(part.uvs)
        normals.extend(part.normals)
        for face in part.faces:
            faces.append([(vi + v_off, vti + vt_off, vni + vn_off) for (vi, vti, vni) in face])

    return MeshData(name=name, vertices=vertices, uvs=uvs, normals=normals, faces=faces)


def _make_octahedron_crystal(name: str, radius: float = 0.5, height: float = 1.6) -> MeshData:
    """Create a watertight crystal/gem octahedron with outward normals and UVs."""
    hh = height * 0.5
    vertices = [
        (0.0, 0.0, hh),       # 0: top apex
        (radius, 0.0, 0.0),   # 1: +X
        (0.0, radius, 0.0),   # 2: +Y
        (-radius, 0.0, 0.0),  # 3: -X
        (0.0, -radius, 0.0),  # 4: -Y
        (0.0, 0.0, -hh),      # 5: bottom apex
    ]
    uvs = [(0.5, 1.0), (0.0, 0.5), (0.25, 0.5), (0.5, 0.5), (0.75, 0.5), (0.5, 0.0)]
    raw_tris = [
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
        (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4),
    ]
    normals: List[Tuple[float, float, float]] = []
    faces: List[List[Tuple[int, int, int]]] = []
    for idx, (i0, i1, i2) in enumerate(raw_tris):
        n = _normalize(_cross(_sub(vertices[i1], vertices[i0]), _sub(vertices[i2], vertices[i0])))
        normals.append(n)
        faces.append([(i0, i0, idx), (i1, i1, idx), (i2, i2, idx)])
    return MeshData(name=name, vertices=vertices, uvs=uvs, normals=normals, faces=faces)


def _make_plane_mesh(name: str, half_size: float = 1.0) -> MeshData:
    vertices = [
        (-half_size, -half_size, 0.0),
        (half_size, -half_size, 0.0),
        (half_size, half_size, 0.0),
        (-half_size, half_size, 0.0),
    ]
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    normals = [(0.0, 0.0, 1.0)]
    faces = [
        [(0, 0, 0), (1, 1, 0), (2, 2, 0)],
        [(0, 0, 0), (2, 2, 0), (3, 3, 0)],
    ]
    return MeshData(name=name, vertices=vertices, uvs=uvs, normals=normals, faces=faces)


def build_procedural_mesh(
    asset_type: str = "cube",
    name: str = "asset",
    scale: float = 1.0,
) -> MeshData:
    """Build a clean, game-mod-ready procedural 3D mesh."""
    kind = (asset_type or "cube").strip().lower()
    s = max(0.05, float(scale))

    if kind == "sword":
        blade = _make_box_mesh(f"{name}_blade", 0.06 * s, 0.02 * s, 0.65 * s, (0.0, 0.0, 0.75 * s))
        guard = _make_box_mesh(f"{name}_guard", 0.22 * s, 0.04 * s, 0.04 * s, (0.0, 0.0, 0.08 * s))
        grip = _make_box_mesh(f"{name}_grip", 0.03 * s, 0.03 * s, 0.16 * s, (0.0, 0.0, -0.10 * s))
        return _merge_meshes(name, [blade, guard, grip])
    if kind == "shield":
        body = _make_box_mesh(f"{name}_shield", 0.35 * s, 0.04 * s, 0.48 * s)
        boss = _make_box_mesh(f"{name}_boss", 0.10 * s, 0.06 * s, 0.10 * s, (0.0, -0.05 * s, 0.0))
        return _merge_meshes(name, [body, boss])
    if kind == "pillar":
        base = _make_box_mesh(f"{name}_base", 0.45 * s, 0.45 * s, 0.12 * s, (0.0, 0.0, 0.12 * s))
        shaft = _make_box_mesh(f"{name}_shaft", 0.28 * s, 0.28 * s, 1.0 * s, (0.0, 0.0, 1.24 * s))
        cap = _make_box_mesh(f"{name}_cap", 0.45 * s, 0.45 * s, 0.12 * s, (0.0, 0.0, 2.36 * s))
        return _merge_meshes(name, [base, shaft, cap])
    if kind == "crystal":
        return _make_octahedron_crystal(name, radius=0.35 * s, height=1.2 * s)
    if kind == "plane":
        return _make_plane_mesh(name, half_size=0.5 * s)
    # "cube", "crate", or fallback
    return _make_box_mesh(name, 0.5 * s, 0.5 * s, 0.5 * s)


# ---------------------------------------------------------------------------
# Exporters: OBJ (+ MTL) & Binary GLB (glTF 2.0)
# ---------------------------------------------------------------------------
def export_mesh_obj(
    mesh: MeshData,
    obj_path: Path,
    texture_path: Optional[str] = None,
) -> Path:
    """Write MeshData to Wavefront .obj (and optional .mtl)."""
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [
        f"# AI-Office Blender3D Pipeline Export",
        f"# Asset: {mesh.name}",
        f"o {mesh.name}",
    ]

    if texture_path:
        mtl_path = obj_path.with_suffix(".mtl")
        mtl_lines = [
            f"# Material for {mesh.name}",
            f"newmtl {mesh.name}_mat",
            "Ka 0.200 0.200 0.200",
            "Kd 0.800 0.800 0.800",
            "Ks 0.100 0.100 0.100",
            "d 1.0",
            f"map_Kd {texture_path}",
        ]
        mtl_path.write_text("\n".join(mtl_lines) + "\n", encoding="utf-8")
        lines.append(f"mtllib {mtl_path.name}")
        lines.append(f"usemtl {mesh.name}_mat")

    for vx, vy, vz in mesh.vertices:
        lines.append(f"v {vx:.6f} {vy:.6f} {vz:.6f}")
    for u, v in mesh.uvs:
        lines.append(f"vt {u:.6f} {v:.6f}")
    for nx, ny, nz in mesh.normals:
        lines.append(f"vn {nx:.6f} {ny:.6f} {nz:.6f}")

    for face in mesh.faces:
        tokens = [f"{vi + 1}/{vti + 1}/{vni + 1}" for (vi, vti, vni) in face]
        lines.append("f " + " ".join(tokens))

    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return obj_path


def export_mesh_glb(mesh: MeshData, glb_path: Path) -> Path:
    """Write MeshData to a spec-compliant binary glTF 2.0 (.glb) file."""
    glb_path.parent.mkdir(parents=True, exist_ok=True)

    # Expand per-face-corner attributes so POSITION, NORMAL, TEXCOORD_0 align 1:1
    positions: List[Tuple[float, float, float]] = []
    normals: List[Tuple[float, float, float]] = []
    uvs: List[Tuple[float, float]] = []
    indices: List[int] = []

    corner_map: Dict[Tuple[int, int, int], int] = {}
    for face in mesh.faces:
        if len(face) < 3:
            continue
        tri_fans = [(face[0], face[i], face[i + 1]) for i in range(1, len(face) - 1)]
        for tri in tri_fans:
            for key in tri:
                if key not in corner_map:
                    vi, vti, vni = key
                    corner_map[key] = len(positions)
                    positions.append(mesh.vertices[vi])
                    uvs.append(mesh.uvs[vti] if 0 <= vti < len(mesh.uvs) else (0.0, 0.0))
                    normals.append(mesh.normals[vni] if 0 <= vni < len(mesh.normals) else (0.0, 0.0, 1.0))
                indices.append(corner_map[key])

    pos_bytes = b"".join(struct.pack("<3f", *p) for p in positions)
    norm_bytes = b"".join(struct.pack("<3f", *n) for n in normals)
    uv_bytes = b"".join(struct.pack("<2f", *t) for t in uvs)
    idx_bytes = b"".join(struct.pack("<I", i) for i in indices)

    # 4-byte alignment padding for BIN buffer
    def _pad4(data: bytes, fill: bytes = b"\x00") -> bytes:
        rem = len(data) % 4
        return data if rem == 0 else data + fill * (4 - rem)

    pos_offset = 0
    norm_offset = len(pos_bytes)
    uv_offset = norm_offset + len(norm_bytes)
    idx_offset = uv_offset + len(uv_bytes)
    bin_chunk = _pad4(pos_bytes + norm_bytes + uv_bytes + idx_bytes)

    xs = [p[0] for p in positions] or [0.0]
    ys = [p[1] for p in positions] or [0.0]
    zs = [p[2] for p in positions] or [0.0]

    gltf_json = {
        "asset": {"version": "2.0", "generator": "AI-Office Blender3D Pipeline"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": mesh.name}],
        "meshes": [
            {
                "name": mesh.name,
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                        "indices": 3,
                        "mode": 4,
                    }
                ],
            }
        ],
        "buffers": [{"byteLength": len(bin_chunk)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": pos_offset, "byteLength": len(pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": norm_offset, "byteLength": len(norm_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": uv_offset, "byteLength": len(uv_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": idx_offset, "byteLength": len(idx_bytes), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            },
            {"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": len(uvs), "type": "VEC2"},
            {"bufferView": 3, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ],
    }
    json_bytes = _pad4(json.dumps(gltf_json, separators=(",", ":")).encode("utf-8"), b" ")

    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    header = struct.pack("<3I", 0x46546C67, 2, total_length)
    json_header = struct.pack("<2I", len(json_bytes), 0x4E4F534A)
    bin_header = struct.pack("<2I", len(bin_chunk), 0x004E4942)

    glb_path.write_bytes(header + json_header + json_bytes + bin_header + bin_chunk)
    return glb_path


# ---------------------------------------------------------------------------
# Headless Blender bpy Script Generation & Execution
# ---------------------------------------------------------------------------
def generate_bpy_script(
    asset_type: str,
    name: str,
    export_dir: Path,
    export_format: str = "glb",
    scale: float = 1.0,
) -> str:
    """Generate a headless Blender ``bpy`` Python script for ``blender --background --python``."""
    safe_name = _safe_stem(name)
    out_obj = (export_dir / f"{safe_name}.obj").as_posix()
    out_glb = (export_dir / f"{safe_name}.glb").as_posix()

    return f'''"""Auto-generated headless Blender script by AI-Office."""
import bpy
import bmesh

bpy.ops.wm.read_factory_settings(use_empty=True)

asset_type = {asset_type!r}
scale = {float(scale)!r}

if asset_type == "crystal":
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.5 * scale)
elif asset_type == "pillar":
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.35 * scale, depth=2.0 * scale)
elif asset_type == "plane":
    bpy.ops.mesh.primitive_plane_add(size=1.0 * scale)
else:
    bpy.ops.mesh.primitive_cube_add(size=1.0 * scale)

obj = bpy.context.active_object
obj.name = {safe_name!r}

# Enforce clean manifold topology & outward normals for game modding
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(obj.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bmesh.update_edit_mesh(obj.data)
bpy.ops.uv.smart_project(angle_limit=66.0)
bpy.ops.object.mode_set(mode="OBJECT")

fmt = {export_format.lower()!r}
if fmt in ("obj", "both"):
    bpy.ops.wm.obj_export(filepath={out_obj!r}, export_uv=True, export_normals=True)
if fmt in ("glb", "both"):
    bpy.ops.export_scene.gltf(filepath={out_glb!r}, export_format="GLB")
'''


def run_blender_headless(
    script_path: Path,
    blender_exe: Optional[Path] = None,
    timeout: int = 90,
) -> Dict[str, Any]:
    """Run ``blender --background --python <script_path>`` if Blender is installed."""
    exe = blender_exe or find_blender_executable()
    if exe is None or not exe.is_file():
        return {"ran": False, "reason": "blender.exe not found", "returncode": -1}

    cmd = [str(exe), "--background", "--python", str(script_path)]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "ran": True,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-2000:] if proc.stdout else "",
        "stderr": proc.stderr[-2000:] if proc.stderr else "",
        "command": cmd,
    }


# ---------------------------------------------------------------------------
# Topology & Game-Modding Validator
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    valid: bool
    file_path: str
    format: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_obj_for_validation(path: Path) -> Tuple[
    List[Tuple[float, float, float]],
    List[Tuple[float, float]],
    List[Tuple[float, float, float]],
    List[List[Tuple[int, Optional[int], Optional[int]]]],
    List[str],
]:
    vertices: List[Tuple[float, float, float]] = []
    uvs: List[Tuple[float, float]] = []
    normals: List[Tuple[float, float, float]] = []
    faces: List[List[Tuple[int, Optional[int], Optional[int]]]] = []
    mtl_files: List[str] = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        tag = parts[0]
        if tag == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif tag == "vt" and len(parts) >= 3:
            uvs.append((float(parts[1]), float(parts[2])))
        elif tag == "vn" and len(parts) >= 4:
            normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif tag == "mtllib" and len(parts) >= 2:
            mtl_files.append(" ".join(parts[1:]))
        elif tag == "f" and len(parts) >= 4:
            face_verts: List[Tuple[int, Optional[int], Optional[int]]] = []
            for tok in parts[1:]:
                segs = tok.split("/")
                vi = int(segs[0])
                vi = vi - 1 if vi > 0 else len(vertices) + vi
                vti: Optional[int] = None
                vni: Optional[int] = None
                if len(segs) >= 2 and segs[1]:
                    raw_vt = int(segs[1])
                    vti = raw_vt - 1 if raw_vt > 0 else len(uvs) + raw_vt
                if len(segs) >= 3 and segs[2]:
                    raw_vn = int(segs[2])
                    vni = raw_vn - 1 if raw_vn > 0 else len(normals) + raw_vn
                face_verts.append((vi, vti, vni))
            faces.append(face_verts)

    return vertices, uvs, normals, faces, mtl_files


def _parse_glb_for_validation(path: Path) -> Tuple[
    List[Tuple[float, float, float]],
    List[Tuple[float, float]],
    List[Tuple[float, float, float]],
    List[List[Tuple[int, Optional[int], Optional[int]]]],
    List[str],
]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("Invalid GLB: file too small")
    magic, version, _total_len = struct.unpack_from("<3I", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError("Invalid GLB header magic/version")

    offset = 12
    gltf_json: Optional[Dict[str, Any]] = None
    bin_data = b""
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<2I", data, offset)
        offset += 8
        chunk_bytes = data[offset: offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            gltf_json = json.loads(chunk_bytes.decode("utf-8"))
        elif chunk_type == 0x004E4942:
            bin_data = chunk_bytes

    if gltf_json is None:
        raise ValueError("Invalid GLB: missing JSON chunk")

    accessors = gltf_json.get("accessors", [])
    buffer_views = gltf_json.get("bufferViews", [])

    def _read_accessor(acc_idx: int) -> List[Any]:
        acc = accessors[acc_idx]
        bv = buffer_views[acc["bufferView"]]
        base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        count = acc["count"]
        ctype = acc["componentType"]
        atype = acc["type"]
        fmt_map = {5126: "f", 5125: "I", 5123: "H", 5121: "B"}
        comp_cnt = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[atype]
        fmt_char = fmt_map[ctype]
        stride = bv.get("byteStride") or (struct.calcsize("<" + fmt_char * comp_cnt))
        out = []
        for i in range(count):
            vals = struct.unpack_from("<" + fmt_char * comp_cnt, bin_data, base + i * stride)
            out.append(vals[0] if comp_cnt == 1 else vals)
        return out

    vertices: List[Tuple[float, float, float]] = []
    uvs: List[Tuple[float, float]] = []
    normals: List[Tuple[float, float, float]] = []
    faces: List[List[Tuple[int, Optional[int], Optional[int]]]] = []

    for mesh in gltf_json.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs = prim.get("attributes", {})
            v_off = len(vertices)
            vt_off = len(uvs)
            vn_off = len(normals)

            pos_list = _read_accessor(attrs["POSITION"]) if "POSITION" in attrs else []
            vertices.extend((float(p[0]), float(p[1]), float(p[2])) for p in pos_list)

            has_uv = "TEXCOORD_0" in attrs
            if has_uv:
                uv_list = _read_accessor(attrs["TEXCOORD_0"])
                uvs.extend((float(t[0]), float(t[1])) for t in uv_list)

            has_norm = "NORMAL" in attrs
            if has_norm:
                n_list = _read_accessor(attrs["NORMAL"])
                normals.extend((float(n[0]), float(n[1]), float(n[2])) for n in n_list)

            if "indices" in prim:
                idxs = _read_accessor(prim["indices"])
            else:
                idxs = list(range(len(pos_list)))

            for i in range(0, len(idxs) - 2, 3):
                a, b, c = int(idxs[i]), int(idxs[i + 1]), int(idxs[i + 2])
                faces.append([
                    (a + v_off, (a + vt_off) if has_uv else None, (a + vn_off) if has_norm else None),
                    (b + v_off, (b + vt_off) if has_uv else None, (b + vn_off) if has_norm else None),
                    (c + v_off, (c + vt_off) if has_uv else None, (c + vn_off) if has_norm else None),
                ])

    tex_uris = [img["uri"] for img in gltf_json.get("images", []) if "uri" in img and not img["uri"].startswith("data:")]
    return vertices, uvs, normals, faces, tex_uris


def _inspect_mtl_textures(obj_path: Path, mtl_files: List[str]) -> Tuple[List[str], List[str]]:
    referenced: List[str] = []
    missing: List[str] = []
    tex_keys = ("map_kd", "map_ka", "map_ks", "map_bump", "bump", "map_d", "map_ns")

    for mtl_rel in mtl_files:
        mtl_path = (obj_path.parent / mtl_rel)
        if not mtl_path.exists():
            missing.append(mtl_rel)
            continue
        for raw_line in mtl_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].lower() in tex_keys:
                tex_ref = parts[1].strip()
                referenced.append(tex_ref)
                tex_p = Path(tex_ref)
                if not tex_p.is_absolute():
                    tex_p = mtl_path.parent / tex_ref
                if not tex_p.exists():
                    missing.append(tex_ref)

    return referenced, missing


def validate_3d_asset(
    file_path: str | Path,
    max_polycount: Optional[int] = None,
    check_textures: bool = True,
    mod_preset: str = "prop",
) -> ValidationResult:
    """Validate a 3D asset (.obj or .glb) for bug-free game modding.

    Checks:
    - Non-manifold edges (>2 incident faces) & open boundary edges (1 incident face)
    - Duplicate vertices at identical quantized coordinates
    - Face normals presence, degenerate/zero-area faces, and outward winding
    - UV map presence & face UV coverage
    - Triangle polycount against game-mod preset limit
    - Texture file paths (missing files or non-portable absolute paths)
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"3D asset not found: {path}")

    ext = path.suffix.lower()
    if ext not in (".obj", ".glb"):
        raise ValueError(f"Unsupported 3D format '{ext}'. Supported: .obj, .glb")

    preset_cfg = GAME_MOD_PRESETS.get(mod_preset, GAME_MOD_PRESETS["prop"])
    poly_limit = int(max_polycount if max_polycount is not None else preset_cfg["max_polys"])
    allow_open = bool(preset_cfg.get("allow_open_boundaries", False))

    if ext == ".obj":
        vertices, uvs, normals, faces, extra_refs = _parse_obj_for_validation(path)
        ref_textures, missing_textures = _inspect_mtl_textures(path, extra_refs) if check_textures else ([], [])
    else:
        vertices, uvs, normals, faces, extra_refs = _parse_glb_for_validation(path)
        ref_textures = extra_refs
        missing_textures = []
        if check_textures:
            for t in ref_textures:
                tp = Path(t) if Path(t).is_absolute() else path.parent / t
                if not tp.exists():
                    missing_textures.append(t)

    errors: List[str] = []
    warnings: List[str] = []

    if not vertices or not faces:
        errors.append("Mesh has no vertices or faces (will be invisible in game).")

    # 1. Duplicate vertices (quantized to 1e-6)
    coord_to_canonical: Dict[Tuple[float, float, float], int] = {}
    canonical_idx: List[int] = []
    duplicate_vertices = 0
    for idx, (vx, vy, vz) in enumerate(vertices):
        key = (round(vx, 6), round(vy, 6), round(vz, 6))
        if key in coord_to_canonical:
            duplicate_vertices += 1
            canonical_idx.append(coord_to_canonical[key])
        else:
            coord_to_canonical[key] = idx
            canonical_idx.append(idx)

    # For GLB, vertices are intentionally duplicated at hard edges/UV seams;
    # only treat welded-position duplicates as a warning unless severe in OBJ.
    if duplicate_vertices > 0 and ext == ".obj":
        warnings.append(
            f"Found {duplicate_vertices} duplicate vertices; merge doubles to prevent shading/clipping seams."
        )

    # 2. Polycount & Edge Manifoldness & Face Normals
    triangle_count = 0
    edge_face_counts: Dict[Tuple[int, int], int] = {}
    zero_area_faces = 0
    faces_missing_uv = 0
    faces_missing_normal = 0
    signed_volume_sum = 0.0

    for face in faces:
        n_verts = len(face)
        if n_verts < 3:
            zero_area_faces += 1
            continue
        triangle_count += (n_verts - 2)

        # Edge counting using canonical vertex indices so welded topology is checked
        for i in range(n_verts):
            a = canonical_idx[face[i][0]]
            b = canonical_idx[face[(i + 1) % n_verts][0]]
            if a == b:
                continue
            edge = (a, b) if a < b else (b, a)
            edge_face_counts[edge] = edge_face_counts.get(edge, 0) + 1

        if any(vt is None for (_, vt, _) in face):
            faces_missing_uv += 1
        if any(vn is None for (_, _, vn) in face):
            faces_missing_normal += 1

        # Triangulate fan for area & signed volume
        p0 = vertices[face[0][0]]
        for i in range(1, n_verts - 1):
            p1 = vertices[face[i][0]]
            p2 = vertices[face[i + 1][0]]
            cross_p = _cross(_sub(p1, p0), _sub(p2, p0))
            area2 = math.sqrt(_dot(cross_p, cross_p))
            if area2 <= 1e-10:
                zero_area_faces += 1
            signed_volume_sum += _dot(p0, _cross(p1, p2)) / 6.0

    non_manifold_edges = sum(1 for c in edge_face_counts.values() if c > 2)
    boundary_edges = sum(1 for c in edge_face_counts.values() if c == 1)

    if non_manifold_edges > 0:
        errors.append(
            f"Non-manifold geometry: {non_manifold_edges} edge(s) shared by >2 faces (causes clipping/collision bugs)."
        )
    if boundary_edges > 0 and not allow_open:
        warnings.append(
            f"Open boundary: {boundary_edges} edge(s) belong to only 1 face (may cause backface invisibility)."
        )

    if zero_area_faces > 0:
        errors.append(f"Found {zero_area_faces} degenerate/zero-area face(s).")

    # Closed mesh outward winding check
    is_closed = len(edge_face_counts) > 0 and boundary_edges == 0 and non_manifold_edges == 0
    inverted_normals = False
    if is_closed and signed_volume_sum < -1e-7:
        inverted_normals = True
        errors.append(
            "Inverted face normals detected (negative signed volume; mesh will appear inside-out/invisible in game)."
        )

    has_normals = len(normals) > 0 and faces_missing_normal == 0
    if not has_normals:
        warnings.append("Missing vertex/face normals; game engine will recompute flat/auto normals.")

    # 3. UV map check
    has_uv = len(uvs) > 0 and faces_missing_uv == 0
    if not has_uv:
        errors.append("Missing UV map coordinates on one or more faces (textures will fail to render).")

    # 4. Polycount check
    polycount_ok = triangle_count <= poly_limit
    if not polycount_ok:
        errors.append(
            f"Polycount {triangle_count} triangles exceeds '{mod_preset}' limit of {poly_limit}."
        )

    # 5. Texture path check
    if check_textures and missing_textures:
        errors.append(f"Missing texture/material file(s): {', '.join(missing_textures)}")
    for t in ref_textures:
        if Path(t).is_absolute():
            warnings.append(f"Absolute texture path '{t}' may break mod portability; use relative paths.")

    return ValidationResult(
        valid=(len(errors) == 0),
        file_path=str(path),
        format=ext.lstrip("."),
        errors=errors,
        warnings=warnings,
        stats={
            "vertices": len(vertices),
            "faces": len(faces),
            "triangles": triangle_count,
            "duplicate_vertices": duplicate_vertices,
            "non_manifold_edges": non_manifold_edges,
            "boundary_edges": boundary_edges,
            "zero_area_faces": zero_area_faces,
            "inverted_normals": inverted_normals,
            "has_normals": has_normals,
            "has_uv": has_uv,
            "polycount": triangle_count,
            "max_polycount": poly_limit,
            "polycount_ok": polycount_ok,
            "referenced_textures": ref_textures,
            "missing_textures": missing_textures,
        },
    )


# ---------------------------------------------------------------------------
# High-Level Asset Generation Orchestrator
# ---------------------------------------------------------------------------
def generate_3d_asset(
    name: str = "mod_prop",
    asset_type: str = "cube",
    export_format: str = "both",
    mod_preset: str = "prop",
    scale: float = 1.0,
    use_blender: bool = False,
    texture_path: Optional[str] = None,
    export_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a 3D asset (.obj/.glb), bpy script, metadata JSON, and validation report."""
    out_dir = export_dir or EXPORT_3D_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_stem(name)
    fmt = (export_format or "both").strip().lower()
    if fmt not in ("obj", "glb", "both"):
        raise ValueError(f"Invalid export_format '{export_format}'. Choose 'obj', 'glb', or 'both'.")

    mesh = build_procedural_mesh(asset_type=asset_type, name=safe_name, scale=scale)
    exported_files: Dict[str, str] = {}

    if fmt in ("obj", "both"):
        obj_path = export_mesh_obj(mesh, out_dir / f"{safe_name}.obj", texture_path=texture_path)
        exported_files["obj"] = str(obj_path)
    if fmt in ("glb", "both"):
        glb_path = export_mesh_glb(mesh, out_dir / f"{safe_name}.glb")
        exported_files["glb"] = str(glb_path)

    script_content = generate_bpy_script(
        asset_type=asset_type,
        name=safe_name,
        export_dir=out_dir,
        export_format=fmt,
        scale=scale,
    )
    script_path = out_dir / f"{safe_name}_bpy.py"
    script_path.write_text(script_content, encoding="utf-8")

    blender_run: Dict[str, Any] = {"ran": False, "reason": "headless_python_export"}
    if use_blender:
        blender_run = run_blender_headless(script_path)

    primary_file = exported_files.get("glb") or exported_files.get("obj")
    validation = validate_3d_asset(primary_file, mod_preset=mod_preset)

    metadata = {
        "name": safe_name,
        "asset_type": asset_type,
        "mod_preset": mod_preset,
        "scale": scale,
        "created_at": _utc_now(),
        "exported_files": exported_files,
        "bpy_script": str(script_path),
        "blender_run": blender_run,
        "validation": validation.to_dict(),
    }
    meta_path = out_dir / f"{safe_name}_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metadata["metadata_path"] = str(meta_path)
    return metadata


# ---------------------------------------------------------------------------
# FastAPI Routes
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/3d", tags=["Blender 3D & Game Modding"])


class Generate3DAssetRequest(BaseModel):
    name: str = Field(default="mod_prop", description="Asset base filename")
    asset_type: str = Field(default="cube", description="cube, crate, sword, shield, pillar, crystal, plane")
    export_format: str = Field(default="both", description="obj, glb, or both")
    mod_preset: str = Field(default="prop", description="prop, weapon, character, environment, custom")
    scale: float = Field(default=1.0, gt=0.0, le=100.0)
    use_blender: bool = Field(default=False, description="Run blender.exe --background if installed")
    texture_path: Optional[str] = None


class ValidateModRequest(BaseModel):
    file_path: str
    mod_preset: str = "prop"
    max_polycount: Optional[int] = None
    check_textures: bool = True


@router.get("/status")
def get_3d_status() -> Dict[str, Any]:
    """Return Blender availability, export path, and supported game mod presets."""
    blender_exe = find_blender_executable()
    return {
        "blender_available": blender_exe is not None,
        "blender_path": str(blender_exe) if blender_exe else None,
        "export_dir": str(EXPORT_3D_DIR),
        "supported_formats": ["obj", "glb"],
        "supported_asset_types": list(SUPPORTED_ASSET_TYPES),
        "mod_presets": GAME_MOD_PRESETS,
    }


@router.get("/exports")
def list_3d_exports() -> Dict[str, Any]:
    """List exported 3D assets in F:\\AI-Office\\Export\\3D\\."""
    EXPORT_3D_DIR.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    for p in sorted(EXPORT_3D_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        stat = p.stat()
        items.append({
            "filename": p.name,
            "path": str(p),
            "format": p.suffix.lstrip(".").lower(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"export_dir": str(EXPORT_3D_DIR), "count": len(items), "files": items}


@router.post("/generate-asset")
def api_generate_3d_asset(req: Generate3DAssetRequest) -> Dict[str, Any]:
    """Generate a 3D asset (.obj/.glb), bpy script, metadata, and run topology validation."""
    try:
        result = generate_3d_asset(
            name=req.name,
            asset_type=req.asset_type,
            export_format=req.export_format,
            mod_preset=req.mod_preset,
            scale=req.scale,
            use_blender=req.use_blender,
            texture_path=req.texture_path,
        )
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("3D asset generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/validate-mod")
def api_validate_mod(req: ValidateModRequest) -> Dict[str, Any]:
    """Validate an existing .obj or .glb asset for game modding."""
    try:
        report = validate_3d_asset(
            file_path=req.file_path,
            max_polycount=req.max_polycount,
            check_textures=req.check_textures,
            mod_preset=req.mod_preset,
        )
        return report.to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("3D asset validation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def register_routes(app: FastAPI) -> None:
    """Register Blender 3D & Game Modding routes on FastAPI app."""
    app.include_router(router)
