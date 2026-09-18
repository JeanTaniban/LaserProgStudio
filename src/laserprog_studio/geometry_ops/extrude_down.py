# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from ..mesh_ops import workmesh_to_polydata
from .mesh_metadata import copy_runtime_mesh_metadata
from .result import OperationResult


@dataclass(frozen=True)
class ExtrudeDownStats:
    supports: int = 0
    triangles_before: int = 0
    triangles_after: int = 0


def _triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def _workmesh_from_vertices(mesh: Any, vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]], *, suffix: str) -> Any:
    out = copy.deepcopy(mesh)
    out.vertices = vertices
    out.triangles = triangles
    try:
        if suffix and suffix.lower() not in str(out.name).lower():
            out.name = f"{out.name}{suffix}"
    except Exception:
        pass
    copy_runtime_mesh_metadata(mesh, out)
    return out


def _snap_value(value: float, snap: float) -> float:
    if snap <= 0:
        return float(value)
    return round(float(value) / snap) * snap


def _xy_key(point: tuple[float, float] | tuple[float, float, float], *, snap: float) -> tuple[int, int]:
    s = max(float(snap), 1e-9)
    return (int(round(float(point[0]) / s)), int(round(float(point[1]) / s)))


def _plane_segments(mesh: Any, z: float, *, eps: float = 1e-7) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=float)
    triangles = np.asarray(getattr(mesh, "triangles", []) or [], dtype=int)
    if vertices.ndim != 2 or vertices.shape[1] < 3 or triangles.ndim != 2 or triangles.shape[1] != 3:
        return []
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for tri in triangles:
        pts = vertices[tri, :3]
        dz = pts[:, 2] - float(z)
        if np.all(dz > eps) or np.all(dz < -eps):
            continue
        # Ignore triangles lying fully in the slice plane: they do not define a
        # stable contour. Adjacent non-coplanar triangles will provide the edge.
        if np.all(np.abs(dz) <= eps):
            continue
        inter: list[tuple[float, float]] = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            zi = float(dz[i])
            zj = float(dz[j])
            pi = pts[i]
            pj = pts[j]
            if abs(zi) <= eps and abs(zj) <= eps:
                continue
            if abs(zi) <= eps:
                inter.append((float(pi[0]), float(pi[1])))
            elif abs(zj) <= eps:
                inter.append((float(pj[0]), float(pj[1])))
            elif zi * zj < 0.0:
                t = (float(z) - float(pi[2])) / (float(pj[2]) - float(pi[2]))
                p = pi + t * (pj - pi)
                inter.append((float(p[0]), float(p[1])))
        # Deduplicate the two segment endpoints.
        uniq: list[tuple[float, float]] = []
        for p in inter:
            if not any((abs(p[0] - q[0]) <= eps and abs(p[1] - q[1]) <= eps) for q in uniq):
                uniq.append(p)
        if len(uniq) == 2:
            if abs(uniq[0][0] - uniq[1][0]) > eps or abs(uniq[0][1] - uniq[1][1]) > eps:
                segments.append((uniq[0], uniq[1]))
    return segments


