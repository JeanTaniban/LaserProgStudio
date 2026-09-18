# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable

from .contracts import Vec2
from .validation import distance2d

if TYPE_CHECKING:  # pragma: no cover
    from .vent_model import VentPathDraft


def preview_half_widths(draft: "VentPathDraft", *, include_inner: bool = False) -> list[float]:
    """Return the half widths used by the EVT preview.

    EVT is now an intentionally rectangular-only user workflow.  The public
    model can still load old round-vent files/tests, but the editor itself
    previews a rectangular airway: inner width plus wall thickness for the outer
    footprint, and optionally the inner airway width for snapping.
    """

    width, _height = draft.section_dimensions()
    wall = max(float(draft.wall_thickness), 0.0)
    halves = [float(width) * 0.5 + wall]
    if include_inner:
        halves.append(float(width) * 0.5)
    return halves


def _unit(v: Vec2, fallback: Vec2 = (1.0, 0.0)) -> Vec2:
    length = math.hypot(float(v[0]), float(v[1]))
    if not math.isfinite(length) or length <= 1e-9:
        return fallback
    return (float(v[0]) / length, float(v[1]) / length)


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _add(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]))


def clean_polyline(points: Iterable[Vec2], *, tolerance: float = 1e-8) -> list[Vec2]:
    out: list[Vec2] = []
    for raw in points:
        p = (float(raw[0]), float(raw[1]))
        if not out or distance2d(out[-1], p) > float(tolerance):
            out.append(p)
    return out


def _local_tangent(points: list[Vec2], index: int) -> Vec2:
    count = len(points)
    if count < 2:
        return (1.0, 0.0)
    if index <= 0:
        return _unit(_sub(points[1], points[0]))
    if index >= count - 1:
        return _unit(_sub(points[-1], points[-2]))
    before = _unit(_sub(points[index], points[index - 1]))
    after = _unit(_sub(points[index + 1], points[index]))
    blended = _add(before, after)
    if math.hypot(blended[0], blended[1]) <= 1e-7:
        return after
    return _unit(blended)


def offset_path(centerline: list[Vec2], half_width: float, *, miter_limit: float = 3.0) -> list[Vec2]:
    """Normal-offset helper used when Shapely is unavailable.

    The live EVT preview no longer relies on this function for its outside
    contours because independent left/right offsets are visually fragile around
    tight bends.  The drawing code now uses Shapely corridor footprints through
    :func:`corridor_outline_paths`.  Keeping this deterministic helper avoids
    breaking older tests/extensions that import ``offset_paths`` directly.
    """

    pts = clean_polyline(centerline)
    if len(pts) < 2:
        return []
    half = float(half_width)
    out: list[Vec2] = []
    for i, p in enumerate(pts):
        tx, ty = _local_tangent(pts, i)
        nx, ny = -ty, tx
        q = (float(p[0]) + nx * half, float(p[1]) + ny * half)
        if not out or distance2d(out[-1], q) > 1e-8:
            out.append(q)
    return out


def offset_paths(centerline: list[Vec2], half_width: float) -> tuple[list[Vec2], list[Vec2]]:
    return offset_path(centerline, float(half_width)), offset_path(centerline, -float(half_width))


def _line_buffer(centerline: Iterable[Vec2], half_width: float, *, join_style: int = 1, cap_style: int = 2):
    """Build a robust 2D corridor for a sampled centerline.

    ``cap_style=2`` gives flat inlet/outlet cuts exactly at the first and last
    waypoint, which is the most predictable behaviour for an event that is meant
    to connect to a face.  ``join_style=1`` rounds residual polyline corners and
    prevents the huge miter spikes that made previous exterior guides unusable.
    """

    pts = clean_polyline(centerline)
    if len(pts) < 2 or float(half_width) <= 1e-9:
        return None
    try:
        from shapely.geometry import LineString
    except Exception:  # pragma: no cover - runtime fallback below
        return None
    try:
        geom = LineString(pts).buffer(float(half_width), cap_style=cap_style, join_style=join_style, resolution=10)
        return geom.buffer(0)
    except Exception:
        return None




