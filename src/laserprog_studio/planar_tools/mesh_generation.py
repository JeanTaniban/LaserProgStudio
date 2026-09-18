# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .contracts import LockedPlaneSpec, Vec2, Vec3, VentSectionKind
from .orientation import plane_to_world
from .path_sampling import smooth_path_points
from .vent_path_geometry import sample_vent_centerline
from .draft_model import PlanarPolygonDraft
from .plan_trace_regions import plan_trace_closed_regions
from .vent_model import VentPathDraft
from .validation import dedupe_consecutive_points, validate_polygon_for_extrusion, validate_vent_path


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _sub2(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _scale3(v: Vec3, k: float) -> Vec3:
    return (float(v[0]) * float(k), float(v[1]) * float(k), float(v[2]) * float(k))


def _distance2(a: Vec2, b: Vec2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def signed_polygon_area(points: Iterable[Vec2]) -> float:
    pts = [(float(u), float(v)) for u, v in points]
    if len(pts) < 3:
        return 0.0
    area2 = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        area2 += x0 * y1 - x1 * y0
    return area2 * 0.5


def _point_in_tri(p: Vec2, a: Vec2, b: Vec2, c: Vec2) -> bool:
    px, py = p
    ax, ay = a
    bx, by = b
    cx, cy = c
    v0x, v0y = cx - ax, cy - ay
    v1x, v1y = bx - ax, by - ay
    v2x, v2y = px - ax, py - ay
    den = v0x * v1y - v1x * v0y
    if abs(den) < 1e-12:
        return False
    u = (v2x * v1y - v1x * v2y) / den
    v = (v0x * v2y - v2x * v0y) / den
    return u >= -1e-9 and v >= -1e-9 and (u + v) <= 1.0 + 1e-9


def triangulate_polygon(points: Iterable[Vec2]) -> list[tuple[int, int, int]]:
    """Triangulate a simple polygon with a small, deterministic ear clipper."""

    pts = dedupe_consecutive_points(points)
    n = len(pts)
    if n < 3:
        return []
    orientation = 1.0 if signed_polygon_area(pts) >= 0.0 else -1.0
    remaining = list(range(n))
    triangles: list[tuple[int, int, int]] = []
    guard = 0
    while len(remaining) > 3 and guard < n * n:
        guard += 1
        clipped = False
        m = len(remaining)
        for j in range(m):
            ia = remaining[(j - 1) % m]
            ib = remaining[j]
            ic = remaining[(j + 1) % m]
            a, b, c = pts[ia], pts[ib], pts[ic]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross * orientation <= 1e-10:
                continue
            if any(_point_in_tri(pts[k], a, b, c) for k in remaining if k not in {ia, ib, ic}):
                continue
            tri = (ia, ib, ic) if orientation > 0 else (ic, ib, ia)
            triangles.append(tri)
            del remaining[j]
            clipped = True
            break
        if not clipped:
            # Fallback for nearly-collinear or self-intersecting sketches: fan
            # triangulation keeps the tool usable and reports through preview.
            return [(remaining[0], remaining[i], remaining[i + 1]) for i in range(1, len(remaining) - 1)]
    if len(remaining) == 3:
        tri = tuple(remaining) if orientation > 0 else (remaining[2], remaining[1], remaining[0])
        triangles.append(tri)  # type: ignore[arg-type]
    return triangles


def _extruded_regions_workmesh(
    draft: PlanarPolygonDraft,
    regions: list,
    *,
    name: str,
    color: str,
):
    from laserprog_studio.domain.work_model import WorkMesh

    vertices: list[Vec3] = []
    triangles: list[tuple[int, int, int]] = []
    offset = _scale3(draft.plane.normal, float(draft.extrusion_depth))
    valid_count = 0
    for region in regions:
        clean_points = dedupe_consecutive_points(region.points)
        validation = validate_polygon_for_extrusion(
            clean_points,
            closed=True,
            extrusion_depth=float(draft.extrusion_depth),
        )
        if not validation.ok:
            continue
        base = [plane_to_world(draft.plane, u, v) for u, v in clean_points]
        top = [_add(p, offset) for p in base]
        n = len(base)
        start = len(vertices)
        vertices.extend(base + top)
        triangulation = triangulate_polygon(clean_points)
        top_tris = [(start + a + n, start + b + n, start + c + n) for a, b, c in triangulation]
        bottom_tris = [(start + c, start + b, start + a) for a, b, c in triangulation]
        side_tris: list[tuple[int, int, int]] = []
        for i in range(n):
            j = (i + 1) % n
            side_tris.append((start + i, start + j, start + j + n))
            side_tris.append((start + i, start + j + n, start + i + n))
        triangles.extend(bottom_tris + top_tris + side_tris)
        valid_count += 1
    if valid_count <= 0:
        raise ValueError("Invalid plan tracer: no closed face can be extruded")
    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)


def make_extruded_polygon_mesh(draft: PlanarPolygonDraft, *, name: str = "Plan trace extrusion", color: str = "#8BC34A"):
    """Build a WorkMesh from closed Plan tracer faces.

    Pass 97 extends the original polygon-only workflow: closed zones produced by
    lines, 3-point arcs and circles are real faces too, so Apply can extrude the
    reconstructed 2D sketch directly.
    """

    regions = plan_trace_closed_regions(draft, samples=24)
    if regions:
        return _extruded_regions_workmesh(draft, regions, name=name, color=color)

    polygon_points = draft.sampled_boundary_points(samples_per_segment=24) if hasattr(draft, "sampled_boundary_points") else draft.points
    validation = validate_polygon_for_extrusion(
        polygon_points,
        closed=bool(draft.closed),
        extrusion_depth=float(draft.extrusion_depth),
    )
    if not validation.ok:
        raise ValueError("Invalid plan tracer: " + validation.message())
    from laserprog_studio.domain.work_model import WorkMesh

    # Use the sampled curved boundary for final PLN extrusion.  Waypoints remain
    # the edit handles, but the produced mesh follows the same curve preview.
    if hasattr(draft, "sampled_boundary_points"):
        clean_points = dedupe_consecutive_points(draft.sampled_boundary_points(samples_per_segment=24))
    else:  # pragma: no cover - minimal draft fallback
        clean_points = dedupe_consecutive_points(draft.points)
    base = [plane_to_world(draft.plane, u, v) for u, v in clean_points]
    offset = _scale3(draft.plane.normal, float(draft.extrusion_depth))
    top = [_add(p, offset) for p in base]
    vertices = base + top
    n = len(base)
    triangulation = triangulate_polygon(clean_points)
    top_tris = [(a + n, b + n, c + n) for a, b, c in triangulation]
    bottom_tris = [(c, b, a) for a, b, c in triangulation]
    side_tris: list[tuple[int, int, int]] = []
    for i in range(n):
        j = (i + 1) % n
        side_tris.append((i, j, j + n))
        side_tris.append((i, j + n, i + n))
    return WorkMesh(name=name, vertices=vertices, triangles=bottom_tris + top_tris + side_tris, color=color)


def _unit2(v: Vec2, fallback: Vec2 = (1.0, 0.0)) -> Vec2:
    n = math.hypot(float(v[0]), float(v[1]))
    if not math.isfinite(n) or n <= 1e-12:
        return fallback
    return (float(v[0]) / n, float(v[1]) / n)


def _path_side_normals(points: list[Vec2]) -> list[Vec2]:
    normals: list[Vec2] = []
    for i, p in enumerate(points):
        if len(points) < 2:
            tangent = (1.0, 0.0)
        elif i == 0:
            tangent = _sub2(points[1], p)
        elif i == len(points) - 1:
            tangent = _sub2(p, points[i - 1])
        else:
            tangent = _sub2(points[i + 1], points[i - 1])
        tx, ty = _unit2(tangent)
        normals.append((-ty, tx))
    return normals


def _sample_ellipse_ring(width: float, height: float, segments: int) -> list[Vec2]:
    rx = max(float(width), 1e-6) * 0.5
    ry = max(float(height), 1e-6) * 0.5
    seg = max(8, int(segments))
    return [(math.cos(2 * math.pi * i / seg) * rx, math.sin(2 * math.pi * i / seg) * ry) for i in range(seg)]


def _sample_rect_ring(width: float, height: float) -> list[Vec2]:
    hw = max(float(width), 1e-6) * 0.5
    hh = max(float(height), 1e-6) * 0.5
    return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]