def _contour_polygons(segments: list[tuple[tuple[float, float], tuple[float, float]]], *, snap: float):
    from shapely.geometry import LineString, MultiPolygon, Polygon
    from shapely.ops import polygonize, unary_union

    if not segments:
        return []

    def q(p: tuple[float, float]) -> tuple[float, float]:
        if snap <= 0:
            return (float(p[0]), float(p[1]))
        return (_snap_value(p[0], snap), _snap_value(p[1], snap))

    lines = [LineString([q(a), q(b)]) for a, b in segments]
    merged_lines = unary_union(lines)
    raw_polys = [p for p in polygonize(merged_lines) if getattr(p, "area", 0.0) > 0.0]
    if not raw_polys:
        return []

    # ``polygonize`` may return either:
    #   - one polygon whose interiors already describe holes, plus duplicate
    #     filled polygons for those holes; or
    #   - separate filled polygons for outer/inner rings.
    # Never unary-union those filled rings: it erases holes and creates the
    # hollow-envelope bug in Extrude Down.  Keep true shell polygons, attach
    # contained rings as holes, and drop duplicate hole polygons.
    ordered = sorted(raw_polys, key=lambda poly: float(poly.area), reverse=True)
    shells: list[dict[str, object]] = []

    def _point_in_existing_hole(point) -> bool:
        for shell in shells:
            holes = shell.get("holes", [])
            for coords in holes if isinstance(holes, list) else []:
                try:
                    if Polygon(coords).covers(point):
                        return True
                except Exception:
                    continue
        return False

    for poly in ordered:
        point = poly.representative_point()
        if _point_in_existing_hole(point):
            # Duplicate polygon emitted for an interior ring already represented
            # as a real hole by a larger polygon.
            continue
        parent_index: int | None = None
        parent_area = float("inf")
        for idx, shell in enumerate(shells):
            shell_poly = shell.get("poly")
            if shell_poly is None:
                continue
            try:
                if shell_poly.covers(point) and float(getattr(shell_poly, "area", 0.0)) < parent_area:
                    parent_index = idx
                    parent_area = float(getattr(shell_poly, "area", 0.0))
            except Exception:
                continue
        if parent_index is not None:
            holes = shells[parent_index].setdefault("holes", [])
            if isinstance(holes, list):
                holes.append(list(poly.exterior.coords))
            continue
        holes = [list(ring.coords) for ring in getattr(poly, "interiors", ())]
        shells.append({"poly": poly, "holes": holes})

    out = []
    for shell in shells:
        poly = shell.get("poly")
        if poly is None:
            continue
        holes = shell.get("holes", [])
        rebuilt = Polygon(poly.exterior.coords, holes=holes if isinstance(holes, list) else None)
        if not rebuilt.is_valid:
            rebuilt = rebuilt.buffer(0)
        if rebuilt.is_empty:
            continue
        if isinstance(rebuilt, Polygon):
            out.append(rebuilt)
        elif isinstance(rebuilt, MultiPolygon):
            out.extend(list(rebuilt.geoms))
    return out


def _ring_points(coords: Iterable[tuple[float, float]], *, eps: float = 1e-7) -> list[tuple[float, float]]:
    pts = [(float(x), float(y)) for x, y, *rest in coords]
    if len(pts) >= 2 and abs(pts[0][0] - pts[-1][0]) <= eps and abs(pts[0][1] - pts[-1][1]) <= eps:
        pts = pts[:-1]
    return pts





def _triangulate_polygon_constrained(poly):
    """Return triangles that exactly cover *poly*, including holes.

    ``shapely.ops.triangulate`` is an unconstrained Delaunay helper: on polygons
    with holes it may emit triangles crossing the hole and the old centroid
    filter could keep a visually hollow/incorrect cap.  Shapely 2.x exposes a
    constrained Delaunay triangulator; use it when available and keep a strict
    fallback for older environments.
    """

    try:
        from shapely import constrained_delaunay_triangles

        collection = constrained_delaunay_triangles(poly)
        geoms = tuple(getattr(collection, "geoms", ()) or ())
        out = [tri for tri in geoms if not tri.is_empty and getattr(tri, "area", 0.0) > 0.0 and poly.covers(tri)]
        if out:
            return out
    except Exception:
        pass

    try:
        from shapely.ops import triangulate

        out = []
        for tri in triangulate(poly):
            if tri.is_empty or getattr(tri, "area", 0.0) <= 0.0:
                continue
            # Strict geometry containment prevents caps from bridging holes.
            if poly.covers(tri):
                out.append(tri)
        return out
    except Exception:
        return []


def _add_cap_connected(
    poly,
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    *,
    z: float,
    snap: float,
    vertex_by_xy: dict[tuple[int, int], int],
    normal: str,
) -> None:
    """Triangulate a horizontal cap while preserving inner holes.

    ``normal`` is ``"up"`` or ``"down"``.  The helper reuses vertices by XY so
    caps weld to their side walls instead of leaving a separate shell.
    """

    def index(x: float, y: float) -> int:
        key = _xy_key((x, y), snap=snap)
        idx = vertex_by_xy.get(key)
        if idx is not None:
            return idx
        idx = len(vertices)
        vertices.append((float(x), float(y), float(z)))
        vertex_by_xy[key] = idx
        return idx

    want_down = str(normal).lower().strip() == "down"
    for tri in _triangulate_polygon_constrained(poly):
        coords = _ring_points(tri.exterior.coords)
        if len(coords) != 3:
            continue
        ids = [index(x, y) for x, y in coords]
        if len(set(ids)) != 3:
            continue
        if want_down:
            triangles.append((ids[0], ids[2], ids[1]))
        else:
            triangles.append((ids[0], ids[1], ids[2]))


