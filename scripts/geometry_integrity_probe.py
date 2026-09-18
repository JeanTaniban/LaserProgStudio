# -*- coding: utf-8 -*-
"""Runtime probe for the geometry-integrity mission.

This is intentionally diagnostic: it exercises production geometry generators and
reports topology/manifold metrics without mutating application code.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
import json
import math
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
        return {
            "status": str(construction.status),
            "valid": bool(manifold_is_valid(construction.manifold, m3d)),
            "merge_changed": bool(construction.merge_changed),
        }
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


def _dumbbell() -> WorkMesh:
    from laserprog_studio.boolean_ops import boolean_union
    left = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0, pos_x=-15.0))
    right = build_box(_req("box", size_x=20.0, size_y=20.0, size_z=20.0, pos_x=15.0))
    bridge = build_box(_req("box", size_x=10.4, size_y=0.60, size_z=0.60, pos_x=0.0))
    return boolean_union(boolean_union(left, bridge), right)


def main() -> int:
    report: dict[str, Any] = {"cases": {}, "simplify": {}, "inter_tool": {}}

    primitives = {
        "primitive_box": build_box(_req("box")),
        "primitive_cylinder": build_cylinder(_req("cylinder")),
        "primitive_cone": build_cone(_req("cone")),
        "primitive_sphere": build_sphere(_req("sphere")),
        "mechanical_gear_bore": build_gear_mesh(GearSpec(name="probe gear", teeth=24, module_mm=2.0, thickness_mm=6.0, bore_diameter_mm=5.0)),
        "touching_boxes_indexed_distinct": _touching_boxes(),
    }
    for name, mesh in primitives.items():
        report["cases"][name] = audit_mesh(mesh)

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

    hollow_vent = hollow_selected_meshes([vent], [0], thickness=1.0)
    report["inter_tool"]["vent_to_hollow"] = {
        "ok": bool(hollow_vent.ok),
        "errors": list(hollow_vent.errors),
    }

    try:
        dumbbell = _dumbbell()
        report["cases"]["dumbbell_source"] = audit_mesh(dumbbell)
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