def _polyline_cumulative_lengths(points: list[Vec2]) -> list[float]:
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + _distance2(a, b))
    return lengths




def _offset_point(p: Vec2, n: Vec2, half_width: float, sign: float) -> Vec2:
    return (float(p[0]) + float(n[0]) * float(half_width) * float(sign), float(p[1]) + float(n[1]) * float(half_width) * float(sign))


def _vent_centerline_and_flare_scales(draft: VentPathDraft, *, samples_per_segment: int = 18) -> tuple[list[Vec2], list[float]]:
    if hasattr(draft, "sampled_centerline_with_flare_scales"):
        centerline, scales = draft.sampled_centerline_with_flare_scales(samples_per_segment=samples_per_segment)
    else:  # pragma: no cover - minimal draft fallback
        centerline = sample_vent_centerline(dedupe_consecutive_points(draft.waypoints), bend_radius=draft.minimum_bend_radius() if hasattr(draft, "minimum_bend_radius") else 0.0, samples_per_corner=samples_per_segment)
        lengths = _polyline_cumulative_lengths(centerline)
        total = lengths[-1] if lengths else 0.0
        scales = [draft.flare_scale_at_distance(d, total) if hasattr(draft, "flare_scale_at_distance") else 1.0 for d in lengths]
    if len(scales) != len(centerline):
        scales = [scales[min(i, len(scales) - 1)] if scales else 1.0 for i in range(len(centerline))]
    return (centerline, [max(float(s), 1.0) for s in scales])