def _variable_line_buffer(centerline: Iterable[Vec2], half_widths: Iterable[float]):
    """Build a robust 2D corridor for a sampled centerline with local widths.

    This is used by the preview/snap path so embouchures shown in the editor
    match the variable-width footprint used by Apply.
    """

    pts = clean_polyline(centerline)
    widths = [max(float(w), 1e-9) for w in half_widths]
    if len(pts) < 2:
        return None
    if len(widths) != len(pts):
        widths = [widths[min(i, len(widths) - 1)] if widths else 1e-9 for i in range(len(pts))]
    try:
        from shapely.geometry import Polygon as ShapelyPolygon
        from shapely.ops import unary_union
    except Exception:  # pragma: no cover - runtime fallback below
        return None
    try:
        normals = []
        for i, p in enumerate(pts):
            tx, ty = _local_tangent(pts, i)
            normals.append((-ty, tx))
        pieces = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if distance2d(a, b) <= 1e-9:
                continue
            na, nb = normals[i], normals[i + 1]
            ha, hb = widths[i], widths[i + 1]
            poly = ShapelyPolygon([
                (a[0] + na[0] * ha, a[1] + na[1] * ha),
                (b[0] + nb[0] * hb, b[1] + nb[1] * hb),
                (b[0] - nb[0] * hb, b[1] - nb[1] * hb),
                (a[0] - na[0] * ha, a[1] - na[1] * ha),
            ])
            if not poly.is_empty and abs(float(poly.area)) > 1e-9:
                pieces.append(poly.buffer(0))
        if not pieces:
            return None
        return unary_union(pieces).buffer(0)
    except Exception:
        return None


def _iter_polygon_rings(geom) -> list[list[Vec2]]:
    if geom is None or getattr(geom, "is_empty", True):
        return []
    polygons = []
    gtype = getattr(geom, "geom_type", "")
    if gtype == "Polygon":
        polygons = [geom]
    elif gtype == "MultiPolygon":
        polygons = sorted([g for g in geom.geoms if not g.is_empty], key=lambda g: float(getattr(g, "area", 0.0)), reverse=True)
    rings: list[list[Vec2]] = []
    for poly in polygons:
        coords = list(poly.exterior.coords)
        if len(coords) >= 4:
            ring = [(float(x), float(y)) for x, y in coords[:-1]]
            if ring:
                rings.append(ring)
        for interior in getattr(poly, "interiors", []):
            coords = list(interior.coords)
            if len(coords) >= 4:
                ring = [(float(x), float(y)) for x, y in coords[:-1]]
                if ring:
                    rings.append(ring)
    return rings


def corridor_outline_paths(centerline: Iterable[Vec2], half_width: float) -> list[list[Vec2]]:
    """Return clean outline rings for the visual corridor footprint.

    Unlike separate left/right guide lines, these rings represent the actual 2D
    area occupied by the vent.  Overlaps, U-turns and tight curves are unioned
    before display, so the contour never draws impossible spirals or tangled
    miters while the user edits curve radius/force.
    """

    pts = clean_polyline(centerline)
    if len(pts) < 2:
        return []
    geom = _line_buffer(pts, half_width)
    rings = _iter_polygon_rings(geom)
    if rings:
        return rings
    # Fallback without Shapely: one closed outline from offset guide paths.
    left, right = offset_paths(pts, half_width)
    outline = left + list(reversed(right))
    return [outline] if len(outline) >= 3 else []




def variable_corridor_outline_paths(centerline: Iterable[Vec2], half_widths: Iterable[float]) -> list[list[Vec2]]:
    pts = clean_polyline(centerline)
    widths = [max(float(w), 1e-9) for w in half_widths]
    if len(pts) < 2:
        return []
    geom = _variable_line_buffer(pts, widths)
    rings = _iter_polygon_rings(geom)
    if rings:
        return rings
    fallback_width = max(widths) if widths else 0.0
    return corridor_outline_paths(pts, fallback_width)


def variable_corridor_bounds(centerline: Iterable[Vec2], half_widths: Iterable[float]) -> tuple[float, float, float, float] | None:
    pts = clean_polyline(centerline)
    widths = [max(float(w), 1e-9) for w in half_widths]
    if len(pts) < 2:
        return None
    geom = _variable_line_buffer(pts, widths)
    if geom is not None and not getattr(geom, "is_empty", True):
        minx, miny, maxx, maxy = geom.bounds
        return (float(minx), float(miny), float(maxx), float(maxy))
    rings = variable_corridor_outline_paths(pts, widths)
    flat = [p for ring in rings for p in ring]
    if not flat:
        return None
    return (min(x for x, _ in flat), min(y for _, y in flat), max(x for x, _ in flat), max(y for _, y in flat))