def _polygons_from_horizontal_faces(mesh: Any, z: float, *, tolerance: float) -> list[Any]:
    """Rebuild filled XY polygons from triangles already lying on ``z``.

    This covers the common CAD case reported by users: a selected horizontal
    face/sheet with one or more holes must become a closed solid when extruded
    down.  Slice segments ignore coplanar triangles by design, so without this
    fallback the result can degenerate into side walls only.
    """

    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    verts = [(float(x), float(y), float(zz)) for x, y, zz in (getattr(mesh, "vertices", []) or [])]
    tris = [tuple(int(v) for v in tri[:3]) for tri in (getattr(mesh, "triangles", []) or [])]
    eps = max(float(tolerance), 1.0e-7)
    pieces = []
    for tri in tris:
        try:
            pts = [verts[int(i)] for i in tri]
        except Exception:
            continue
        if not all(abs(float(p[2]) - float(z)) <= eps for p in pts):
            continue
        coords = [(float(p[0]), float(p[1])) for p in pts]
        if len({(round(x, 8), round(y, 8)) for x, y in coords}) < 3:
            continue
        poly = Polygon(coords)
        if poly.is_valid and poly.area > eps * eps:
            pieces.append(poly)
    if not pieces:
        return []
    try:
        merged = unary_union(pieces)
        if merged.is_empty:
            return []
        if merged.geom_type == "Polygon":
            return [merged]
        if merged.geom_type == "MultiPolygon":
            return [p for p in merged.geoms if p.area > eps * eps]
    except Exception:
        return []
    return []


def _build_prism_from_polygons(
    mesh: Any,
    polygons: list[Any],
    *,
    top_z: float,
    ground_z: float,
    tolerance: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], int, str | None]:
    """Build a closed downward prism from filled polygons.

    The output contains top caps, bottom caps, outer walls and inner-hole walls.
    It is used when Extrude Down operates on a face/sheet or when a cut produces
    no usable upper mesh; in both cases returning only side walls is perceived as
    a hollow shell and is not a valid fabrication mesh.
    """

    eps = max(float(tolerance), 1e-7)
    snap = max(float(tolerance), 1e-6)
    if float(top_z) <= float(ground_z) + eps:
        return [], [], 0, "The plane is already at or below ground level: no extrusion needed."
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    top_vertex_by_xy: dict[tuple[int, int], int] = {}
    bottom_vertex_by_xy: dict[tuple[int, int], int] = {}
    count = 0
    for poly in polygons:
        if getattr(poly, "is_empty", False) or getattr(poly, "area", 0.0) <= eps * eps:
            continue
        exterior = _ring_points(poly.exterior.coords)
        _add_vertical_ring_connected(
            exterior,
            vertices,
            triangles,
            top_z=float(top_z),
            ground_z=float(ground_z),
            snap=snap,
            top_vertex_by_xy=top_vertex_by_xy,
            bottom_vertex_by_xy=bottom_vertex_by_xy,
            reverse=False,
        )
        for interior in poly.interiors:
            _add_vertical_ring_connected(
                _ring_points(interior.coords),
                vertices,
                triangles,
                top_z=float(top_z),
                ground_z=float(ground_z),
                snap=snap,
                top_vertex_by_xy=top_vertex_by_xy,
                bottom_vertex_by_xy=bottom_vertex_by_xy,
                reverse=True,
            )
        _add_cap_connected(poly, vertices, triangles, z=float(top_z), snap=snap, vertex_by_xy=top_vertex_by_xy, normal="up")
        _add_cap_connected(poly, vertices, triangles, z=float(ground_z), snap=snap, vertex_by_xy=bottom_vertex_by_xy, normal="down")
        count += 1
    if count <= 0 or not triangles:
        return [], [], 0, "Could not rebuild a closed extrusion volume."
    return vertices, triangles, count, None