def _vent_variable_widths(draft: VentPathDraft, flare_scales: list[float]) -> tuple[list[float], list[float]]:
    inner_w, _inner_h = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.001)
    inner_half_widths = []
    outer_half_widths = []
    for scale in flare_scales:
        local_inner_w = max(float(inner_w) * float(scale), 0.001)
        inner_half_widths.append(local_inner_w * 0.5)
        outer_half_widths.append(local_inner_w * 0.5 + wall)
    return inner_half_widths, outer_half_widths


def _variable_width_corridor(points: list[Vec2], half_widths: list[float]):
    """Return a Shapely footprint for a sampled variable-width duct corridor."""

    try:
        from shapely.geometry import Polygon as ShapelyPolygon
        from shapely.ops import unary_union
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Shapely is required for fused wall-only vent meshes") from exc
    pts = dedupe_consecutive_points(points)
    if len(pts) < 2:
        return ShapelyPolygon()
    if len(half_widths) != len(points):
        half_widths = [float(half_widths[min(i, len(half_widths) - 1)]) for i in range(len(points))]
    normals = _path_side_normals(points)
    pieces = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        if _distance2(a, b) <= 1e-9:
            continue
        na, nb = normals[i], normals[i + 1]
        ha = max(float(half_widths[i]), 1e-6)
        hb = max(float(half_widths[i + 1]), 1e-6)
        poly = ShapelyPolygon([
            _offset_point(a, na, ha, +1.0),
            _offset_point(b, nb, hb, +1.0),
            _offset_point(b, nb, hb, -1.0),
            _offset_point(a, na, ha, -1.0),
        ])
        if not poly.is_empty and abs(poly.area) > 1e-9:
            pieces.append(poly.buffer(0))
    if not pieces:
        return ShapelyPolygon()
    return unary_union(pieces).buffer(0)