def corridor_bounds(centerline: Iterable[Vec2], half_width: float) -> tuple[float, float, float, float] | None:
    pts = clean_polyline(centerline)
    if len(pts) < 2:
        return None
    geom = _line_buffer(pts, half_width)
    if geom is not None and not getattr(geom, "is_empty", True):
        minx, miny, maxx, maxy = geom.bounds
        return (float(minx), float(miny), float(maxx), float(maxy))
    rings = corridor_outline_paths(pts, half_width)
    flat = [p for ring in rings for p in ring]
    if not flat:
        return None
    return (min(x for x, _ in flat), min(y for _, y in flat), max(x for x, _ in flat), max(y for _, y in flat))




def _endpoint_tangent_from_waypoints(points: list[Vec2], *, at_start: bool) -> Vec2:
    """Stable tangent used by local rectangular mouth pads."""

    pts = clean_polyline(points)
    if len(pts) < 2:
        return (1.0, 0.0)
    if bool(at_start):
        return _unit(_sub(pts[1], pts[0]))
    return _unit(_sub(pts[-1], pts[-2]))


def _endpoint_flare_depth(draft: "VentPathDraft", *, at_start: bool) -> float:
    """Return the local rounded-mouth transition length.

    The previous embouchure was a shallow rectangular pad.  It widened the
    opening abruptly, which looked like a step and is a poor acoustic shape.
    Keep the flare endpoint-local, but make the transition long enough to draw
    a real smooth radius/taper before the duct returns to its nominal section.
    """

    waypoints = clean_polyline(getattr(draft, "waypoints", []))
    if len(waypoints) < 2:
        return 0.0
    width, _height = draft.section_dimensions()
    wall = max(float(getattr(draft, "wall_thickness", 0.0)), 0.0)
    try:
        factor = max(float(draft.normalized_flare_factor()), 1.0)
    except Exception:
        factor = 1.0
    seg_len = distance2d(waypoints[0], waypoints[1]) if bool(at_start) else distance2d(waypoints[-2], waypoints[-1])
    if seg_len <= 1e-9 or factor <= 1.000001:
        return 0.0
    inner_half = max(float(width) * 0.5, 1e-9)
    flared_half = inner_half * factor
    flare_delta = max(flared_half - inner_half, 0.0)
    desired = max(wall * 3.0, float(width) * 0.45, flare_delta * 1.35, 1.0)
    # The mouth is deliberately endpoint-local.  It never consumes a whole user
    # segment, so it cannot appear to move from one waypoint to the next.
    return max(0.0, min(float(desired), float(seg_len) * 0.35))


def _cosine_ease_out_to_nominal(t: float) -> float:
    """1 at the mouth, 0 at the nominal duct, with zero slope at both ends."""

    u = min(max(float(t), 0.0), 1.0)
    return 0.5 * (1.0 + math.cos(math.pi * u))


def _endpoint_flare_polygon(
    point: Vec2,
    tangent: Vec2,
    nominal_half_width: float,
    flared_half_width: float,
    depth: float,
    *,
    at_start: bool,
    samples: int = 14,
):
    """Return a rounded local mouth polygon instead of a rectangular step."""

    try:
        from shapely.geometry import Polygon as ShapelyPolygon
    except Exception:  # pragma: no cover
        return None
    nominal = max(float(nominal_half_width), 0.0)
    flared = max(float(flared_half_width), nominal)
    d = max(float(depth), 0.0)
    if flared <= 1e-9 or d <= 1e-9:
        return None
    tx, ty = _unit(tangent)
    nx, ny = -ty, tx
    p = (float(point[0]), float(point[1]))
    steps = max(4, int(samples))
    left: list[Vec2] = []
    right: list[Vec2] = []
    for i in range(steps + 1):
        t = i / steps
        dist = d * t
        half = nominal + (flared - nominal) * _cosine_ease_out_to_nominal(t)
        if bool(at_start):
            c = (p[0] + tx * dist, p[1] + ty * dist)
        else:
            c = (p[0] - tx * (d - dist), p[1] - ty * (d - dist))
        left.append((c[0] + nx * half, c[1] + ny * half))
        right.append((c[0] - nx * half, c[1] - ny * half))
    coords = left + list(reversed(right))
    poly = ShapelyPolygon(coords)
    try:
        return poly.buffer(0)
    except Exception:
        return poly


