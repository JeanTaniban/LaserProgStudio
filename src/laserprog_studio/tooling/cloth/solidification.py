"""Closed thin-solid generation for editable Cloth outputs.

The interactive Cloth model remains a panel surface graph.  Manufacturing and
boolean operations, however, require a closed manifold volume.  This module is
kept independent from the renderer and the boolean controller so both paths can
reuse exactly the same conservative thickening contract.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any, Iterable

from laserprog_studio.domain.work_model import WorkMesh

Point3 = tuple[float, float, float]
_EPS = 1.0e-12
_DEFAULT_THICKNESS_MM = 0.2
_DEFAULT_STITCH_TOLERANCE_MM = 0.05


@dataclass(frozen=True, slots=True)
class ClothSolidificationReport:
    input_vertices: int
    input_triangles: int
    welded_vertices: int
    boundary_edges: int
    nonmanifold_edges: int
    thickness_mm: float
    stitch_tolerance_mm: float


def cloth_thickness_mm(source: Any, *, default: float = _DEFAULT_THICKNESS_MM) -> float:
    metadata = getattr(source, "metadata", source if isinstance(source, dict) else {}) or {}
    try:
        value = float(metadata.get("cloth_thickness_mm", default))
    except (TypeError, ValueError):
        value = float(default)
    return max(0.01, min(20.0, value))


def cloth_stitch_tolerance_mm(source: Any, *, default: float = _DEFAULT_STITCH_TOLERANCE_MM) -> float:
    metadata = getattr(source, "metadata", source if isinstance(source, dict) else {}) or {}
    try:
        value = float(metadata.get("cloth_stitch_tolerance_mm", default))
    except (TypeError, ValueError):
        value = float(default)
    return max(1.0e-6, min(5.0, value))


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Point3, b: Point3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Point3, factor: float) -> Point3:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Point3) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Point3) -> Point3 | None:
    length = _norm(a)
    if length <= _EPS:
        return None
    return _scale(a, 1.0 / length)


def _weld_surface(
    vertices: Iterable[Iterable[float]],
    triangles: Iterable[Iterable[int]],
    *,
    tolerance_mm: float,
) -> tuple[list[Point3], list[tuple[int, int, int]], int]:
    raw_vertices = [tuple(float(value) for value in point[:3]) for point in vertices]
    raw_triangles = [tuple(int(value) for value in triangle[:3]) for triangle in triangles]
    tolerance = max(1.0e-9, float(tolerance_mm))
    buckets: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    sums: list[list[float]] = []
    counts: list[int] = []
    old_to_new: list[int] = []

    # A quantised bucket plus a 3x3x3 neighbour lookup avoids the classic grid
    # boundary bug where two points closer than tolerance land in adjacent cells.
    for point in raw_vertices:
        key = tuple(int(math.floor(value / tolerance)) for value in point)
        found: int | None = None
        best = tolerance
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for candidate in buckets.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        current = tuple(sums[candidate][axis] / counts[candidate] for axis in range(3))
                        distance = math.dist(point, current)
                        if distance <= best:
                            found = candidate
                            best = distance
        if found is None:
            found = len(sums)
            sums.append([point[0], point[1], point[2]])
            counts.append(1)
            buckets[key].append(found)
        else:
            sums[found][0] += point[0]
            sums[found][1] += point[1]
            sums[found][2] += point[2]
            counts[found] += 1
        old_to_new.append(found)

    welded = [
        (values[0] / counts[index], values[1] / counts[index], values[2] / counts[index])
        for index, values in enumerate(sums)
    ]
    cleaned: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for triangle in raw_triangles:
        if any(index < 0 or index >= len(old_to_new) for index in triangle):
            continue
        mapped = tuple(old_to_new[index] for index in triangle)
        if len(set(mapped)) != 3:
            continue
        a, b, c = (welded[index] for index in mapped)
        if _norm(_cross(_sub(b, a), _sub(c, a))) <= _EPS:
            continue
        face_key = tuple(sorted(mapped))
        if face_key in seen:
            continue
        seen.add(face_key)
        cleaned.append(mapped)
    return welded, cleaned, len(raw_vertices) - len(welded)


def _clean_surface_without_cross_patch_weld(
    vertices: Iterable[Iterable[float]], triangles: Iterable[Iterable[int]]
) -> tuple[list[Point3], list[tuple[int, int, int]], int]:
    """Clean indices while preserving topology-authored coincident cuts."""

    values = [tuple(float(value) for value in point[:3]) for point in vertices]
    cleaned: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for raw in triangles:
        try:
            triangle = tuple(int(value) for value in raw[:3])
        except Exception:
            continue
        if len(set(triangle)) != 3 or any(index < 0 or index >= len(values) for index in triangle):
            continue
        a, b, c = (values[index] for index in triangle)
        if _norm(_cross(_sub(b, a), _sub(c, a))) <= _EPS:
            continue
        key = tuple(sorted(triangle))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(triangle)
    return values, cleaned, 0


def _orient_surface(
    vertices: list[Point3], triangles: list[tuple[int, int, int]]
) -> tuple[list[tuple[int, int, int]], list[list[int]]]:
    edge_map: dict[tuple[int, int], list[tuple[int, tuple[int, int]]]] = defaultdict(list)
    for triangle_index, (a, b, c) in enumerate(triangles):
        for edge in ((a, b), (b, c), (c, a)):
            edge_map[tuple(sorted(edge))].append((triangle_index, edge))

    flips = [False] * len(triangles)
    visited = [False] * len(triangles)
    components: list[list[int]] = []

    def directed_edges(triangle: tuple[int, int, int], flipped: bool):
        a, b, c = triangle
        return ((a, c), (c, b), (b, a)) if flipped else ((a, b), (b, c), (c, a))

    for start in range(len(triangles)):
        if visited[start]:
            continue
        queue: deque[int] = deque([start])
        visited[start] = True
        component: list[int] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for edge in directed_edges(triangles[current], flips[current]):
                for neighbour, neighbour_edge in edge_map.get(tuple(sorted(edge)), ()):
                    if neighbour == current:
                        continue
                    should_flip = neighbour_edge == edge
                    if not visited[neighbour]:
                        visited[neighbour] = True
                        flips[neighbour] = should_flip
                        queue.append(neighbour)
        components.append(component)

    oriented = list(triangles)
    for index, flip in enumerate(flips):
        if flip:
            a, b, c = oriented[index]
            oriented[index] = (a, c, b)
    return oriented, components


def _orient_closed_outward(vertices: list[Point3], triangles: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    oriented, components = _orient_surface(vertices, triangles)
    for component in components:
        volume = 0.0
        for index in component:
            a, b, c = (vertices[value] for value in oriented[index])
            volume += _dot(a, _cross(b, c)) / 6.0
        if volume < 0.0:
            for index in component:
                a, b, c = oriented[index]
                oriented[index] = (a, c, b)
    return oriented


def solidify_cloth_surface_mesh(
    mesh: Any,
    *,
    thickness_mm: float | None = None,
    stitch_tolerance_mm: float | None = None,
    name: str | None = None,
) -> tuple[WorkMesh, ClothSolidificationReport]:
    """Turn an open Cloth surface into one closed thin manifold shell.

    Vertices closer than the stitch tolerance are welded before thickening.  The
    weld is intentionally restricted to Cloth output preparation; it does not
    mutate the editable source document or unrelated scene meshes.
    """

    thickness = cloth_thickness_mm(mesh) if thickness_mm is None else max(0.01, min(20.0, float(thickness_mm)))
    stitch = cloth_stitch_tolerance_mm(mesh) if stitch_tolerance_mm is None else max(1.0e-6, min(5.0, float(stitch_tolerance_mm)))
    raw_vertices = list(getattr(mesh, "vertices", []) or [])
    raw_triangles = list(getattr(mesh, "triangles", []) or [])
    metadata = dict(getattr(mesh, "metadata", {}) or {})
    if bool(metadata.get("cloth_topology_welded", False)):
        # The mesh builder already welded only intentional Fold interfaces.
        # A spatial weld here would reconnect explicit Cut boundaries that happen
        # to overlap in the folded pose and recreate non-manifold edges.
        vertices, triangles, welded_count = _clean_surface_without_cross_patch_weld(raw_vertices, raw_triangles)
    else:
        vertices, triangles, welded_count = _weld_surface(raw_vertices, raw_triangles, tolerance_mm=stitch)
    if not vertices or not triangles:
        raise ValueError("Cloth solidification failed: the source surface is empty.")
    triangles, _components = _orient_surface(vertices, triangles)

    edge_faces: dict[tuple[int, int], list[tuple[int, tuple[int, int]]]] = defaultdict(list)
    for triangle_index, (a, b, c) in enumerate(triangles):
        for edge in ((a, b), (b, c), (c, a)):
            edge_faces[tuple(sorted(edge))].append((triangle_index, edge))
    nonmanifold = [edge for edge, entries in edge_faces.items() if len(entries) > 2]
    if nonmanifold:
        raise ValueError(
            "Cloth solidification failed: the panel surface contains "
            f"{len(nonmanifold)} non-manifold edge(s). Check overlapping panels or reduce Stitch tolerance."
        )
    boundary_entries = [entries[0][1] for entries in edge_faces.values() if len(entries) == 1]
    closed_mid_surface = not boundary_entries
    if closed_mid_surface:
        # A closed Cloth mid-surface is still zero thickness.  Orient it first,
        # then create an outer shell and a reversed inner shell.  Keeping the
        # inner shell negative is essential: orienting both shells outward would
        # turn the result into a filled block instead of a thin sheet.
        triangles = _orient_closed_outward(vertices, triangles)

    vertex_normals: list[Point3] = [(0.0, 0.0, 0.0) for _ in vertices]
    fallback_normal = (0.0, 0.0, 1.0)
    for a_index, b_index, c_index in triangles:
        a, b, c = vertices[a_index], vertices[b_index], vertices[c_index]
        normal = _cross(_sub(b, a), _sub(c, a))
        length = _norm(normal)
        if length <= _EPS:
            continue
        fallback_normal = _scale(normal, 1.0 / length)
        # Area weighting keeps the normal stable on dense arc triangulations.
        for index in (a_index, b_index, c_index):
            vertex_normals[index] = _add(vertex_normals[index], normal)
    normals = [_unit(value) or fallback_normal for value in vertex_normals]
    half = thickness * 0.5
    top = [_add(point, _scale(normals[index], half)) for index, point in enumerate(vertices)]
    bottom = [_add(point, _scale(normals[index], -half)) for index, point in enumerate(vertices)]
    count = len(vertices)
    output_vertices = top + bottom
    output_triangles: list[tuple[int, int, int]] = []
    output_triangles.extend(triangles)
    output_triangles.extend((a + count, c + count, b + count) for a, b, c in triangles)
    for a, b in boundary_entries:
        output_triangles.append((a, a + count, b + count))
        output_triangles.append((a, b + count, b))
    if not closed_mid_surface:
        output_triangles = _orient_closed_outward(output_vertices, output_triangles)

    # Contract check before handing the mesh to generic booleans.
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for a, b, c in output_triangles:
        counts[tuple(sorted((a, b)))] += 1
        counts[tuple(sorted((b, c)))] += 1
        counts[tuple(sorted((c, a)))] += 1
    bad_edges = [edge for edge, count_value in counts.items() if count_value != 2]
    if bad_edges:
        raise ValueError(
            "Cloth solidification failed to close the sheet "
            f"({len(bad_edges)} invalid edge(s) remain)."
        )

    result = WorkMesh(
        name=str(name or getattr(mesh, "name", "Cloth")),
        vertices=output_vertices,
        triangles=output_triangles,
        color=str(getattr(mesh, "color", "#BFD8E8") or "#BFD8E8"),
        material=deepcopy(getattr(mesh, "material", None)),
        engraving=deepcopy(getattr(mesh, "engraving", None)),
        metadata=deepcopy(getattr(mesh, "metadata", {}) or {}),
    )
    result.metadata.update(
        {
            "cloth_surface_only": False,
            "cloth_boolean_ready": True,
            "cloth_thickness_mm": thickness,
            "cloth_stitch_tolerance_mm": stitch,
            "cloth_mid_surface_vertices": len(vertices),
            "cloth_mid_surface_triangles": len(triangles),
            "cloth_closed_mid_surface": bool(closed_mid_surface),
        }
    )
    # The topology is already authored and validated.  Letting manifold3d
    # merge coincident XYZ vertices can reconnect unrelated cut boundaries.
    result._lps_skip_boolean_merge = True

    report = ClothSolidificationReport(
        input_vertices=len(raw_vertices),
        input_triangles=len(raw_triangles),
        welded_vertices=welded_count,
        boundary_edges=len(boundary_entries),
        nonmanifold_edges=0,
        thickness_mm=thickness,
        stitch_tolerance_mm=stitch,
    )
    return result, report


__all__ = [
    "ClothSolidificationReport",
    "cloth_stitch_tolerance_mm",
    "cloth_thickness_mm",
    "solidify_cloth_surface_mesh",
]