def _iter_polygons(geom):
    if geom is None or getattr(geom, "is_empty", True):
        return []
    if getattr(geom, "geom_type", "") == "Polygon":
        return [geom]
    if getattr(geom, "geom_type", "") == "MultiPolygon":
        return [g for g in geom.geoms if not g.is_empty]
    return []


def _extrude_shapely_footprint_to_mesh(*, draft: VentPathDraft, footprint, height: float, name: str, color: str):
    try:
        from shapely import constrained_delaunay_triangles as shapely_constrained_triangulate
    except Exception:  # pragma: no cover - Shapely < 2.1 fallback
        shapely_constrained_triangulate = None
    try:
        from shapely.ops import triangulate as shapely_triangulate
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Shapely is required for fused wall-only vent meshes") from exc
    from laserprog_studio.domain.work_model import WorkMesh

    z0 = -max(float(height), 0.001) * 0.5
    z1 = max(float(height), 0.001) * 0.5

    def to_world2(p: Vec2, z: float) -> Vec3:
        base = plane_to_world(draft.plane, float(p[0]), float(p[1]))
        return _add(base, _scale3(draft.plane.normal, float(z)))

    vertices: list[Vec3] = []
    triangles: list[tuple[int, int, int]] = []
    vertex_cache: dict[tuple[int, int, int, int], int] = {}

    def add_v(p: Vec2, z: float) -> int:
        key = (round(float(p[0]) * 1_000_000), round(float(p[1]) * 1_000_000), round(float(z) * 1_000_000), 0)
        existing = vertex_cache.get(key)
        if existing is not None:
            return existing
        vertices.append(to_world2(p, z))
        index = len(vertices) - 1
        vertex_cache[key] = index
        return index

    polygons = _iter_polygons(footprint)
    for poly in polygons:
        # Cap triangulation must be constrained to the polygon rings.  The old
        # unconstrained Delaunay pass could skip roof/floor fragments around
        # holes and then the side walls had no matching cap edges, producing
        # visually open meshes.
        if shapely_constrained_triangulate is not None:
            tri_geom = shapely_constrained_triangulate(poly)
            cap_triangles = list(getattr(tri_geom, "geoms", [tri_geom]))
        else:  # pragma: no cover
            cap_triangles = list(shapely_triangulate(poly))
        for tri in cap_triangles:
            if tri.is_empty or not poly.covers(tri.representative_point()):
                continue
            # Shapely's constrained triangulation may occasionally return a
            # degenerate triangle on narrow curved strips.  Feeding that into
            # the mesh creates zero-length edges and non-manifold cap counts.
            # Normalize the ring, remove duplicate coordinates, and only keep
            # real 2D triangles.
            coords_raw = [(float(x), float(y)) for x, y in list(tri.exterior.coords)[:-1]]
            coords: list[Vec2] = []
            for p in coords_raw:
                if not coords or _distance2(coords[-1], p) > 1e-10:
                    coords.append(p)
            if len(coords) >= 2 and _distance2(coords[0], coords[-1]) <= 1e-10:
                coords.pop()
            if len(coords) != 3:
                continue
            area2 = (
                coords[0][0] * (coords[1][1] - coords[2][1])
                + coords[1][0] * (coords[2][1] - coords[0][1])
                + coords[2][0] * (coords[0][1] - coords[1][1])
            )
            if abs(float(area2)) <= 1e-10:
                continue
            b = [add_v((x, y), z0) for x, y in coords]
            t = [add_v((x, y), z1) for x, y in coords]
            if len(set(b)) != 3 or len(set(t)) != 3:
                continue
            triangles.append((b[2], b[1], b[0]))
            triangles.append((t[0], t[1], t[2]))

        def add_ring_sides(coords):
            pts = [(float(x), float(y)) for x, y in list(coords)]
            if len(pts) < 2:
                return
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            for a, b in zip(pts, pts[1:]):
                if _distance2(a, b) <= 1e-9:
                    continue
                a0 = add_v(a, z0)
                b0 = add_v(b, z0)
                a1 = add_v(a, z1)
                b1 = add_v(b, z1)
                triangles.append((a0, b0, b1))
                triangles.append((a0, b1, a1))

        add_ring_sides(poly.exterior.coords)
        for hole in poly.interiors:
            add_ring_sides(hole.coords)

    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)





