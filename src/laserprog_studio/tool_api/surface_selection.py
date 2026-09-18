"""Public intelligent mesh-surface selection API.

Tools should import this module rather than the headless implementation path.
"""
from __future__ import annotations

import math
from typing import Iterable

from laserprog_studio.tool_core.surface_selection import (
    EdgeKey,
    Point3,
    SurfaceAccessibilityField,
    SurfaceMeshSnapshot,
    SurfaceRegionMetrics,
    SurfaceRegionResult,
    SurfaceSelectionCache,
    SurfaceSelectionDiagnosticSink,
    SurfaceSelectionPointerAction,
    SurfaceSelectionPointerMachine,
    SurfaceSelectionPointerState,
    SurfaceSelectionMeshPolicy,
    SurfaceSelectionProfile,
    SurfaceSelectionSession,
    Triangle,
    auto_surface_region,
    select_surface_region,
    surface_region_from_faces,
)


def snapshot_from_pick(ctx, pick, *, diagnostics: SurfaceSelectionDiagnosticSink | None = None) -> SurfaceMeshSnapshot | None:
    """Build a canonical immutable snapshot for a face pick."""

    if pick is None or not bool(getattr(pick, "hit", False)):
        return None
    obj = None
    try:
        object_id = getattr(pick, "object_id", None)
        if object_id is not None:
            obj = ctx.document.get(str(object_id))
    except Exception:
        obj = None
    if obj is None:
        try:
            index = getattr(pick, "object_index", None)
            if index is not None:
                obj = ctx.document.objects()[int(index)]
        except Exception:
            obj = None
    if obj is None:
        return None
    mesh = getattr(obj, "mesh", None) or obj
    object_id = str(getattr(pick, "object_id", "") or getattr(obj, "id", "") or getattr(mesh, "mesh_id", "") or id(mesh))
    revision = str(getattr(mesh, "geometry_revision", "") or getattr(mesh, "revision", "") or "")
    try:
        return SurfaceMeshSnapshot.from_mesh(obj, object_id=object_id, revision_token=revision, diagnostics=diagnostics)
    except Exception:
        return None


def face_index_from_pick(
    pick,
    snapshot: SurfaceMeshSnapshot | None = None,
) -> int | None:
    """Resolve the picked display cell to the canonical mesh triangle.

    A VTK actor can use a rebuilt or reordered dataset, so its ``cell_id`` is
    not a guaranteed triangle index in the document mesh.  When a snapshot is
    supplied, the displayed cell vertices and the exact world hit are used to
    validate/remap the raw id.  The raw id is retained only as a safe fallback.
    """

    try:
        raw = int(getattr(pick, "element_index"))
    except Exception:
        raw = -1
    if snapshot is None:
        return raw if raw >= 0 else None

    triangle_count = len(snapshot.triangles)
    raw_valid = 0 <= raw < triangle_count
    tolerance = max(1.0e-7, float(snapshot.diagonal) * 2.0e-6)
    metadata = getattr(pick, "metadata", None) or {}
    picked_vertices = _pick_points(metadata.get("face_vertices"))
    world_pos = _point_or_none(getattr(pick, "world_pos", None))
    picked_normal = _point_or_none(getattr(pick, "normal", None))

    if raw_valid and picked_vertices and _triangle_matches_points(snapshot, raw, picked_vertices, tolerance):
        return raw
    if raw_valid and world_pos is not None:
        raw_distance = _point_triangle_distance(world_pos, snapshot, raw)
        if raw_distance <= tolerance:
            return raw

    if picked_vertices:
        matches = [
            index
            for index in range(triangle_count)
            if _triangle_matches_points(snapshot, index, picked_vertices, tolerance)
        ]
        if matches:
            return min(
                matches,
                key=lambda index: _face_pick_score(snapshot, index, world_pos, picked_normal),
            )

    if world_pos is not None:
        candidate = min(
            range(triangle_count),
            key=lambda index: _face_pick_score(snapshot, index, world_pos, picked_normal),
            default=None,
        )
        if candidate is not None:
            distance = _point_triangle_distance(world_pos, snapshot, candidate)
            if distance <= max(tolerance * 8.0, snapshot.diagonal * 1.0e-5):
                return int(candidate)

    return raw if raw_valid else None


def _pick_points(values) -> tuple[Point3, ...]:
    try:
        return tuple((float(value[0]), float(value[1]), float(value[2])) for value in values)
    except Exception:
        return ()


def _point_or_none(value) -> Point3 | None:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return None