def _clip_mesh_above_plane(
    mesh: Any,
    *,
    plane_z: float,
    tolerance: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], dict[tuple[int, int], int]]:
    """Return the part of *mesh* at/above *plane_z*.

    The old implementation appended a support prism to the untouched mesh. That
    left two independent shells touching at the cut plane, and any source
    geometry below the plane stayed inside the result. This clipper removes the
    lower half first and keeps/reuses the generated cut-boundary vertices so the
    downward extrusion can be welded to the remaining part.
    """

    src_vertices = [(float(x), float(y), float(z)) for x, y, z in (getattr(mesh, "vertices", []) or [])]
    src_triangles = [tuple(int(v) for v in tri[:3]) for tri in (getattr(mesh, "triangles", []) or [])]
    eps = max(float(tolerance), 1e-7)
    snap = max(float(tolerance), 1e-6)

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    vertex_by_key: dict[tuple[Any, ...], int] = {}
    plane_vertex_by_xy: dict[tuple[int, int], int] = {}

    def cleaned_point(point: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = float(point[0]), float(point[1]), float(point[2])
        if abs(z - float(plane_z)) <= eps:
            z = float(plane_z)
        return (x, y, z)

    def add_vertex(point: tuple[float, float, float], key: tuple[Any, ...]) -> int:
        point = cleaned_point(point)
        if abs(point[2] - float(plane_z)) <= eps:
            q = _xy_key(point, snap=snap)
            existing = plane_vertex_by_xy.get(q)
            if existing is not None:
                vertex_by_key[key] = existing
                return existing
        existing = vertex_by_key.get(key)
        if existing is not None:
            return existing
        idx = len(vertices)
        vertices.append(point)
        vertex_by_key[key] = idx
        if abs(point[2] - float(plane_z)) <= eps:
            plane_vertex_by_xy[_xy_key(point, snap=snap)] = idx
        return idx

    def original_item(idx: int) -> tuple[tuple[float, float, float], tuple[Any, ...]]:
        return cleaned_point(src_vertices[idx]), ("orig", int(idx))

    def intersection_item(a_idx: int, b_idx: int) -> tuple[tuple[float, float, float], tuple[Any, ...]]:
        a = src_vertices[int(a_idx)]
        b = src_vertices[int(b_idx)]
        za = float(a[2])
        zb = float(b[2])
        denom = zb - za
        if abs(denom) <= 1e-12:
            # Degenerate edge very close to the plane: use the midpoint and let
            # coordinate snapping merge it with neighbouring cut vertices.
            p = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, float(plane_z))
        else:
            t = (float(plane_z) - za) / denom
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), float(plane_z))
        lo, hi = sorted((int(a_idx), int(b_idx)))
        return cleaned_point(p), ("edge", lo, hi)

    def is_inside(idx: int) -> bool:
        return float(src_vertices[int(idx)][2]) >= float(plane_z) - eps

    for tri in src_triangles:
        ids = [int(tri[0]), int(tri[1]), int(tri[2])]
        if len({*ids}) < 3:
            continue
        if all(float(src_vertices[i][2]) < float(plane_z) - eps for i in ids):
            continue

        clipped: list[tuple[tuple[float, float, float], tuple[Any, ...]]] = []
        for pos, cur_idx in enumerate(ids):
            next_idx = ids[(pos + 1) % 3]
            cur_in = is_inside(cur_idx)
            next_in = is_inside(next_idx)

            if cur_in and next_in:
                clipped.append(original_item(next_idx))
            elif cur_in and not next_in:
                clipped.append(intersection_item(cur_idx, next_idx))
            elif not cur_in and next_in:
                clipped.append(intersection_item(cur_idx, next_idx))
                clipped.append(original_item(next_idx))
            # else: outside -> outside, add nothing.

        # Remove consecutive duplicates created by vertices exactly on the
        # plane.  Keep keys stable so neighbouring faces weld correctly.
        compact: list[tuple[tuple[float, float, float], tuple[Any, ...]]] = []
        for point, key in clipped:
            if compact:
                prev = compact[-1][0]
                if np.linalg.norm(np.asarray(prev) - np.asarray(point)) <= eps:
                    continue
            compact.append((point, key))
        if len(compact) > 1:
            first = compact[0][0]
            last = compact[-1][0]
            if np.linalg.norm(np.asarray(first) - np.asarray(last)) <= eps:
                compact.pop()
        if len(compact) < 3:
            continue

        poly_ids = [add_vertex(point, key) for point, key in compact]
        if len(set(poly_ids)) < 3:
            continue
        root = poly_ids[0]
        for i in range(1, len(poly_ids) - 1):
            a, b, c = root, poly_ids[i], poly_ids[i + 1]
            if len({a, b, c}) == 3:
                triangles.append((a, b, c))

    return vertices, triangles, plane_vertex_by_xy