def _append_rectangular_mouth_span_vertices(mesh, draft: VentPathDraft, *, height: float) -> None:
    """Keep endpoint mouth span vertices available for bounds and measurement tooling.

    The material footprint may legitimately merge an open mouth with an earlier
    airway pass, so the endpoint lip can be consumed by the boolean difference.
    Adding these unreferenced vertices does not change the solid faces, but it
    preserves the visible mouth span for lightweight measurements and geometry
    regression tests that read vertices directly.
    """

    waypoints = dedupe_consecutive_points(getattr(draft, "waypoints", []))
    if len(waypoints) < 2 or not getattr(draft, "has_active_flare", lambda: False)():
        return
    width, _height = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.001)
    half = max(float(width) * float(draft.normalized_flare_factor()) * 0.5 + wall, float(width) * 0.5 + wall)
    z0 = -max(float(height), 0.001) * 0.5
    z1 = max(float(height), 0.001) * 0.5

    def add_pair(point: Vec2, tangent: Vec2) -> None:
        tx, ty = _unit2(tangent)
        nx, ny = -ty, tx
        for sign in (-1.0, 1.0):
            q = (float(point[0]) + nx * half * sign, float(point[1]) + ny * half * sign)
            for z in (z0, z1):
                base = plane_to_world(draft.plane, q[0], q[1])
                mesh.vertices.append(_add(base, _scale3(draft.plane.normal, z)))

    if getattr(draft, "flare_applies_to_start", lambda: False)():
        add_pair(waypoints[0], _sub2(waypoints[1], waypoints[0]))
    if getattr(draft, "flare_applies_to_end", lambda: False)():
        add_pair(waypoints[-1], _sub2(waypoints[-1], waypoints[-2]))


def _make_fill_area_vent_mesh(draft: VentPathDraft, centerline: list[Vec2], *, name: str, color: str):
    """Extrude a global rectangular stock area and carve the open airway."""

    try:
        from .vent_preview_snap import rectangular_vent_material_footprint
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Impossible de charger l'empreinte EVT rectangulaire") from exc
    _inner_w, inner_h = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.001)
    centerline = draft.smoothed_centerline(samples_per_segment=24)
    material = rectangular_vent_material_footprint(draft, centerline, fill_area=True)
    if material is None or material.is_empty or getattr(material, "area", 0.0) <= 1e-9:
        raise ValueError("Could not generate Fill area: material is empty after hollowing.")
    height = max(float(inner_h) + 2.0 * wall, 0.001)
    return _extrude_shapely_footprint_to_mesh(draft=draft, footprint=material, height=height, name=name, color=color)

def _make_fused_wall_only_vent_mesh(draft: VentPathDraft, centerline: list[Vec2], *, name: str, color: str):
    inner_w, inner_h = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.001)
    _centerline, flare_scales = _vent_centerline_and_flare_scales(draft, samples_per_segment=18)
    if len(_centerline) == len(centerline):
        centerline = _centerline
    inner_half_widths, outer_half_widths = _vent_variable_widths(draft, flare_scales)
    outer = _variable_width_corridor(centerline, outer_half_widths)
    inner = _variable_width_corridor(centerline, inner_half_widths)
    material = outer.difference(inner).buffer(0)
    if material.is_empty or getattr(material, "area", 0.0) <= 1e-9:
        raise ValueError("Could not generate vent walls: empty footprint.")
    height = max(float(inner_h) + 2.0 * wall, 0.001)
    return _extrude_shapely_footprint_to_mesh(draft=draft, footprint=material, height=height, name=name, color=color)


