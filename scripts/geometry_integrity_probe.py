# -*- coding: utf-8 -*-
"""Runtime probe for the geometry-integrity mission.

This is intentionally diagnostic: it exercises production geometry generators and
reports topology/manifold metrics without mutating application code.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
import json
import math
from pathlib import Path
import tempfile
import zipfile
from typing import Any

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
from laserprog_studio.fabrication.layflat_core import MeshObject, merge_group, orient_piece_flat, read_3mf_meshes
from laserprog_studio.geometry_ops.image_mask_relief_builder import build_mask_relief_mesh
from laserprog_studio.geometry_ops.text_relief import make_text_relief_mesh
from laserprog_studio.io.project_file import save_project, load_project
from laserprog_studio.project import ProjectStore


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


def main() -> int:
    try:
        import manifold3d as m3d
        manifold_capabilities = {
            "version": str(getattr(m3d, "__version__", "unknown")),
            "has_mesh64": bool(hasattr(m3d, "Mesh64")),
            "manifold_methods": sorted(
                name for name in ("simplify", "decompose", "refine", "volume", "surface_area")
                if hasattr(m3d.Manifold, name)
            ),
        }
    except Exception as exc:
        manifold_capabilities = {"error": f"{type(exc).__name__}: {exc}"}
    report: dict[str, Any] = {"manifold": manifold_capabilities, "cases": {}, "simplify": {}, "inter_tool": {}, "formats": {}, "relief": {}}

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
                "repair_report": dict(repair_report.__dict__),
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
        try:
            hollow_dumbbell = hollow_selected_meshes([dumbbell], [0], thickness=1.0)
            report["inter_tool"]["hollow_concave_dumbbell"] = {
                "ok": bool(hollow_dumbbell.ok),
                "errors": list(hollow_dumbbell.errors),
                "mesh": audit_mesh(hollow_dumbbell.meshes[0]) if hollow_dumbbell.ok and hollow_dumbbell.meshes else None,
            }
        except Exception as exc:
            report["inter_tool"]["hollow_concave_dumbbell"] = {
                "error": f"{type(exc).__name__}: {exc}",
            }
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