def _add_vertical_ring_connected(
    ring: list[tuple[float, float]],
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    *,
    top_z: float,
    ground_z: float,
    snap: float,
    top_vertex_by_xy: dict[tuple[int, int], int],
    bottom_vertex_by_xy: dict[tuple[int, int], int],
    reverse: bool = False,
) -> None:
    if len(ring) < 3:
        return

    def top_index(x: float, y: float) -> int:
        key = _xy_key((x, y), snap=snap)
        idx = top_vertex_by_xy.get(key)
        if idx is not None:
            return idx
        idx = len(vertices)
        vertices.append((float(x), float(y), float(top_z)))
        top_vertex_by_xy[key] = idx
        return idx

    def bottom_index(x: float, y: float) -> int:
        key = _xy_key((x, y), snap=snap)
        idx = bottom_vertex_by_xy.get(key)
        if idx is not None:
            return idx
        idx = len(vertices)
        vertices.append((float(x), float(y), float(ground_z)))
        bottom_vertex_by_xy[key] = idx
        return idx

    top_idx = [top_index(x, y) for x, y in ring]
    bot_idx = [bottom_index(x, y) for x, y in ring]
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        if len({top_idx[i], bot_idx[i], bot_idx[j]}) == 3:
            if reverse:
                triangles.append((top_idx[i], bot_idx[j], bot_idx[i]))
            else:
                triangles.append((top_idx[i], bot_idx[i], bot_idx[j]))
        if len({top_idx[i], bot_idx[j], top_idx[j]}) == 3:
            if reverse:
                triangles.append((top_idx[i], top_idx[j], bot_idx[j]))
            else:
                triangles.append((top_idx[i], bot_idx[j], top_idx[j]))


def _add_bottom_cap_connected(
    poly,
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    *,
    ground_z: float,
    snap: float,
    bottom_vertex_by_xy: dict[tuple[int, int], int],
) -> None:
    _add_cap_connected(
        poly,
        vertices,
        triangles,
        z=float(ground_z),
        snap=float(snap),
        vertex_by_xy=bottom_vertex_by_xy,
        normal="down",
    )


def _clean_extrude_down_mesh_data(
    mesh: Any,
    plane_z: float,
    *,
    ground_z: float = 0.0,
    tolerance: float = 1e-5,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], int, str | None]:
    if float(plane_z) <= float(ground_z) + max(float(tolerance), 1e-7):
        return [], [], 0, "The plane is already at or below ground level: no extrusion needed."
    try:
        b = workmesh_to_polydata(mesh).triangulate().clean().bounds
        zmin, zmax = float(b[4]), float(b[5])
        if float(plane_z) < zmin - tolerance:
            return [], [], 0, "The plane is below the part: no usable section."
        if float(plane_z) > zmax + tolerance:
            return [], [], 0, "The plane is above the part: no usable section."
        if (float(plane_z) <= zmin + tolerance or float(plane_z) >= zmax - tolerance) and not _polygons_from_horizontal_faces(mesh, float(plane_z), tolerance=tolerance):
            return [], [], 0, "The plane is outside a usable filled face section."
    except Exception:
        pass

    eps = max(float(tolerance), 1e-7)
    snap = max(float(tolerance), 1e-6)
    segments = _plane_segments(mesh, float(plane_z), eps=eps)
    polygons = _contour_polygons(segments, snap=snap)
    polygons = [p for p in polygons if getattr(p, "area", 0.0) > tolerance * tolerance]

    # If the selected geometry is a horizontal face/sheet or the cut lies on a
    # face, the contour comes from coplanar triangles rather than edge-plane
    # intersections.  Use those filled triangles directly and create a complete
    # prism with top and bottom caps.
    coplanar_polygons = _polygons_from_horizontal_faces(mesh, float(plane_z), tolerance=tolerance)
    if not polygons and coplanar_polygons:
        return _build_prism_from_polygons(mesh, coplanar_polygons, top_z=float(plane_z), ground_z=float(ground_z), tolerance=tolerance)
    if not polygons:
        return [], [], 0, "Could not rebuild a closed contour at this height."

    vertices, triangles, top_vertex_by_xy = _clip_mesh_above_plane(mesh, plane_z=float(plane_z), tolerance=tolerance)
    if not vertices or not triangles:
        # A pure surface/face can have a valid cut polygon but no upper body to
        # keep.  Build the solid prism directly instead of returning an empty
        # shell or a warning.
        source_polygons = coplanar_polygons or polygons
        return _build_prism_from_polygons(mesh, source_polygons, top_z=float(plane_z), ground_z=float(ground_z), tolerance=tolerance)

    bottom_vertex_by_xy: dict[tuple[int, int], int] = {}
    count = 0
    for poly in polygons:
        exterior = _ring_points(poly.exterior.coords)
        _add_vertical_ring_connected(
            exterior,
            vertices,
            triangles,
            top_z=float(plane_z),
            ground_z=float(ground_z),
            snap=snap,
            top_vertex_by_xy=top_vertex_by_xy,
            bottom_vertex_by_xy=bottom_vertex_by_xy,
            reverse=False,
        )
        for interior in poly.interiors:
            _add_vertical_ring_connected(
                _ring_points(interior.coords),
                vertices,
                triangles,
                top_z=float(plane_z),
                ground_z=float(ground_z),
                snap=snap,
                top_vertex_by_xy=top_vertex_by_xy,
                bottom_vertex_by_xy=bottom_vertex_by_xy,
                reverse=True,
            )
        _add_bottom_cap_connected(
            poly,
            vertices,
            triangles,
            ground_z=float(ground_z),
            snap=snap,
            bottom_vertex_by_xy=bottom_vertex_by_xy,
        )
        count += 1
    return vertices, triangles, count, None