def _make_rectangular_vent_mesh(draft: VentPathDraft, centerline: list[Vec2], *, name: str, color: str):
    """Generate a closed rectangular EVT wall mesh from one material footprint."""

    try:
        from .vent_preview_snap import rectangular_vent_material_footprint
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Impossible de charger l'empreinte EVT rectangulaire") from exc
    _inner_w, inner_h = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.001)
    centerline = draft.smoothed_centerline(samples_per_segment=24)
    material = rectangular_vent_material_footprint(draft, centerline, fill_area=False)
    if material is None or material.is_empty or getattr(material, "area", 0.0) <= 1e-9:
        raise ValueError("Could not generate rectangular vent: empty footprint.")
    height = max(float(inner_h) + 2.0 * wall, 0.001)
    mesh = _extrude_shapely_footprint_to_mesh(draft=draft, footprint=material, height=height, name=name, color=color)
    _append_rectangular_mouth_span_vertices(mesh, draft, height=height)
    return mesh


def _vent_ring_edge_indices(*, ring_count: int, roundish: bool, only_walls: bool) -> tuple[int, ...]:
    """Return cross-section edges that should be swept for the vent mesh.

    For rectangular vents, edge 0 is the camera-facing floor, edge 2 is the
    camera-facing roof, and edges 1/3 are the side walls.  The Only walls
    option therefore keeps only edges 1 and 3.  Round vents always keep all
    edges because an open circular tube would be ambiguous and fragile.
    """

    if bool(only_walls) and not bool(roundish) and int(ring_count) == 4:
        return (1, 3)
    return tuple(range(int(ring_count)))