def _union_geometries(items):
    try:
        from shapely.geometry import Polygon as ShapelyPolygon
        from shapely.ops import unary_union
    except Exception:  # pragma: no cover
        return None
    valid = [g for g in items if g is not None and not getattr(g, "is_empty", True)]
    if not valid:
        return ShapelyPolygon()
    try:
        return unary_union(valid).buffer(0)
    except Exception:
        return unary_union(valid)




def _bounds_diagonal(bounds: tuple[float, float, float, float] | None) -> float:
    if bounds is None:
        return 0.0
    minx, miny, maxx, maxy = bounds
    return math.hypot(float(maxx) - float(minx), float(maxy) - float(miny))


def _extended_centerline_for_open_airway(points: list[Vec2], extension: float) -> list[Vec2]:
    pts = clean_polyline(points)
    if len(pts) < 2:
        return pts
    ext = max(float(extension), 0.0)
    if ext <= 1e-9:
        return pts
    start_t = _unit(_sub(pts[1], pts[0]))
    end_t = _unit(_sub(pts[-1], pts[-2]))
    start = (float(pts[0][0]) - start_t[0] * ext, float(pts[0][1]) - start_t[1] * ext)
    end = (float(pts[-1][0]) + end_t[0] * ext, float(pts[-1][1]) + end_t[1] * ext)
    return [start] + pts + [end]


def _endpoint_opening_flare_polygon(
    point: Vec2,
    tangent: Vec2,
    nominal_half_width: float,
    flared_half_width: float,
    inward_depth: float,
    outward_depth: float,
    *,
    at_start: bool,
    samples: int = 14,
):
    """Cut the rounded flared airway through the mouth and outward opening."""

    try:
        from shapely.geometry import Polygon as ShapelyPolygon
    except Exception:  # pragma: no cover
        return None
    nominal = max(float(nominal_half_width), 0.0)
    flared = max(float(flared_half_width), nominal)
    in_d = max(float(inward_depth), 0.0)
    out_d = max(float(outward_depth), 0.0)
    if flared <= 1e-9 or (in_d + out_d) <= 1e-9:
        return None
    tx, ty = _unit(tangent)
    nx, ny = -ty, tx
    p = (float(point[0]), float(point[1]))
    steps = max(4, int(samples))
    left: list[Vec2] = []
    right: list[Vec2] = []
    if bool(at_start):
        # Outside the panel the opening stays fully flared; inside, it returns
        # smoothly to the nominal duct section.
        stations = [(-out_d, flared)]
        for i in range(0, steps + 1):
            t = i / steps
            stations.append((in_d * t, nominal + (flared - nominal) * _cosine_ease_out_to_nominal(t)))
    else:
        stations = []
        for i in range(0, steps + 1):
            t = i / steps
            stations.append((-in_d * (1.0 - t), nominal + (flared - nominal) * _cosine_ease_out_to_nominal(1.0 - t)))
        stations.append((out_d, flared))
    for dist, half in stations:
        c = (p[0] + tx * float(dist), p[1] + ty * float(dist))
        left.append((c[0] + nx * half, c[1] + ny * half))
        right.append((c[0] - nx * half, c[1] - ny * half))
    poly = ShapelyPolygon(left + list(reversed(right)))
    try:
        return poly.buffer(0)
    except Exception:
        return poly