def _distance(a: Point3, b: Point3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _triangle_matches_points(
    snapshot: SurfaceMeshSnapshot,
    face_index: int,
    picked_vertices: tuple[Point3, ...],
    tolerance: float,
) -> bool:
    if len(picked_vertices) != 3:
        return False
    triangle_points = tuple(snapshot.vertices[index] for index in snapshot.triangles[int(face_index)])
    remaining = list(picked_vertices)
    for point in triangle_points:
        best = min(range(len(remaining)), key=lambda index: _distance(point, remaining[index]), default=None)
        if best is None or _distance(point, remaining[best]) > tolerance:
            return False
        remaining.pop(best)
    return True


def _face_pick_score(
    snapshot: SurfaceMeshSnapshot,
    face_index: int,
    world_pos: Point3 | None,
    picked_normal: Point3 | None,
) -> tuple[float, float]:
    distance = _point_triangle_distance(world_pos, snapshot, face_index) if world_pos is not None else 0.0
    normal_penalty = 0.0
    if picked_normal is not None:
        normal = snapshot.normals[int(face_index)]
        normal_length = math.sqrt(sum(value * value for value in normal))
        picked_length = math.sqrt(sum(value * value for value in picked_normal))
        if normal_length > 1.0e-12 and picked_length > 1.0e-12:
            cosine = abs(sum(normal[index] * picked_normal[index] for index in range(3)) / (normal_length * picked_length))
            normal_penalty = 1.0 - max(0.0, min(1.0, cosine))
    return (distance, normal_penalty)


def _point_triangle_distance(
    point: Point3 | None,
    snapshot: SurfaceMeshSnapshot,
    face_index: int,
) -> float:
    if point is None:
        return float("inf")
    a, b, c = (snapshot.vertices[index] for index in snapshot.triangles[int(face_index)])
    closest = _closest_point_on_triangle(point, a, b, c)
    return _distance(point, closest)


def _closest_point_on_triangle(point: Point3, a: Point3, b: Point3, c: Point3) -> Point3:
    # Real-Time Collision Detection, Christer Ericson, section 5.1.5.
    ab = tuple(b[index] - a[index] for index in range(3))
    ac = tuple(c[index] - a[index] for index in range(3))
    ap = tuple(point[index] - a[index] for index in range(3))
    d1 = sum(ab[index] * ap[index] for index in range(3))
    d2 = sum(ac[index] * ap[index] for index in range(3))
    if d1 <= 0.0 and d2 <= 0.0:
        return a

    bp = tuple(point[index] - b[index] for index in range(3))
    d3 = sum(ab[index] * bp[index] for index in range(3))
    d4 = sum(ac[index] * bp[index] for index in range(3))
    if d3 >= 0.0 and d4 <= d3:
        return b

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / max(1.0e-30, d1 - d3)
        return tuple(a[index] + v * ab[index] for index in range(3))  # type: ignore[return-value]

    cp = tuple(point[index] - c[index] for index in range(3))
    d5 = sum(ab[index] * cp[index] for index in range(3))
    d6 = sum(ac[index] * cp[index] for index in range(3))
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / max(1.0e-30, d2 - d6)
        return tuple(a[index] + w * ac[index] for index in range(3))  # type: ignore[return-value]

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        bc = tuple(c[index] - b[index] for index in range(3))
        w = (d4 - d3) / max(1.0e-30, (d4 - d3) + (d5 - d6))
        return tuple(b[index] + w * bc[index] for index in range(3))  # type: ignore[return-value]

    denominator = max(1.0e-30, va + vb + vc)
    v = vb / denominator
    w = vc / denominator
    return tuple(a[index] + ab[index] * v + ac[index] * w for index in range(3))  # type: ignore[return-value]


__all__ = [
    "EdgeKey",
    "Point3",
    "SurfaceAccessibilityField",
    "SurfaceMeshSnapshot",
    "SurfaceRegionMetrics",
    "SurfaceRegionResult",
    "SurfaceSelectionCache",
    "SurfaceSelectionDiagnosticSink",
    "SurfaceSelectionPointerAction",
    "SurfaceSelectionPointerMachine",
    "SurfaceSelectionPointerState",
    "SurfaceSelectionMeshPolicy",
    "SurfaceSelectionProfile",
    "SurfaceSelectionSession",
    "Triangle",
    "auto_surface_region",
    "face_index_from_pick",
    "select_surface_region",
    "surface_region_from_faces",
    "snapshot_from_pick",
]
