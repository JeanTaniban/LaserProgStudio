# -*- coding: utf-8 -*-
"""Geometry-level topology contract for meshes consumed by 3D booleans.

An indexed triangle mesh can look watertight while still being invalid once
coincident XYZ vertices are welded by the boolean kernel.  Typical examples are
zero-length seam edges, duplicated coincident shells and bow-tie vertex contacts.
This module detects those defects without importing manifold3d, Qt or VTK.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any, Sequence

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class BooleanTopologyReport:
    vertices: int
    triangles: int
    indexed_boundary_edges: int
    indexed_nonmanifold_edges: int
    welded_vertices: int
    welded_boundary_edges: int
    welded_nonmanifold_edges: int
    welded_nonmanifold_vertices: int
    collapsed_triangles_after_weld: int
    duplicate_triangles_after_weld: int
    weld_tolerance: float

    @property
    def indexed_closed(self) -> bool:
        return bool(self.triangles > 0 and self.indexed_boundary_edges == 0 and self.indexed_nonmanifold_edges == 0)

    @property
    def geometrically_manifold(self) -> bool:
        return bool(
            self.indexed_closed
            and self.collapsed_triangles_after_weld == 0
            and self.duplicate_triangles_after_weld == 0
            and self.welded_boundary_edges == 0
            and self.welded_nonmanifold_edges == 0
            and self.welded_nonmanifold_vertices == 0
        )

    def as_dict(self) -> dict[str, int | float | bool]:
        return {
            "vertices": int(self.vertices),
            "triangles": int(self.triangles),
            "indexed_closed": bool(self.indexed_closed),
            "indexed_boundary_edges": int(self.indexed_boundary_edges),
            "indexed_nonmanifold_edges": int(self.indexed_nonmanifold_edges),
            "welded_vertices": int(self.welded_vertices),
            "welded_boundary_edges": int(self.welded_boundary_edges),
            "welded_nonmanifold_edges": int(self.welded_nonmanifold_edges),
            "welded_nonmanifold_vertices": int(self.welded_nonmanifold_vertices),
            "collapsed_triangles_after_weld": int(self.collapsed_triangles_after_weld),
            "duplicate_triangles_after_weld": int(self.duplicate_triangles_after_weld),
            "weld_tolerance": float(self.weld_tolerance),
            "geometrically_manifold": bool(self.geometrically_manifold),
        }


def _edge_counts(vertex_count: int, triangles: Sequence[Triangle]) -> tuple[int, int]:
    edges: Counter[tuple[int, int]] = Counter()
    for triangle in triangles:
        try:
            a, b, c = int(triangle[0]), int(triangle[1]), int(triangle[2])
        except Exception:
            return 1, 1
        if min(a, b, c) < 0 or max(a, b, c) >= int(vertex_count):
            return 1, 1
        for x, y in ((a, b), (b, c), (c, a)):
            if x == y:
                continue
            edges[(x, y) if x < y else (y, x)] += 1
    return (
        sum(1 for count in edges.values() if count == 1),
        sum(1 for count in edges.values() if count > 2),
    )


def _nonmanifold_vertex_count(vertex_count: int, triangles: Sequence[Triangle]) -> int:
    """Count vertices whose incident triangle link is not one connected cycle."""

    incident: list[list[tuple[int, int]]] = [[] for _ in range(max(int(vertex_count), 0))]
    for triangle in triangles:
        try:
            a, b, c = int(triangle[0]), int(triangle[1]), int(triangle[2])
        except Exception:
            return 1
        if min(a, b, c) < 0 or max(a, b, c) >= int(vertex_count):
            return 1
        incident[a].append((b, c))
        incident[b].append((c, a))
        incident[c].append((a, b))

    invalid = 0
    for links in incident:
        if not links:
            continue
        adjacency: dict[int, set[int]] = {}
        for left, right in links:
            if left == right:
                invalid += 1
                adjacency = {}
                break
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
        if not adjacency:
            continue
        if any(len(neighbours) != 2 for neighbours in adjacency.values()):
            invalid += 1
            continue
        start = next(iter(adjacency))
        stack = [start]
        visited: set[int] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacency[current] - visited)
        if len(visited) != len(adjacency):
            invalid += 1
    return int(invalid)


def mesh_extent(vertices: Sequence[Any]) -> float:
    try:
        xs = [float(point[0]) for point in vertices]
        ys = [float(point[1]) for point in vertices]
        zs = [float(point[2]) for point in vertices]
    except Exception:
        return 1.0
    if not xs:
        return 1.0
    value = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)
    return float(value) if math.isfinite(value) else 1.0


def default_boolean_weld_tolerance(vertices: Sequence[Any]) -> float:
    """Conservative tolerance for geometry-level seam validation.

    Keep this much tighter than user-facing repair tolerances.  The contract is
    intended to reveal coincident seams/zero-length cells, not erase legitimate
    thin manufacturing features.
    """

    extent = mesh_extent(vertices)
    return max(1.0e-9, min(1.0e-6, extent * 1.0e-10))


def analyze_boolean_topology(
    vertices: Sequence[Any],
    triangles: Sequence[Any],
    *,
    weld_tolerance: float | None = None,
) -> BooleanTopologyReport:
    points: list[Point3] = []
    for point in vertices or ():
        try:
            value = (float(point[0]), float(point[1]), float(point[2]))
        except Exception:
            value = (float("nan"), float("nan"), float("nan"))
        points.append(value)
    cells: list[Triangle] = []
    for triangle in triangles or ():
        try:
            cells.append((int(triangle[0]), int(triangle[1]), int(triangle[2])))
        except Exception:
            cells.append((-1, -1, -1))

    indexed_boundary, indexed_nonmanifold = _edge_counts(len(points), cells)
    tolerance = float(weld_tolerance) if weld_tolerance is not None else default_boolean_weld_tolerance(points)
    tolerance = max(abs(tolerance), 1.0e-12)

    key_to_index: dict[tuple[int, int, int], int] = {}
    remap: list[int] = []
    for point in points:
        if not all(math.isfinite(component) for component in point):
            # Keep invalid points distinct; indexed validation will fail elsewhere,
            # while this contract must remain deterministic and side-effect free.
            remap.append(len(key_to_index))
            key_to_index[(len(key_to_index), 0, 0)] = remap[-1]
            continue
        key = tuple(int(round(component / tolerance)) for component in point)
        existing = key_to_index.get(key)
        if existing is None:
            existing = len(key_to_index)
            key_to_index[key] = existing
        remap.append(existing)

    welded_cells: list[Triangle] = []
    collapsed = 0
    duplicates = 0
    seen: set[tuple[int, int, int]] = set()
    for a, b, c in cells:
        if min(a, b, c) < 0 or max(a, b, c) >= len(remap):
            collapsed += 1
            continue
        wa, wb, wc = remap[a], remap[b], remap[c]
        if len({wa, wb, wc}) != 3:
            collapsed += 1
            continue
        canonical = tuple(sorted((wa, wb, wc)))
        if canonical in seen:
            duplicates += 1
            continue
        seen.add(canonical)
        welded_cells.append((wa, wb, wc))

    welded_boundary, welded_nonmanifold = _edge_counts(len(key_to_index), welded_cells)
    welded_nonmanifold_vertices = _nonmanifold_vertex_count(len(key_to_index), welded_cells)
    return BooleanTopologyReport(
        vertices=len(points),
        triangles=len(cells),
        indexed_boundary_edges=int(indexed_boundary),
        indexed_nonmanifold_edges=int(indexed_nonmanifold),
        welded_vertices=len(key_to_index),
        welded_boundary_edges=int(welded_boundary),
        welded_nonmanifold_edges=int(welded_nonmanifold),
        welded_nonmanifold_vertices=int(welded_nonmanifold_vertices),
        collapsed_triangles_after_weld=int(collapsed),
        duplicate_triangles_after_weld=int(duplicates),
        weld_tolerance=float(tolerance),
    )


def analyze_work_mesh_boolean_topology(mesh: Any, *, weld_tolerance: float | None = None) -> BooleanTopologyReport:
    return analyze_boolean_topology(
        getattr(mesh, "vertices", ()) or (),
        getattr(mesh, "triangles", ()) or (),
        weld_tolerance=weld_tolerance,
    )


def require_geometric_boolean_manifold(
    mesh: Any,
    *,
    label: str = "mesh",
    weld_tolerance: float | None = None,
) -> BooleanTopologyReport:
    report = analyze_work_mesh_boolean_topology(mesh, weld_tolerance=weld_tolerance)
    if not report.geometrically_manifold:
        raise ValueError(
            f"{label} is closed by triangle indices but is not a valid geometric manifold "
            "after coincident-vertex welding "
            f"(indexed_boundary_edges={report.indexed_boundary_edges}, "
            f"indexed_nonmanifold_edges={report.indexed_nonmanifold_edges}, "
            f"welded_vertices={report.welded_vertices}/{report.vertices}, "
            f"collapsed_triangles={report.collapsed_triangles_after_weld}, "
            f"duplicate_triangles={report.duplicate_triangles_after_weld}, "
            f"welded_boundary_edges={report.welded_boundary_edges}, "
            f"welded_nonmanifold_edges={report.welded_nonmanifold_edges}, "
            f"welded_nonmanifold_vertices={report.welded_nonmanifold_vertices})."
        )
    return report


__all__ = [
    "BooleanTopologyReport",
    "analyze_boolean_topology",
    "analyze_work_mesh_boolean_topology",
    "default_boolean_weld_tolerance",
    "mesh_extent",
    "require_geometric_boolean_manifold",
]