def rectangular_vent_airway_cut_geometry(
    draft: "VentPathDraft",
    centerline: Iterable[Vec2] | None = None,
    *,
    outer_reference=None,
):
    """Return the real cutting footprint for the rectangular EVT airway.

    The visible inner guide is endpoint-local, but the generated material must
    be open at the inlet and outlet.  This cutter therefore extends past the
    first and last waypoint before boolean subtraction.  Without that extension
    Shapely can leave a thin cap at ends or at the Fill-area bounding box, which
    visually blocks sections of the duct.
    """

    pts = clean_polyline(centerline if centerline is not None else draft.smoothed_centerline(samples_per_segment=24))
    if len(pts) < 2:
        return None
    width, _height = draft.section_dimensions()
    wall = max(float(getattr(draft, "wall_thickness", 0.0)), 0.0)
    factor = max(float(draft.normalized_flare_factor()), 1.0) if hasattr(draft, "normalized_flare_factor") else 1.0
    inner_half = max(float(width) * 0.5, 1e-9)
    outer_half = inner_half + wall
    if outer_reference is not None and not getattr(outer_reference, "is_empty", True):
        try:
            ref_bounds = tuple(float(v) for v in outer_reference.bounds)
        except Exception:
            ref_bounds = None
    else:
        ref_bounds = None
    path_diag = _bounds_diagonal(ref_bounds)
    # Long enough to pass through a Fill-area stock rectangle even when the
    # endpoint sits inside the global bounds because of curves or mouth pads.
    extension = max(path_diag * 1.5, outer_half * 8.0, float(width) * max(factor, 1.0) * 4.0, wall * 12.0, 10.0)
    parts = [_line_buffer(_extended_centerline_for_open_airway(pts, extension), inner_half, join_style=1, cap_style=2)]

    waypoints = clean_polyline(getattr(draft, "waypoints", []))
    if len(waypoints) >= 2:
        flared_inner_half = max(float(width) * factor * 0.5, inner_half)
        start_tangent = _endpoint_tangent_from_waypoints(waypoints, at_start=True)
        end_tangent = _endpoint_tangent_from_waypoints(waypoints, at_start=False)
        start_depth = _endpoint_flare_depth(draft, at_start=True) if factor > 1.000001 and getattr(draft, "flare_applies_to_start", lambda: False)() else max(wall, 0.0)
        end_depth = _endpoint_flare_depth(draft, at_start=False) if factor > 1.000001 and getattr(draft, "flare_applies_to_end", lambda: False)() else max(wall, 0.0)
        start_half = flared_inner_half if factor > 1.000001 and getattr(draft, "flare_applies_to_start", lambda: False)() else inner_half
        end_half = flared_inner_half if factor > 1.000001 and getattr(draft, "flare_applies_to_end", lambda: False)() else inner_half
        parts.append(_endpoint_opening_flare_polygon(waypoints[0], start_tangent, inner_half, start_half, start_depth, extension, at_start=True))
        parts.append(_endpoint_opening_flare_polygon(waypoints[-1], end_tangent, inner_half, end_half, end_depth, extension, at_start=False))
    return _union_geometries(parts)


def rectangular_vent_material_footprint(draft: "VentPathDraft", centerline: Iterable[Vec2] | None = None, *, fill_area: bool | None = None):
    """Return the exact 2D material footprint used by Apply.

    ``fill_area=False`` returns only the duct walls. ``fill_area=True`` returns
    the global rectangular stock area with the airway cut open through the
    inlet and outlet.  The function is shared by preview, snapping and mesh
    generation so mode plein and non plein cannot diverge.
    """

    try:
        from shapely.geometry import box as shapely_box
    except Exception:  # pragma: no cover
        return None
    pts = clean_polyline(centerline if centerline is not None else draft.smoothed_centerline(samples_per_segment=24))
    if len(pts) < 2:
        return None
    outer, _visible_inner = rectangular_vent_footprint_geometries(draft, pts)
    if outer is None or getattr(outer, "is_empty", True):
        return None
    use_fill = bool(getattr(draft, "fill_area", False) if fill_area is None else fill_area)
    if use_fill:
        minx, miny, maxx, maxy = outer.bounds
        stock = shapely_box(float(minx), float(miny), float(maxx), float(maxy))
        airway = rectangular_vent_airway_cut_geometry(draft, pts, outer_reference=stock)
        base = stock
    else:
        airway = rectangular_vent_airway_cut_geometry(draft, pts, outer_reference=outer)
        base = outer
    if airway is None or getattr(airway, "is_empty", True):
        return None
    try:
        material = base.difference(airway).buffer(0)
    except Exception:
        material = base.difference(airway)
    return material

