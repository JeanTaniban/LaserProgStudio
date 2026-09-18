# -*- coding: utf-8 -*-
"""Runtime probe for the geometry-integrity mission.

This is intentionally diagnostic: it exercises production geometry generators and
reports topology/manifold metrics without mutating application code.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
import json
import math
import platform
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
import tempfile
import zipfile
from typing import Any
from dataclasses import asdict

import numpy as np

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology
from laserprog_studio.geometry_ops.manifold_contract import construct_manifold, manifold_is_valid
from laserprog_studio.geometry_ops.simplify import simplify_mesh
from laserprog_studio.geometry_ops.hollow import hollow_selected_meshes
from laserprog_studio.modifiers.split_plane import split_mesh_by_plane
from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box, build_cone, build_cylinder, build_sphere
from laserprog_studio.geometry_ops.acoustic_diffuser import AcousticDiffuserSettings, build_acoustic_diffuser
from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh
from laserprog_studio.tooling.mechanical_motion.geometry import build_gear_mesh, merge_meshes
from laserprog_studio.tooling.mechanical_motion.models import GearSpec
from laserprog_studio.tooling.mechanical_motion.compound_geometry import build_compound_shaft_mesh, _build_axial_hub_mesh
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.folding.geometry import arbitrary_face_plane, deform_mesh
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingMode, FoldingDeformationMode
from laserprog_studio.fabrication.layflat_core import MeshObject, merge_group, orient_piece_flat, read_3mf_meshes
from laserprog_studio.geometry_ops.image_mask_relief_builder import build_mask_relief_mesh
from laserprog_studio.geometry_ops.cavity_volume import measure_cavity_volume
from laserprog_studio.geometry_ops.extrude_down import extrude_mesh_down
from laserprog_studio.geometry_ops.text_relief import make_text_relief_mesh
from laserprog_studio.io.project_file import save_project, load_project
from laserprog_studio.project import ProjectStore
from laserprog_studio.geometry_ops.planar_boolean_solid import extrude_planar_regions_boolean_ready
from laserprog_studio.fabrication.box_generator import build_box_meshes
from laserprog_studio.fabrication.joint_builder_core import apply_tab_slot_simple
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan


def _area2(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return float(np.linalg.norm(np.cross(b - a, c - a)))


def _component_triangle_counts(triangles: list[tuple[int, int, int]]) -> list[int]:
    if not triangles:
        return []
    edge_to_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, tri in enumerate(triangles):
        a, b, c = map(int, tri)
        for x, y in ((a, b), (b, c), (c, a)):
            edge_to_tris[(x, y) if x < y else (y, x)].append(i)
    neighbours: list[set[int]] = [set() for _ in triangles]
    for owners in edge_to_tris.values():
        for i in owners:
            neighbours[i].update(j for j in owners if j != i)
    seen: set[int] = set()
    sizes: list[int] = []
    for start in range(len(triangles)):
        if start in seen:
            continue
        q = [start]
        seen.add(start)
        count = 0
        while q:
            cur = q.pop()
            count += 1
            for nxt in neighbours[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        sizes.append(count)
    return sorted(sizes, reverse=True)


def _manifold_metrics(value: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, method_name in (("volume", "volume"), ("surface_area", "surface_area")):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                out[key] = float(method())
            except Exception:
                pass
    decompose = getattr(value, "decompose", None)
    if callable(decompose):
        try:
            out["body_count"] = len(tuple(decompose()))
        except Exception:
            pass
    return out


def _manifold_probe(mesh: Any, *, merge: bool) -> dict[str, Any]:
    try:
        import manifold3d as m3d
        vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float64)
        triangles = np.asarray(getattr(mesh, "triangles", []) or [], dtype=np.int32)
        construction = construct_manifold(
            m3d,
            vertices=vertices[:, :3],
            triangles=triangles,
            merge=bool(merge),
            prefer_64bit=True,
        )
        result = {
            "status": str(construction.status),
            "valid": bool(manifold_is_valid(construction.manifold, m3d)),
            "merge_changed": bool(construction.merge_changed),
        }
        result.update(_manifold_metrics(construction.manifold))
        return result
    except Exception as exc:
        return {"status": f"exception:{type(exc).__name__}", "valid": False, "error": str(exc)}


def _production_boolean_probe(mesh: Any) -> dict[str, Any]:
    try:
        import manifold3d as m3d
        from laserprog_studio.boolean_ops import _prepared_boolean_arrays

        vertices, triangles, skip_merge = _prepared_boolean_arrays(mesh, label="probe")
        construction = construct_manifold(
            m3d,
            vertices=vertices,
            triangles=triangles,
            merge=not bool(skip_merge),
            prefer_64bit=True,
        )
        result = {
            "status": str(construction.status),
            "valid": bool(manifold_is_valid(construction.manifold, m3d)),
            "merge_changed": bool(construction.merge_changed),
            "skip_merge": bool(skip_merge),
            "prepared_triangles": int(len(triangles)),
        }
        result.update(_manifold_metrics(construction.manifold))
        return result
    except Exception as exc:
        return {"status": f"exception:{type(exc).__name__}", "valid": False, "error": str(exc)}


def audit_mesh(mesh: Any) -> dict[str, Any]:
    vertices = [tuple(float(v) for v in p[:3]) for p in (getattr(mesh, "vertices", []) or [])]
    triangles = [tuple(int(v) for v in t[:3]) for t in (getattr(mesh, "triangles", []) or [])]
    used: set[int] = set()
    invalid_indices = 0
    degenerate_indices = 0
    zero_area = 0
    duplicate_faces = 0
    edges: Counter[tuple[int, int]] = Counter()
    edge_dirs: defaultdict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    seen_faces: set[tuple[int, int, int]] = set()
    pts = np.asarray(vertices, dtype=np.float64) if vertices else np.empty((0, 3), dtype=np.float64)
    for tri in triangles:
        a, b, c = tri
        if min(a, b, c) < 0 or max(a, b, c) >= len(vertices):
            invalid_indices += 1
            continue
        used.update((a, b, c))
        if len({a, b, c}) != 3:
            degenerate_indices += 1
            continue
        if _area2(pts[a], pts[b], pts[c]) <= 1.0e-12:
            zero_area += 1
        canonical = tuple(sorted((a, b, c)))
        if canonical in seen_faces:
            duplicate_faces += 1
        seen_faces.add(canonical)
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            edges[key] += 1
            edge_dirs[key].append((x, y))
    boundary = sum(1 for n in edges.values() if n == 1)
    nonmanifold = sum(1 for n in edges.values() if n > 2)
    orientation_conflicts = 0
    for dirs in edge_dirs.values():
        if len(dirs) == 2 and dirs[0] == dirs[1]:
            orientation_conflicts += 1
    topo = analyze_work_mesh_boolean_topology(mesh).as_dict()
    return {
        "name": str(getattr(mesh, "name", "")),
        "vertices": len(vertices),
        "triangles": len(triangles),
        "unused_vertices": max(0, len(vertices) - len(used)),
        "invalid_indices": invalid_indices,
        "degenerate_index_triangles": degenerate_indices,
        "zero_area_triangles": zero_area,
        "duplicate_faces": duplicate_faces,
        "indexed_boundary_edges": boundary,
        "indexed_nonmanifold_edges": nonmanifold,
        "orientation_conflicts": orientation_conflicts,
        "edge_connected_components": _component_triangle_counts(triangles),
        "geometric_weld_contract": topo,
        "manifold_direct": _manifold_probe(mesh, merge=False),
        "manifold_after_merge": _manifold_probe(mesh, merge=True),
        "production_boolean_preparation": _production_boolean_probe(mesh),
    }


def _req(kind: str, **values: Any) -> PrimitiveBuildRequest:
    base = {
        "size_x": 20.0,
        "size_y": 20.0,
        "size_z": 20.0,
        "pos_x": 0.0,
        "pos_y": 0.0,
        "pos_z": 0.0,
        "segments": 48,
        "theta_resolution": 48,
        "phi_resolution": 24,
    }
    base.update(values)
    return PrimitiveBuildRequest(kind, base, 1)


def _vent_flared() -> WorkMesh:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 18.0
    draft.section.height = 8.0
    draft.section.area = 144.0
    draft.wall_thickness = 3.0
    draft.fill_area = False
    draft.waypoints = [(0.0, 0.0), (48.0, 0.0), (48.0, 34.0), (8.0, 34.0)]
    draft.selected_index = 2
    draft.set_selected_segment_curve(radius=12.0, strength=0.65)
    draft.flare_side = VentFlareSide.BOTH
    draft.flare_factor = 1.7
    draft.end_flare_finalized = True
    return make_vent_path_mesh(draft, name="probe_vent_flared")


def _touching_boxes() -> WorkMesh:
    a = build_box(_req("box", pos_x=0.0, pos_y=0.0, pos_z=0.0))
    b = build_box(_req("box", pos_x=20.0, pos_y=20.0, pos_z=20.0))
    return merge_meshes((a, b), name="two_boxes_point_contact")


def _touching_pair(offset: tuple[float, float, float], name: str) -> WorkMesh:
    a = build_box(_req("box", pos_x=0.0, pos_y=0.0, pos_z=0.0))
    b = build_box(_req("box", pos_x=float(offset[0]), pos_y=float(offset[1]), pos_z=float(offset[2])))
    return merge_meshes((a, b), name=name)


def _dumbbell() -> WorkMesh:
    from laserprog_studio.boolean_ops import boolean_union
    left = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0, pos_x=-15.0))
    right = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0, pos_x=15.0))
    bridge = build_box(_req("box", size_x=10.4, size_y=0.60, size_z=0.60, pos_x=0.0))
    return boolean_union(boolean_union(left, bridge), right)


def _manifold_simplify_probe(mesh: Any, tolerances: tuple[float, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        import manifold3d as m3d
        vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float64)
        triangles = np.asarray(getattr(mesh, "triangles", []) or [], dtype=np.int32)
        base = construct_manifold(
            m3d,
            vertices=vertices[:, :3],
            triangles=triangles,
            merge=False,
            prefer_64bit=True,
        ).manifold
        for tolerance in tolerances:
            try:
                simplified = base.simplify(float(tolerance))
                mesh_out = simplified.to_mesh64() if hasattr(simplified, "to_mesh64") else simplified.to_mesh()
                verts = np.asarray(mesh_out.vert_properties, dtype=float)
                tris = np.asarray(mesh_out.tri_verts, dtype=np.int32)
                wm = WorkMesh(
                    name=f"{getattr(mesh, 'name', 'mesh')} manifold_simplify_{tolerance:g}",
                    vertices=[tuple(map(float, row[:3])) for row in verts],
                    triangles=[tuple(map(int, row[:3])) for row in tris],
                )
                out[f"{tolerance:g}"] = audit_mesh(wm)
            except Exception as exc:
                out[f"{tolerance:g}"] = {"error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:
        out["setup_error"] = f"{type(exc).__name__}: {exc}"
    return out


def _write_probe_3mf(path: Path, *, unit: str = "millimeter", item_transform: str | None = None) -> None:
    transform_attr = f' transform="{item_transform}"' if item_transform else ""
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="{unit}" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0"/>
          <vertex x="1" y="0" z="0"/>
          <vertex x="0" y="1" z="0"/>
          <vertex x="0" y="0" z="1"/>
        </vertices>
        <triangles>
          <triangle v1="0" v2="2" v3="1"/>
          <triangle v1="0" v2="1" v3="3"/>
          <triangle v1="1" v2="2" v3="3"/>
          <triangle v1="2" v2="0" v3="3"/>
        </triangles>
      </mesh>
    </object>
  </resources>
  <build><item objectid="1"{transform_attr}/></build>
</model>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>'''
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("3D/3dmodel.model", xml)


def _mesh_bounds(mesh: Any) -> list[float]:
    vertices = list(getattr(mesh, "vertices", []) or [])
    if not vertices:
        return [0.0] * 6
    xs = [float(v[0]) for v in vertices]
    ys = [float(v[1]) for v in vertices]
    zs = [float(v[2]) for v in vertices]
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def _layflat_workmesh(mesh: Any, name: str) -> WorkMesh:
    src = MeshObject(
        name=name,
        vertices=list(getattr(mesh, "vertices", []) or []),
        triangles=list(getattr(mesh, "triangles", []) or []),
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
    )
    piece = merge_group([src], 1)
    orient_piece_flat(piece)
    return WorkMesh(name=name + "_layflat", vertices=list(piece.vertices), triangles=list(piece.triangles), color=piece.color)


def _mirror_x(mesh: Any, name: str) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(-float(v[0]), float(v[1]), float(v[2])) for v in (getattr(mesh, "vertices", []) or [])],
        triangles=[tuple(int(i) for i in tri[:3]) for tri in (getattr(mesh, "triangles", []) or [])],
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
        metadata=dict(getattr(mesh, "metadata", {}) or {}),
    )


def _cavity_measure_probe() -> dict[str, Any]:
    out: dict[str, Any] = {}
    outer = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0))
    cavity = build_box(_req("box", size_x=16.0, size_y=16.0, size_z=16.0))
    cavity.triangles = [(a, c, b) for a, b, c in cavity.triangles]
    island = build_box(_req("box", size_x=4.0, size_y=4.0, size_z=4.0))
    nested = merge_meshes((outer, cavity, island), name="nested_material_cavity_island")
    report = measure_cavity_volume(nested)
    out["nested_parity"] = {
        "reported_cavity_mm3": float(report.cavity_volume_mm3),
        "reported_material_mm3": float(report.solid_volume_liters_estimate * 1_000_000.0),
        "expected_cavity_mm3": float((16.0 ** 3) - (4.0 ** 3)),
        "expected_material_mm3": float((20.0 ** 3) - (16.0 ** 3) + (4.0 ** 3)),
        "cavity_count": int(report.cavity_count),
        "shell_count": int(report.shell_count),
        "warning": report.warning,
        "mesh": audit_mesh(nested),
    }
    return out


def _extrude_down_probe() -> dict[str, Any]:
    out: dict[str, Any] = {}
    cases = {
        "box_half": build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0, pos_z=10.0)),
        "sphere_half": build_sphere(_req("sphere", size_x=20.0, size_y=20.0, size_z=20.0, pos_z=10.0)),
        "cylinder_half": build_cylinder(_req("cylinder", size_x=20.0, size_y=20.0, size_z=20.0, pos_z=10.0)),
    }
    for name, source in cases.items():
        try:
            mesh, stats, warning = extrude_mesh_down(source, plane_z=10.0, ground_z=0.0)
            out[name] = {
                "warning": warning,
                "supports": int(stats.supports),
                "source": audit_mesh(source),
                "result": audit_mesh(mesh) if mesh is not None else None,
            }
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _folding_solid_probe() -> dict[str, Any]:
    out: dict[str, Any] = {}
    source = build_box(
        _req(
            "box",
            size_x=20.0,
            size_y=4.0,
            size_z=1.0,
            pos_x=5.0,
            pos_y=0.0,
            pos_z=0.5,
        )
    )
    source.name = "folding_closed_box"
    plane = arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    mid_plane = arbitrary_face_plane((0.0, 0.0, 0.5), (0.0, 0.0, 1.0))
    out["source"] = audit_mesh(source)
    cases = [
        ("uniform_90", 90.0, (0.0, 0.0, 0.0), FoldingDeformationMode.UNIFORM.value),
        ("uniform_180", 180.0, (0.0, 0.0, 0.0), FoldingDeformationMode.UNIFORM.value),
        ("uniform_270", 270.0, (0.0, 0.0, 0.0), FoldingDeformationMode.UNIFORM.value),
        ("uniform_450", 450.0, (0.0, 0.0, 0.0), FoldingDeformationMode.UNIFORM.value),
        ("uniform_720", 720.0, (0.0, 0.0, 0.0), FoldingDeformationMode.UNIFORM.value),
        ("preserve_180", 180.0, (0.0, 0.0, 0.0), FoldingDeformationMode.PRESERVE_STRUCTURE.value),
        ("s_curve", 120.0, (100.0, -150.0, 80.0), FoldingDeformationMode.PRESERVE_STRUCTURE.value),
    ]
    for name, angle, shape, mode in cases:
        curve = FoldingCurve(
            start=(0.0, 0.0, 0.0),
            end=(10.0, 0.0, 0.0),
            mode=FoldingMode.LIVING_HINGE.value,
            fold_angle_deg=angle,
            shape_angles_deg=shape,
            deformation_mode=mode,
        )
        try:
            folded = deform_mesh(source, plane, curve)
            out[name] = audit_mesh(folded)
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}

    for angle in (90.0, 180.0, 270.0, 450.0, 720.0):
        curve = FoldingCurve(
            start=(0.0, 0.0, 0.5),
            end=(10.0, 0.0, 0.5),
            mode=FoldingMode.LIVING_HINGE.value,
            fold_angle_deg=angle,
            shape_angles_deg=(0.0, 0.0, 0.0),
            deformation_mode=FoldingDeformationMode.UNIFORM.value,
        )
        try:
            folded = deform_mesh(source, mid_plane, curve)
            out[f"midplane_uniform_{angle:.0f}"] = audit_mesh(folded)
        except Exception as exc:
            out[f"midplane_uniform_{angle:.0f}"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _relief_probe() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        text_mesh = make_text_relief_mesh(
            text="AB8",
            anchor_point=(0.0, 0.0, 0.0),
            normal=(0.0, 0.0, 1.0),
            size_mm=12.0,
            depth_mm=1.5,
            font_family="VTK VectorText",
        )
        out["text"] = audit_mesh(text_mesh)
    except Exception as exc:
        out["text"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        from PIL import Image

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "mask.png"
            image = Image.new("L", (12, 12), color=255)
            for x in range(2, 10):
                for y in range(2, 10):
                    image.putpixel((x, y), 0 if (x + y) % 3 else 80)
            image.save(image_path)
            for binary in (False, True):
                result = build_mask_relief_mesh(
                    image_path,
                    max_height_mm=2.0,
                    pixel_size_mm=0.5,
                    invert=False,
                    binary=binary,
                    max_grid_size=64,
                )
                mesh = result.mesh
                key = "image_binary" if binary else "image_grayscale"
                out[key] = {
                    "mesh": audit_mesh(mesh),
                    "runtime_skip_merge": bool(getattr(mesh, "_lps_skip_boolean_merge", False)),
                    "metadata_skip_merge": bool((getattr(mesh, "metadata", {}) or {}).get("boolean_skip_merge", False)),
                    "project_roundtrip": _project_roundtrip_probe(mesh),
                }
    except Exception as exc:
        out["image"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _three_mf_roundtrip_probe(mesh: Any) -> dict[str, Any]:
    try:
        from laserprog_studio.domain.work_model import ModelStore
        store = ModelStore()
        store.set_meshes([mesh], push_undo=False)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "roundtrip.3mf"
            store.export_3mf(path)
            loaded = read_3mf_meshes(path)
            return {
                "mesh_count": len(loaded),
                "meshes": [
                    audit_mesh(
                        WorkMesh(
                            name=obj.name,
                            vertices=list(obj.vertices),
                            triangles=list(obj.triangles),
                            color=obj.color,
                        )
                    )
                    for obj in loaded
                ],
            }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _project_roundtrip_probe(mesh: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        project = ProjectStore.new_empty(scene_name="probe")
        project.active_model_store.set_meshes([mesh])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "probe.lpsproj"
            save_project(project, path)
            loaded = load_project(path)
            loaded_mesh = loaded.active_model_store.committed_meshes[0]
            out = {
                "source_runtime_skip_merge": bool(getattr(mesh, "_lps_skip_boolean_merge", False)),
                "source_metadata_skip_merge": bool((getattr(mesh, "metadata", {}) or {}).get("boolean_skip_merge", False)),
                "loaded_runtime_skip_merge": bool(getattr(loaded_mesh, "_lps_skip_boolean_merge", False)),
                "loaded_metadata_skip_merge": bool((getattr(loaded_mesh, "metadata", {}) or {}).get("boolean_skip_merge", False)),
                "source_audit": audit_mesh(mesh),
                "loaded_audit": audit_mesh(loaded_mesh),
            }
    except Exception as exc:
        out = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _tool_output_probe() -> dict[str, Any]:
    out: dict[str, Any] = {}

    # Plan Tracer: a real planar solid with one inner opening.
    try:
        outer = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0))
        hole = ((15.0, 10.0), (25.0, 10.0), (25.0, 20.0), (15.0, 20.0))
        plan_mesh, plan_report = extrude_planar_regions_boolean_ready(
            [(outer, (hole,))],
            plane=make_locked_plane("top"),
            depth=3.0,
        )
        out["plan_tracer"] = {
            "report": {
                key: getattr(plan_report, key)
                for key in (
                    "backend",
                    "boundary_edges",
                    "nonmanifold_edges",
                    "nonmanifold_vertices",
                    "signed_volume",
                )
                if hasattr(plan_report, key)
            },
            "mesh": audit_mesh(plan_mesh),
        }
    except Exception as exc:
        out["plan_tracer"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Box Generator: every board is a manufacturing solid, while the complete
    # generated box remains a scene-level assembly rather than one pseudo-solid.
    try:
        boards, box_meshes, metrics = build_box_meshes(
            100.0,
            80.0,
            60.0,
            3.0,
            group_id="geometry-audit-box",
        )
        out["box_generator"] = {
            "board_count": len(box_meshes),
            "inner_volume_mm3": float(metrics.inner_volume_mm3),
            "boards": [audit_mesh(mesh) for mesh in box_meshes],
        }
    except Exception as exc:
        out["box_generator"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Joint Builder: two perpendicular 3 mm boards touching on a 60 x 3 mm face.
    try:
        board_a = build_box(
            _req(
                "box",
                size_x=60.0,
                size_y=40.0,
                size_z=3.0,
                pos_x=0.0,
                pos_y=0.0,
                pos_z=1.5,
            )
        )
        board_a.name = "joint_board_A"
        board_b = build_box(
            _req(
                "box",
                size_x=60.0,
                size_y=3.0,
                size_z=40.0,
                pos_x=0.0,
                pos_y=21.5,
                pos_z=20.0,
            )
        )
        board_b.name = "joint_board_B"
        joint_result = apply_tab_slot_simple(
            board_a,
            board_b,
            touch_tolerance=0.10,
            clearance=0.15,
            joint_size=8.0,
            joint_count=2,
            joint_edge_margin=2.0,
            single_depth_probe=True,
        )
        male, female = joint_result[:2]
        out["joint_builder"] = {
            "source_a": audit_mesh(board_a),
            "source_b": audit_mesh(board_b),
            "male": audit_mesh(male),
            "female": audit_mesh(female),
        }
    except Exception as exc:
        out["joint_builder"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Cloth: folded output is a solid, flat output is intentionally a surface.
    try:
        document = ClothDocument()
        drawing = ClothDrawingController(document)
        created = drawing.create_surface_from_positions(
            (
                (0.0, 0.0, 0.0),
                (30.0, 0.0, 0.0),
                (30.0, 20.0, 0.0),
                (0.0, 20.0, 0.0),
            )
        )
        if not created.committed:
            raise RuntimeError(f"Cloth rectangle was not committed: {created.message}")
        plan = build_cloth_apply_plan(document, name="geometry-audit-cloth")
        out["cloth"] = {
            "ready": bool(plan.ready),
            "issues": list(plan.issues),
            "folded_solid": audit_mesh(plan.folded_mesh) if plan.folded_mesh is not None else None,
            "folded_project_roundtrip": (
                _project_roundtrip_probe(plan.folded_mesh)
                if plan.folded_mesh is not None
                else None
            ),
            "flat_surface": audit_mesh(plan.flat_mesh) if plan.flat_mesh is not None else None,
        }
    except Exception as exc:
        out["cloth"] = {"error": f"{type(exc).__name__}: {exc}"}

    return out


def _apply_affine(mesh: Any, matrix: np.ndarray, name: str) -> WorkMesh:
    pts = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float64)
    linear = np.asarray(matrix, dtype=np.float64)
    if linear.shape != (4, 4):
        raise ValueError("Expected a 4x4 affine matrix.")
    if pts.size == 0:
        transformed = pts.reshape((-1, 3))
    else:
        homo = np.column_stack((pts[:, :3], np.ones(len(pts), dtype=np.float64)))
        transformed = (homo @ linear.T)[:, :3]
    return WorkMesh(
        name=name,
        vertices=[tuple(map(float, row)) for row in transformed],
        triangles=[tuple(map(int, tri[:3])) for tri in (getattr(mesh, "triangles", []) or [])],
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
    )


def _affine_contract_probe() -> dict[str, Any]:
    source = build_box(_req("box", size_x=20.0, size_y=10.0, size_z=6.0))
    out: dict[str, Any] = {"source": audit_mesh(source)}
    angle = math.radians(33.0)
    transforms = {
        "translate_rotate": np.array([
            [math.cos(angle), -math.sin(angle), 0.0, 12.0],
            [math.sin(angle), math.cos(angle), 0.0, -7.0],
            [0.0, 0.0, 1.0, 4.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float64),
        "positive_nonuniform_scale": np.diag([2.0, 0.5, 1.5, 1.0]),
        "mirror_x": np.diag([-1.0, 1.0, 1.0, 1.0]),
        "near_singular_x": np.diag([1.0e-12, 1.0, 1.0, 1.0]),
        "singular_x": np.diag([0.0, 1.0, 1.0, 1.0]),
    }
    for key, matrix in transforms.items():
        candidate = _apply_affine(source, matrix, f"affine_{key}")
        out[key] = {
            "determinant": float(np.linalg.det(matrix[:3, :3])),
            "mesh": audit_mesh(candidate),
        }
    return out


def _split_raw_fallback_probe() -> dict[str, Any]:
    try:
        from laserprog_studio.modifiers.split_plane import _mesh_to_polydata, _polydata_to_workmesh

        source = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0))
        poly = _mesh_to_polydata(source)
        clipped = poly.clip(normal=(1.0, 0.0, 0.0), origin=(0.0, 0.0, 0.0), invert=False).triangulate().clean()
        result = _polydata_to_workmesh(
            clipped,
            name="split_raw_clip_fallback",
            color=source.color,
            source_mesh=source,
        )
        return {
            "source": audit_mesh(source),
            "fallback_result": audit_mesh(result) if result is not None else None,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _repair_open_mesh_probe() -> dict[str, Any]:
    try:
        from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh

        source = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0))
        source.triangles = list(source.triangles[:-2])
        repaired, repair_report = repair_work_mesh(
            source,
            tolerance_mm=0.005,
            fill_holes=True,
            remove_tiny_faces=True,
            optional_backends=True,
        )
        return {
            "source": audit_mesh(source),
            "repair_report": asdict(repair_report),
            "result": audit_mesh(repaired),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    def _pkg_version(name: str) -> str:
        try:
            return str(importlib_metadata.version(name))
        except Exception:
            return "unknown"

    try:
        import manifold3d as m3d
        manifold_capabilities = {
            "version": _pkg_version("manifold3d"),
            "has_mesh64": bool(hasattr(m3d, "Mesh64")),
            "manifold_methods": sorted(
                name for name in ("simplify", "decompose", "refine", "volume", "surface_area")
                if hasattr(m3d.Manifold, name)
            ),
        }
    except Exception as exc:
        manifold_capabilities = {"error": f"{type(exc).__name__}: {exc}"}
    environment = {
        "platform": platform.platform(),
        "system": platform.system(),
        "python": sys.version,
        "packages": {
            "manifold3d": _pkg_version("manifold3d"),
            "numpy": _pkg_version("numpy"),
            "pyvista": _pkg_version("pyvista"),
            "vtk": _pkg_version("vtk"),
            "shapely": _pkg_version("shapely"),
        },
    }
    report: dict[str, Any] = {
        "environment": environment,
        "manifold": manifold_capabilities,
        "cases": {},
        "simplify": {},
        "inter_tool": {},
        "formats": {},
        "relief": {},
        "tool_outputs": {},
        "affine": {},
    }

    report["tool_outputs"] = _tool_output_probe()
    report["affine"] = _affine_contract_probe()
    report["inter_tool"]["split_raw_fallback"] = _split_raw_fallback_probe()
    report["inter_tool"]["repair_open_mesh"] = _repair_open_mesh_probe()

    with tempfile.TemporaryDirectory() as td:
        inch_path = Path(td) / "unit_inch.3mf"
        _write_probe_3mf(inch_path, unit="inch")
        imported = read_3mf_meshes(inch_path)
        report["formats"]["3mf_unit_inch"] = {
            "mesh_count": len(imported),
            "bounds": _mesh_bounds(imported[0]) if imported else None,
            "expected_extent_mm": 25.4,
        }

        mirror_path = Path(td) / "mirror.3mf"
        _write_probe_3mf(
            mirror_path,
            unit="millimeter",
            item_transform="-1 0 0 0 1 0 0 0 1 0 0 0",
        )
        mirrored = read_3mf_meshes(mirror_path)
        report["formats"]["3mf_mirrored_instance"] = (
            audit_mesh(
                WorkMesh(
                    name=mirrored[0].name,
                    vertices=list(mirrored[0].vertices),
                    triangles=list(mirrored[0].triangles),
                    color=mirrored[0].color,
                )
            )
            if mirrored
            else {"error": "no mesh"}
        )

    report["relief"] = _relief_probe()
    report["inter_tool"]["cavity_measure"] = _cavity_measure_probe()
    report["inter_tool"]["extrude_down"] = _extrude_down_probe()
    report["inter_tool"]["folding_closed_solid"] = _folding_solid_probe()

    for example_name in ("box.3mf", "layflat_parts.3mf"):
        example_path = Path("examples") / example_name
        try:
            example_meshes = read_3mf_meshes(example_path)
            report["formats"][f"example_{example_name}"] = {
                "mesh_count": len(example_meshes),
                "meshes": [
                    audit_mesh(
                        WorkMesh(
                            name=obj.name,
                            vertices=list(obj.vertices),
                            triangles=list(obj.triangles),
                            color=obj.color,
                        )
                    )
                    for obj in example_meshes
                ],
            }
        except Exception as exc:
            report["formats"][f"example_{example_name}"] = {
                "error": f"{type(exc).__name__}: {exc}"
            }

    # Mechanical compound comparison: real boolean union vs forced fallback concat.
    try:
        plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
        compound_gears = (
            GearSpec(
                name="compound A",
                center=(0.0, 0.0, 3.0),
                teeth=24,
                module_mm=2.0,
                thickness_mm=6.0,
                bore_diameter_mm=5.0,
                shaft_id="shaft_probe",
                stage_index=0,
            ),
            GearSpec(
                name="compound B",
                center=(0.0, 0.0, 10.0),
                teeth=36,
                module_mm=1.5,
                thickness_mm=6.0,
                bore_diameter_mm=5.0,
                shaft_id="shaft_probe",
                stage_index=1,
            ),
        )
        compound_union = build_compound_shaft_mesh(compound_gears, plane=plane, name="compound_union")
        import laserprog_studio.boolean_ops as _bool_mod
        original_union = _bool_mod.boolean_union
        try:
            def _forced_union_failure(*_args: Any, **_kwargs: Any):
                raise RuntimeError("forced compound boolean failure")
            _bool_mod.boolean_union = _forced_union_failure
            compound_fallback = build_compound_shaft_mesh(compound_gears, plane=plane, name="compound_fallback")
        finally:
            _bool_mod.boolean_union = original_union
        mechanical_report = {
            "union": audit_mesh(compound_union),
            "fallback": audit_mesh(compound_fallback),
            "fallback_marker": bool((getattr(compound_fallback, "metadata", {}) or {}).get("mechanical_compound_union_fallback", False)),
        }

        # Isolate Manifold output conversion precision. Production currently
        # converts canonical boolean results with to_mesh() even though inputs use Mesh64.
        try:
            import manifold3d as m3d
            import numpy as _np
            from laserprog_studio.boolean_ops import _construct_valid_manifold

            sorted_gears = tuple(sorted(compound_gears, key=lambda g: sum(float(g.center[i]) * float(plane.normal[i]) for i in range(3))))
            raw_parts = [build_gear_mesh(g, plane=plane) for g in sorted_gears]
            raw_parts.append(_build_axial_hub_mesh(sorted_gears, plane=plane, name="probe hub"))
            raw_manifolds = []
            for idx, part in enumerate(raw_parts):
                manifold_value, _prepared, _attempts = _construct_valid_manifold(
                    part,
                    label=f"mechanical_raw_{idx}",
                    np=_np,
                    m3d=m3d,
                )
                raw_manifolds.append(manifold_value)
            raw_union = raw_manifolds[0]
            for value in raw_manifolds[1:]:
                raw_union = raw_union.add(value) if hasattr(raw_union, "add") else (raw_union + value)

            conversions = {}
            for method_name in ("to_mesh", "to_mesh64"):
                method = getattr(raw_union, method_name, None)
                if not callable(method):
                    conversions[method_name] = {"available": False}
                    continue
                converted = method()
                vp = _np.asarray(converted.vert_properties, dtype=float)
                tp = _np.asarray(converted.tri_verts, dtype=_np.int32)
                wm = WorkMesh(
                    name=f"mechanical_raw_{method_name}",
                    vertices=[tuple(map(float, row[:3])) for row in vp],
                    triangles=[tuple(map(int, row[:3])) for row in tp],
                )
                conversions[method_name] = {
                    "available": True,
                    "audit": audit_mesh(wm),
                }
            mechanical_report["canonical_conversion"] = conversions

            # Reproduce LaserProg's chained-boolean architecture while varying
            # only the intermediate Manifold -> WorkMesh conversion precision.
            chained = {}
            for method_name in ("to_mesh", "to_mesh64"):
                current = raw_manifolds[0]
                history = []
                available = True
                for step_idx, next_manifold in enumerate(raw_manifolds[1:], start=1):
                    current = current.add(next_manifold) if hasattr(current, "add") else (current + next_manifold)
                    method = getattr(current, method_name, None)
                    if not callable(method):
                        available = False
                        break
                    converted = method()
                    vp = _np.asarray(converted.vert_properties, dtype=float)
                    tp = _np.asarray(converted.tri_verts, dtype=_np.int32)
                    wm = WorkMesh(
                        name=f"mechanical_chain_{method_name}_{step_idx}",
                        vertices=[tuple(map(float, row[:3])) for row in vp],
                        triangles=[tuple(map(int, row[:3])) for row in tp],
                    )
                    history.append(audit_mesh(wm))
                    if step_idx < len(raw_manifolds) - 1:
                        current, _prepared, _attempts = _construct_valid_manifold(
                            wm,
                            label=f"mechanical_chain_{method_name}_{step_idx}",
                            np=_np,
                            m3d=m3d,
                        )
                chained[method_name] = {
                    "available": available,
                    "steps": history,
                }
            mechanical_report["intermediate_conversion_chain"] = chained
        except Exception as exc:
            mechanical_report["canonical_conversion"] = {
                "error": f"{type(exc).__name__}: {exc}",
            }

        report["inter_tool"]["mechanical_compound_union_vs_fallback"] = mechanical_report
    except Exception as exc:
        report["inter_tool"]["mechanical_compound_union_vs_fallback"] = {
            "error": f"{type(exc).__name__}: {exc}",
        }

    primitives = {
        "primitive_box": build_box(_req("box")),
        "primitive_cylinder": build_cylinder(_req("cylinder")),
        "primitive_cone": build_cone(_req("cone")),
        "primitive_sphere": build_sphere(_req("sphere")),
        "mechanical_gear_bore": build_gear_mesh(GearSpec(name="probe gear", teeth=24, module_mm=2.0, thickness_mm=6.0, bore_diameter_mm=5.0)),
        "touching_boxes_indexed_distinct": _touching_boxes(),
        "touching_boxes_edge_contact": _touching_pair((20.0, 20.0, 0.0), "two_boxes_edge_contact"),
        "touching_boxes_face_contact": _touching_pair((20.0, 0.0, 0.0), "two_boxes_face_contact"),
    }
    for name, mesh in primitives.items():
        report["cases"][name] = audit_mesh(mesh)

    # Lay Flat grouping currently concatenates overlapping parts instead of performing
    # a volumetric union. Probe the semantic difference explicitly.
    overlap_a = build_box(_req("box", pos_x=-5.0))
    overlap_b = build_box(_req("box", pos_x=5.0))
    overlap_piece = merge_group(
        [
            MeshObject("overlap_a", list(overlap_a.vertices), list(overlap_a.triangles), overlap_a.color),
            MeshObject("overlap_b", list(overlap_b.vertices), list(overlap_b.triangles), overlap_b.color),
        ],
        1,
    )
    overlap_merged = WorkMesh(
        name="layflat_overlap_concat",
        vertices=list(overlap_piece.vertices),
        triangles=list(overlap_piece.triangles),
        color=overlap_piece.color,
    )
    report["inter_tool"]["layflat_overlap_concat"] = audit_mesh(overlap_merged)

    acoustic = build_acoustic_diffuser(AcousticDiffuserSettings(quality=32))
    for i, mesh in enumerate(acoustic.meshes):
        report["cases"][f"acoustic_{i}"] = audit_mesh(mesh)

    vent = _vent_flared()
    report["cases"]["vent_flared"] = audit_mesh(vent)

    box = primitives["primitive_box"]
    split_parts = split_mesh_by_plane(box, origin=(0.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0))
    report["inter_tool"]["split_box"] = {
        "piece_count": len(split_parts),
        "pieces": [audit_mesh(part) for part in split_parts],
    }

    hollow = hollow_selected_meshes([box], [0], thickness=2.0)
    report["inter_tool"]["hollow_box"] = {
        "ok": bool(hollow.ok),
        "errors": list(hollow.errors),
        "mesh": audit_mesh(hollow.meshes[0]) if hollow.ok and hollow.meshes else None,
    }
    if hollow.ok and hollow.meshes:
        hollow_mesh = hollow.meshes[0]
        report["inter_tool"]["hollow_to_layflat"] = {
            "source": audit_mesh(hollow_mesh),
            "layflat": audit_mesh(_layflat_workmesh(hollow_mesh, "hollow_box")),
        }
        report["inter_tool"]["hollow_3mf_roundtrip"] = _three_mf_roundtrip_probe(hollow_mesh)
        report["inter_tool"]["hollow_project_roundtrip"] = _project_roundtrip_probe(hollow_mesh)
        cavity_report = measure_cavity_volume(hollow_mesh)
        report["inter_tool"]["hollow_cavity_measure"] = {
            "cavity_volume_mm3": float(cavity_report.cavity_volume_mm3),
            "outer_volume_mm3": float(cavity_report.outer_volume_mm3),
            "material_estimate_mm3": float(cavity_report.solid_volume_liters_estimate * 1_000_000.0),
            "cavity_count": int(cavity_report.cavity_count),
            "shell_count": int(cavity_report.shell_count),
            "warning": cavity_report.warning,
        }
        try:
            from laserprog_studio.boolean_ops import split_disconnected_mesh
            separated_hollow = split_disconnected_mesh(hollow_mesh)
            report["inter_tool"]["hollow_to_boolean_separate"] = {
                "part_count": len(separated_hollow),
                "parts": [audit_mesh(part) for part in separated_hollow],
            }
        except Exception as exc:
            report["inter_tool"]["hollow_to_boolean_separate"] = {
                "error": f"{type(exc).__name__}: {exc}",
            }
        mirrored_hollow = _mirror_x(hollow_mesh, "hollow_box_mirrored")
        report["inter_tool"]["hollow_mirrored"] = audit_mesh(mirrored_hollow)

        try:
            from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh
            repaired_hollow, repair_report = repair_work_mesh(
                hollow_mesh,
                tolerance_mm=1.0e-6,
                fill_holes=False,
                remove_tiny_faces=False,
                optional_backends=False,
            )
            report["inter_tool"]["hollow_to_repair"] = {
                "repair_report": asdict(repair_report),
                "source": audit_mesh(hollow_mesh),
                "result": audit_mesh(repaired_hollow),
            }
        except Exception as exc:
            report["inter_tool"]["hollow_to_repair"] = {
                "error": f"{type(exc).__name__}: {exc}",
            }

        try:
            split_hollow = split_mesh_by_plane(
                hollow_mesh,
                origin=(0.0, 0.0, 0.0),
                normal=(1.0, 0.0, 0.0),
            )
            report["inter_tool"]["hollow_to_split"] = {
                "piece_count": len(split_hollow),
                "pieces": [audit_mesh(piece) for piece in split_hollow],
            }
            split_hollow_oblique = split_mesh_by_plane(
                hollow_mesh,
                origin=(1.5, 0.0, 0.0),
                normal=(1.0, 1.0, 0.35),
            )
            report["inter_tool"]["hollow_to_split_oblique"] = {
                "piece_count": len(split_hollow_oblique),
                "pieces": [audit_mesh(piece) for piece in split_hollow_oblique],
            }
        except Exception as exc:
            report["inter_tool"]["hollow_to_split"] = {
                "error": f"{type(exc).__name__}: {exc}",
            }

        try:
            from laserprog_studio.boolean_ops import boolean_difference
            cavity_probe = build_box(_req("box", size_x=4.0, size_y=4.0, size_z=4.0))
            hollow_cut = boolean_difference(hollow.meshes[0], cavity_probe, cutter_margin_mm=0.0)
            report["inter_tool"]["hollow_boolean_cavity_probe"] = {
                "ok": True,
                "result": audit_mesh(hollow_cut),
            }
        except Exception as exc:
            report["inter_tool"]["hollow_boolean_cavity_probe"] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    hollow_vent = hollow_selected_meshes([vent], [0], thickness=1.0)
    report["inter_tool"]["vent_to_hollow"] = {
        "ok": bool(hollow_vent.ok),
        "errors": list(hollow_vent.errors),
    }

    try:
        dumbbell = _dumbbell()
        report["cases"]["dumbbell_source"] = audit_mesh(dumbbell)
        concave_hollow_cases = {}
        for thickness in (0.25, 0.50, 1.0, 2.0, 4.0):
            try:
                hollow_dumbbell = hollow_selected_meshes([dumbbell], [0], thickness=thickness)
                concave_hollow_cases[f"{thickness:.2f}"] = {
                    "ok": bool(hollow_dumbbell.ok),
                    "errors": list(hollow_dumbbell.errors),
                    "mesh": audit_mesh(hollow_dumbbell.meshes[0]) if hollow_dumbbell.ok and hollow_dumbbell.meshes else None,
                }
            except Exception as exc:
                concave_hollow_cases[f"{thickness:.2f}"] = {
                    "error": f"{type(exc).__name__}: {exc}",
                }
        report["inter_tool"]["hollow_concave_dumbbell"] = concave_hollow_cases
        report["simplify"]["manifold_dumbbell"] = _manifold_simplify_probe(
            dumbbell,
            (0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 1.0),
        )
        for preserve in (True, False):
            for reduction in (0.50, 0.75, 0.90, 0.95):
                out, error = simplify_mesh(dumbbell, reduction, preserve_topology=preserve)
                key = f"dumbbell_preserve_{int(preserve)}_reduction_{reduction:.2f}"
                report["simplify"][key] = {
                    "error": error,
                    "mesh": audit_mesh(out) if out is not None else None,
                }
    except Exception as exc:
        report["simplify"]["dumbbell_setup"] = {"error": f"{type(exc).__name__}: {exc}"}

    sphere = primitives["primitive_sphere"]
    for preserve in (True, False):
        for reduction in (0.50, 0.75, 0.90, 0.95):
            out, error = simplify_mesh(sphere, reduction, preserve_topology=preserve)
            key = f"sphere_preserve_{int(preserve)}_reduction_{reduction:.2f}"
            report["simplify"][key] = {
                "error": error,
                "mesh": audit_mesh(out) if out is not None else None,
            }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