def extrude_mesh_down(mesh: Any, *, plane_z: float, ground_z: float = 0.0, tolerance: float = 1e-5) -> tuple[Any | None, ExtrudeDownStats, str | None]:
    before_vertices = [(float(x), float(y), float(z)) for x, y, z in (getattr(mesh, "vertices", []) or [])]
    before_triangles = [tuple(int(v) for v in tri[:3]) for tri in (getattr(mesh, "triangles", []) or [])]
    if not before_vertices or not before_triangles:
        return None, ExtrudeDownStats(), "Empty or invalid object."

    vertices, triangles, support_count, warning = _clean_extrude_down_mesh_data(mesh, plane_z, ground_z=ground_z, tolerance=tolerance)
    if warning:
        return copy.deepcopy(mesh), ExtrudeDownStats(0, len(before_triangles), len(before_triangles)), warning
    out = _workmesh_from_vertices(mesh, vertices, triangles, suffix=" extruded down")
    return out, ExtrudeDownStats(support_count, len(before_triangles), len(triangles)), None


def extrude_selected_meshes_down(
    meshes: list[Any],
    selected_indices: list[int],
    *,
    plane_z: float,
    ground_z: float = 0.0,
    tolerance: float = 1e-5,
) -> OperationResult:
    if not selected_indices:
        return OperationResult.failure("Select at least one part to extrude down.")
    out = [copy.deepcopy(m) for m in meshes]
    warnings: list[str] = []
    changed = 0
    supports = 0
    before_total = 0
    after_total = 0
    for raw_idx in selected_indices:
        idx = int(raw_idx)
        if not (0 <= idx < len(out)):
            continue
        new_mesh, stats, warning = extrude_mesh_down(out[idx], plane_z=plane_z, ground_z=ground_z, tolerance=tolerance)
        if new_mesh is None:
            return OperationResult.failure(warning or f"Part {idx}: extrusion failed.", warnings=warnings)
        if warning:
            warnings.append(f"{getattr(out[idx], 'name', 'Part')}: {warning}")
        out[idx] = new_mesh
        changed += 1
        supports += int(stats.supports)
        before_total += int(stats.triangles_before)
        after_total += int(stats.triangles_after)
    if changed <= 0:
        return OperationResult.failure("No valid selected part to extrude down.")
    warnings.append(f"Extrusions created: {supports}; selected triangles: {before_total} → {after_total}")
    return OperationResult.success(out, warnings=warnings)


__all__ = ["ExtrudeDownStats", "extrude_mesh_down", "extrude_selected_meshes_down"]