def rectangular_vent_footprint_geometries(draft: "VentPathDraft", centerline: Iterable[Vec2] | None = None):
    """Return ``(outer, inner)`` Shapely footprints for rectangular EVT.

    The rectangular tool no longer widens every sampled station to draw an
    embouchure.  It builds a constant-width duct and adds a small rectangular
    mouth pad only at the real start/end waypoint.  This keeps the preview and
    Apply result local and predictable: changing curve radius cannot spread the
    embouchure over several waypoints.
    """

    pts = clean_polyline(centerline if centerline is not None else draft.smoothed_centerline(samples_per_segment=24))
    if len(pts) < 2:
        return (None, None)
    width, _height = draft.section_dimensions()
    wall = max(float(getattr(draft, "wall_thickness", 0.0)), 0.0)
    factor = max(float(draft.normalized_flare_factor()), 1.0) if hasattr(draft, "normalized_flare_factor") else 1.0
    inner_half = max(float(width) * 0.5, 1e-9)
    outer_half = inner_half + wall
    inner_parts = [_line_buffer(pts, inner_half, join_style=1, cap_style=2)]
    outer_parts = [_line_buffer(pts, outer_half, join_style=1, cap_style=2)]

    waypoints = clean_polyline(getattr(draft, "waypoints", []))
    if len(waypoints) >= 2 and factor > 1.000001:
        flared_inner_half = max(float(width) * factor * 0.5, inner_half)
        flared_outer_half = flared_inner_half + wall
        if getattr(draft, "flare_applies_to_start", lambda: False)():
            depth = _endpoint_flare_depth(draft, at_start=True)
            tangent = _endpoint_tangent_from_waypoints(waypoints, at_start=True)
            inner_parts.append(_endpoint_flare_polygon(waypoints[0], tangent, inner_half, flared_inner_half, depth, at_start=True))
            outer_parts.append(_endpoint_flare_polygon(waypoints[0], tangent, outer_half, flared_outer_half, depth, at_start=True))
        if getattr(draft, "flare_applies_to_end", lambda: False)():
            depth = _endpoint_flare_depth(draft, at_start=False)
            tangent = _endpoint_tangent_from_waypoints(waypoints, at_start=False)
            inner_parts.append(_endpoint_flare_polygon(waypoints[-1], tangent, inner_half, flared_inner_half, depth, at_start=False))
            outer_parts.append(_endpoint_flare_polygon(waypoints[-1], tangent, outer_half, flared_outer_half, depth, at_start=False))

    return (_union_geometries(outer_parts), _union_geometries(inner_parts))




def rectangular_vent_material_outline_paths(draft: "VentPathDraft", centerline: Iterable[Vec2] | None = None, *, fill_area: bool | None = None) -> list[list[Vec2]]:
    material = rectangular_vent_material_footprint(draft, centerline, fill_area=fill_area)
    return _iter_polygon_rings(material)

def rectangular_vent_outline_paths(draft: "VentPathDraft", centerline: Iterable[Vec2] | None = None) -> tuple[list[list[Vec2]], list[list[Vec2]]]:
    outer, inner = rectangular_vent_footprint_geometries(draft, centerline)
    return (_iter_polygon_rings(outer), _iter_polygon_rings(inner))


def rectangular_vent_bounds(draft: "VentPathDraft", centerline: Iterable[Vec2] | None = None) -> tuple[float, float, float, float] | None:
    outer, _inner = rectangular_vent_footprint_geometries(draft, centerline)
    if outer is not None and not getattr(outer, "is_empty", True):
        minx, miny, maxx, maxy = outer.bounds
        return (float(minx), float(miny), float(maxx), float(maxy))
    return None

def snap_anchor_points(draft: "VentPathDraft", *, samples_per_segment: int = 12) -> list[Vec2]:
    anchors: list[Vec2] = []
    anchors.extend((float(u), float(v)) for u, v in draft.waypoints)
    center = draft.smoothed_centerline(samples_per_segment=samples_per_segment)
    anchors.extend(center)
    outer_rings, inner_rings = rectangular_vent_outline_paths(draft, center)
    for ring in outer_rings + inner_rings:
        anchors.extend(ring)
    cleaned: list[Vec2] = []
    for p in anchors:
        if not any(distance2d(p, q) <= 1e-6 for q in cleaned):
            cleaned.append((float(p[0]), float(p[1])))
    return cleaned