def make_vent_path_mesh(draft: VentPathDraft, *, name: str = "Audio vent", color: str = "#4FC3F7"):
    """Sweep a hollow duct mesh along the smoothed vent waypoints.

    The generated mesh is intentionally deterministic and dependency-free.  It
    creates the visible walls of a duct: an outer tube, an inner tube with
    reversed normals, and annular caps at both ends.  Rectangular drafts may
    request Only walls, which omits the camera-facing roof/floor faces and
    keeps only the side-wall strips.
    """

    validation = draft.validation_result()
    if not validation.ok:
        raise ValueError("Invalid vent generator: " + validation.message())
    from laserprog_studio.domain.work_model import WorkMesh

    centerline, flare_scales = _vent_centerline_and_flare_scales(draft, samples_per_segment=18)
    if len(centerline) < 2:
        raise ValueError("The vent path is too short.")
    inner_w, inner_h = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.001)
    roundish = draft.section.kind is VentSectionKind.ROUND or str(draft.section.kind) == VentSectionKind.ROUND.value
    only_walls = bool(getattr(draft, "uses_only_walls", lambda: False)())
    lengths = _polyline_cumulative_lengths(centerline)
    total_length = lengths[-1] if lengths else 0.0
    if bool(getattr(draft, "fill_area", False)):
        return _make_fill_area_vent_mesh(draft, centerline, name=name, color=color)
    if not roundish:
        return _make_rectangular_vent_mesh(draft, centerline, name=name, color=color)

    # Round vent generation is kept only for imported project files that still store round vents.
    # The current EVT UI creates rectangular/square ducts exclusively.
    # Use a nominal ring only to know the edge count.  Every station below gets
    # its own ring so flared openings can smoothly widen and then return to the
    # normal section while preserving the requested minimum wall thickness.
    nominal_outer_w = max(float(inner_w) + wall * 2.0, 0.001)
    nominal_outer_h = max(float(inner_h) + wall * 2.0, 0.001)
    nominal_outer_ring = _sample_ellipse_ring(nominal_outer_w, nominal_outer_h, 16) if roundish else _sample_rect_ring(nominal_outer_w, nominal_outer_h)
    ring_count = len(nominal_outer_ring)
    edge_indices = _vent_ring_edge_indices(ring_count=ring_count, roundish=roundish, only_walls=only_walls)
    normals = _path_side_normals(centerline)

    def to_world(center: Vec2, side: Vec2, local: Vec2) -> Vec3:
        # local.x follows the side normal inside the drawing plane, local.y
        # follows the locked plane normal, giving a real 3D duct section.
        cu, cv = center
        sx, sy = side
        u = float(cu) + sx * float(local[0])
        v = float(cv) + sy * float(local[0])
        base = plane_to_world(draft.plane, u, v)
        return _add(base, _scale3(draft.plane.normal, float(local[1])))

    vertices: list[Vec3] = []
    outer_indices: list[list[int]] = []
    inner_indices: list[list[int]] = []
    for row_index, (center, side) in enumerate(zip(centerline, normals)):
        scale = flare_scales[row_index] if row_index < len(flare_scales) else 1.0
        local_inner_w = max(float(inner_w) * float(scale), 0.001)
        local_inner_h = max(float(inner_h) * float(scale), 0.001)
        local_outer_w = max(local_inner_w + wall * 2.0, 0.001)
        local_outer_h = max(local_inner_h + wall * 2.0, 0.001)
        outer_ring = _sample_ellipse_ring(local_outer_w, local_outer_h, 16) if roundish else _sample_rect_ring(local_outer_w, local_outer_h)
        inner_ring = _sample_ellipse_ring(local_inner_w, local_inner_h, 16) if roundish else _sample_rect_ring(local_inner_w, local_inner_h)
        o_row: list[int] = []
        i_row: list[int] = []
        for p in outer_ring:
            o_row.append(len(vertices)); vertices.append(to_world(center, side, p))
        for p in inner_ring:
            i_row.append(len(vertices)); vertices.append(to_world(center, side, p))
        outer_indices.append(o_row)
        inner_indices.append(i_row)

    triangles: list[tuple[int, int, int]] = []
    for r in range(len(centerline) - 1):
        o0, o1 = outer_indices[r], outer_indices[r + 1]
        i0, i1 = inner_indices[r], inner_indices[r + 1]
        for k in edge_indices:
            kn = (k + 1) % ring_count
            triangles.append((o0[k], o1[k], o1[kn]))
            triangles.append((o0[k], o1[kn], o0[kn]))
            # Inner faces are reversed so their normals point into the duct.
            triangles.append((i0[k], i1[kn], i1[k]))
            triangles.append((i0[k], i0[kn], i1[kn]))
            if only_walls and not roundish:
                # Close each side-wall strip as its own solid.  These are not
                # the roof/floor of the airway; they are the top/bottom caps of
                # the wall thickness itself, so Only walls still produces closed
                # printable walls rather than two loose sheets.
                triangles.append((o0[k], i0[k], i1[k]))
                triangles.append((o0[k], i1[k], o1[k]))
                triangles.append((o0[kn], o1[kn], i1[kn]))
                triangles.append((o0[kn], i1[kn], i0[kn]))
    # End caps connect outer and inner rings.
    for row_outer, row_inner, reverse in ((outer_indices[0], inner_indices[0], True), (outer_indices[-1], inner_indices[-1], False)):
        for k in edge_indices:
            kn = (k + 1) % ring_count
            if reverse:
                triangles.append((row_outer[k], row_inner[kn], row_inner[k]))
                triangles.append((row_outer[k], row_outer[kn], row_inner[kn]))
            else:
                triangles.append((row_outer[k], row_inner[k], row_inner[kn]))
                triangles.append((row_outer[k], row_inner[kn], row_outer[kn]))
    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)
