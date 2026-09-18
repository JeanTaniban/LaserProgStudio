"""Face extraction from a noded planar arrangement.

This module intentionally keeps the heavy curve/line partitioning logic out of
``face_solver.py``.  The sketch document stores user-authored entities (lines,
arcs and full circles).  Face extraction, however, must work on the *arrangement*
of those entities: every intersection is a node and every bounded cell is a face.

The implementation uses Shapely for the arrangement step.  It samples arcs and
circles into deterministic line strings, nodes sampled curve crossings through
GEOS, then polygonizes the resulting planar graph.  Already-split line-only
sketches skip the redundant noding pass.  The source sketch is not mutated, so
live Plan Tracer editing does not convert circles into arcs.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Iterable

from laserprog_studio.tool_core.geometry import (
    arc_from_three_points,
    circle_from_two_points,
    distance_2d,
    point_on_circle,
    sample_circle,
    sample_circular_arc_through_points,
    sample_cubic_bezier,
)

from .document import SketchDocument, face_signature_from_points

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class ArrangementFaceOptions:
    join_tolerance: float = 0.25
    min_area: float = 1.0e-4
    circle_segments: int = 72
    arc_segments: int = 24
    bezier_segments: int = 48
    curve_contact_tolerance: float = 0.25


@dataclass(frozen=True, slots=True)
class _SourceCurve:
    entity_id: str
    geometry: object


def solve_faces_from_arrangement(sketch: SketchDocument, options: ArrangementFaceOptions) -> tuple[str, ...]:
    """Replace ``sketch.faces`` with bounded cells from the current linework.

    The returned faces are non-overlapping cells.  Nested contours naturally
    become an outer ring face plus the inner island face.  Crossings such as
    ``line + circle``, ``rectangle edge + circle`` or ``circle + circle`` are
    handled by the same noding/polygonize pipeline instead of by hand-written
    special cases.
    """

    try:
        from shapely.geometry import GeometryCollection, LineString, MultiLineString, Polygon
        from shapely.ops import polygonize, unary_union
    except Exception as exc:  # pragma: no cover - dependency alternate path handled by caller
        raise RuntimeError("shapely_unavailable") from exc

    phase_started = _time_now_if_enabled()
    sources = _source_curves(sketch, options)
    _record_elapsed_if_enabled("source_curves", phase_started)
    sketch.faces.clear()
    if not sources:
        return ()

    phase_started = _time_now_if_enabled()
    geometries = [source.geometry for source in sources]
    # SketchCompiler has already inserted line intersections and split line
    # segments before face solving.  Feeding that noded linework directly to
    # polygonize avoids a redundant GEOS unary union for the dominant Plan
    # Tracer case (rectangles/polylines only).  Curves still use unary_union
    # because their sampled intersections must be noded here.
    line_only = not sketch.arcs and not sketch.beziers and not sketch.circles
    noded = geometries if line_only else unary_union(geometries)
    polygons = [poly for poly in polygonize(noded) if isinstance(poly, Polygon) and poly.area >= options.min_area]
    _record_elapsed_if_enabled("polygonize", phase_started)
    if not polygons:
        return ()

    # ``polygonize`` can return equivalent cells in a GeometryCollection/MultiLine
    # corner case.  Dedupe by the same stable signature used by generated faces.
    polygons.sort(key=lambda poly: (-float(poly.area), _geometry_sort_key(poly)))
    seen: set[str] = set()
    created: list[str] = []
    pending_faces: list[tuple[str, object, str]] = []
    line_boundary_index = _build_line_boundary_index(sketch, options.join_tolerance) if line_only else None

    phase_started = _time_now_if_enabled()
    for poly in polygons:
        exterior = _clean_ring(poly.exterior.coords, options.join_tolerance)
        if len(exterior) < 3:
            continue
        holes = tuple(
            ring
            for ring in (_clean_ring(interior.coords, options.join_tolerance) for interior in poly.interiors)
            if len(ring) >= 3
        )
        signature = face_signature_from_points(exterior, hole_polygons=holes)
        if signature in seen:
            continue
        seen.add(signature)
        boundary_ids = _boundary_entity_ids_indexed(
            poly.exterior,
            line_boundary_index,
            sources,
            options.join_tolerance,
        )
        if not boundary_ids:
            # A bounded cell without source ids is not useful for selection or
            # deletion.  Keep the solver conservative instead of producing an
            # anonymous face that cannot be explained to the editor.
            continue
        hole_boundary_ids = tuple(
            _boundary_entity_ids_indexed(interior, line_boundary_index, sources, options.join_tolerance)
            for interior in poly.interiors
        )
        face = sketch.add_face(
            boundary_ids,
            exterior,
            signature=signature,
            hole_polygons=holes,
            hole_boundary_entity_ids=hole_boundary_ids,
        )
        if face is None:
            continue
        face.metadata["hole_count"] = len(holes)
        face.metadata["contains_holes"] = bool(holes)
        face.metadata["arrangement_solver"] = "shapely_polygonize"
        pending_faces.append((face.id, poly, signature))
        created.append(face.id)
    _record_elapsed_if_enabled("build_faces", phase_started)

    phase_started = _time_now_if_enabled()
    _annotate_containment_metadata(sketch, pending_faces)
    _record_elapsed_if_enabled("containment", phase_started)
    return tuple(created)


def _source_curves(sketch: SketchDocument, options: ArrangementFaceOptions) -> list[_SourceCurve]:
    """Build linework with exact curve-contact nodes.

    Snap targets for sampled arcs can place a line endpoint a fraction of a
    millimetre away from the analytic curve.  A visually closed contour then
    contains a microscopic gap and GEOS refuses to polygonize it.  We resolve
    only *edge endpoints* that are close to a circle/arc, project them onto the
    analytic curve, and inject the exact same coordinate into both source
    geometries.  The authored sketch remains untouched.
    """

    from shapely.geometry import LineString

    sources: list[_SourceCurve] = []
    contact_tolerance = max(float(options.join_tolerance), float(options.curve_contact_tolerance), 1.0e-7)

    circles: dict[str, object] = {}
    for circle_id, circle in sketch.circles.items():
        center = sketch.points.get(circle.center_point_id)
        radius_point = sketch.points.get(circle.radius_point_id)
        if center is None or radius_point is None:
            continue
        circle2 = circle_from_two_points(center.position, radius_point.position)
        if circle2 is not None:
            circles[str(circle_id)] = circle2

    arcs: dict[str, object] = {}
    for arc_id, arc in sketch.arcs.items():
        start = sketch.points.get(arc.start_point_id)
        end = sketch.points.get(arc.end_point_id)
        control = sketch.points.get(arc.control_point_id)
        if start is None or end is None or control is None:
            continue
        arc2 = arc_from_three_points(start.position, end.position, control.position)
        if arc2 is not None:
            arcs[str(arc_id)] = arc2

    endpoint_ids = {
        point_id
        for line in sketch.lines.values()
        for point_id in (line.start_point_id, line.end_point_id)
    }
    endpoint_overrides: dict[str, Point2] = {}
    circle_contacts: dict[str, list[tuple[float, Point2]]] = {key: [] for key in circles}
    arc_contacts: dict[str, list[tuple[float, Point2]]] = {key: [] for key in arcs}

    for point_id in endpoint_ids:
        point = sketch.points.get(point_id)
        if point is None:
            continue
        px, py = point.position
        # (distance, curve kind, curve id, curve parameter, projected point)
        best: tuple[float, str, str, float, Point2] | None = None
        for circle_id, circle2 in circles.items():
            radial = distance_2d(point.position, circle2.center)
            if radial <= 1.0e-12:
                continue
            angle = math.atan2(py - circle2.center[1], px - circle2.center[0])
            projected = point_on_circle(circle2.center, circle2.radius, angle)
            error = distance_2d(point.position, projected)
            if error > contact_tolerance:
                continue
            parameter = (angle % math.tau) / math.tau
            candidate = (error, "circle", circle_id, parameter, projected)
            if best is None or candidate[0] < best[0]:
                best = candidate
        for arc_id, arc2 in arcs.items():
            radial = distance_2d(point.position, arc2.center)
            candidates: list[tuple[float, Point2]] = [
                (0.0, arc2.point_at(0.0)),
                (1.0, arc2.point_at(1.0)),
            ]
            if radial > 1.0e-12:
                angle = math.atan2(py - arc2.center[1], px - arc2.center[0])
                parameter = arc2.parameter_for_angle(angle)
                if parameter is not None:
                    candidates.append((parameter, arc2.point_at(parameter)))
            parameter, projected = min(
                candidates,
                key=lambda item: distance_2d(point.position, item[1]),
            )
            error = distance_2d(point.position, projected)
            if error > contact_tolerance:
                continue
            candidate = (error, "arc", arc_id, parameter, projected)
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best is None:
            continue
        _error, curve_kind, curve_id, parameter, projected = best
        endpoint_overrides[str(point_id)] = projected
        if curve_kind == "circle":
            circle_contacts[curve_id].append((parameter, projected))
        else:
            arc_contacts[curve_id].append((parameter, projected))

    for line_id, line in sketch.lines.items():
        start = sketch.points.get(line.start_point_id)
        end = sketch.points.get(line.end_point_id)
        if start is None or end is None:
            continue
        start_xy = endpoint_overrides.get(str(line.start_point_id), start.position)
        end_xy = endpoint_overrides.get(str(line.end_point_id), end.position)
        if distance_2d(start_xy, end_xy) <= options.min_area:
            continue
        sources.append(_SourceCurve(str(line_id), LineString((start_xy, end_xy))))

    for arc_id, arc in sketch.arcs.items():
        start_point = sketch.points.get(arc.start_point_id)
        end_point = sketch.points.get(arc.end_point_id)
        control = sketch.points.get(arc.control_point_id)
        arc2 = arcs.get(str(arc_id))
        if start_point is None or end_point is None or control is None:
            continue
        if arc2 is None:
            samples = sample_circular_arc_through_points(start_point.position, end_point.position, control.position, segments=options.arc_segments)
        else:
            parameters = {index / max(4, int(options.arc_segments)) for index in range(max(4, int(options.arc_segments)) + 1)}
            parameters.update(parameter for parameter, _point in arc_contacts.get(str(arc_id), ()))
            contact_by_key = {round(parameter, 12): point for parameter, point in arc_contacts.get(str(arc_id), ())}
            samples = [contact_by_key.get(round(parameter, 12), arc2.point_at(parameter)) for parameter in sorted(parameters)]
        if len(samples) >= 2:
            samples[0] = endpoint_overrides.get(str(arc.start_point_id), start_point.position)
            samples[-1] = endpoint_overrides.get(str(arc.end_point_id), end_point.position)
            sources.append(_SourceCurve(str(arc_id), LineString(samples)))

    for bezier_id, bezier in getattr(sketch, "beziers", {}).items():
        start_point = sketch.points.get(bezier.start_point_id)
        end_point = sketch.points.get(bezier.end_point_id)
        control_1 = sketch.points.get(bezier.control_1_point_id)
        control_2 = sketch.points.get(bezier.control_2_point_id)
        if start_point is None or end_point is None or control_1 is None or control_2 is None:
            continue
        samples = sample_cubic_bezier(
            endpoint_overrides.get(str(bezier.start_point_id), start_point.position),
            control_1.position,
            control_2.position,
            endpoint_overrides.get(str(bezier.end_point_id), end_point.position),
            segments=options.bezier_segments,
        )
        if len(samples) >= 2:
            sources.append(_SourceCurve(str(bezier_id), LineString(samples)))

    for circle_id, circle in sketch.circles.items():
        circle2 = circles.get(str(circle_id))
        if circle2 is None:
            continue
        segment_count = max(12, int(options.circle_segments))
        parameters = {index / segment_count for index in range(segment_count)}
        parameters.update(parameter % 1.0 for parameter, _point in circle_contacts.get(str(circle_id), ()))
        contact_by_key = {round(parameter % 1.0, 12): point for parameter, point in circle_contacts.get(str(circle_id), ())}
        ordered = sorted(parameters)
        samples = [
            contact_by_key.get(round(parameter, 12), point_on_circle(circle2.center, circle2.radius, parameter * math.tau))
            for parameter in ordered
        ]
        if len(samples) >= 3:
            sources.append(_SourceCurve(str(circle_id), LineString([*samples, samples[0]])))
    return sources


def _boundary_entity_ids(boundary: object, sources: Iterable[_SourceCurve], tolerance: float) -> tuple[str, ...]:
    ids: list[str] = []
    threshold = max(float(tolerance) * 0.25, 1.0e-7)
    corridor = None
    for source in sources:
        try:
            intersection = boundary.intersection(source.geometry)
            length = float(getattr(intersection, "length", 0.0))
            if length <= threshold:
                # GEOS noding can move a contact by a few floating-point ulps.
                # Exact intersection then reports only a point even though the
                # complete source segment is a face boundary. Use a very narrow
                # tolerant corridor solely for source-id attribution.
                if corridor is None:
                    corridor = boundary.buffer(max(abs(float(tolerance)) * 1.0e-3, 1.0e-8))
                tolerant = corridor.intersection(source.geometry)
                length = float(getattr(tolerant, "length", 0.0))
        except Exception:
            length = 0.0
        if length > threshold:
            ids.append(source.entity_id)
    return tuple(sorted(set(ids)))


def _point_key(point: tuple[float, float], tolerance: float) -> tuple[int, int]:
    quantum = max(abs(float(tolerance)) * 0.1, 1.0e-8)
    return (round(float(point[0]) / quantum), round(float(point[1]) / quantum))


def _segment_key(a: tuple[float, float], b: tuple[float, float], tolerance: float) -> tuple[tuple[int, int], tuple[int, int]]:
    pa = _point_key(a, tolerance)
    pb = _point_key(b, tolerance)
    return (pa, pb) if pa <= pb else (pb, pa)


def _build_line_boundary_index(sketch: SketchDocument, tolerance: float) -> dict[tuple[tuple[int, int], tuple[int, int]], tuple[str, ...]]:
    grouped: dict[tuple[tuple[int, int], tuple[int, int]], list[str]] = {}
    for line_id, line in sketch.lines.items():
        start = sketch.points.get(line.start_point_id)
        end = sketch.points.get(line.end_point_id)
        if start is None or end is None:
            continue
        grouped.setdefault(_segment_key(start.position, end.position, tolerance), []).append(str(line_id))
    return {key: tuple(sorted(set(values))) for key, values in grouped.items()}


def _boundary_entity_ids_indexed(
    boundary: object,
    index: dict[tuple[tuple[int, int], tuple[int, int]], tuple[str, ...]] | None,
    sources: Iterable[_SourceCurve],
    tolerance: float,
) -> tuple[str, ...]:
    if index is not None:
        try:
            coords = tuple((float(value[0]), float(value[1])) for value in boundary.coords)
        except Exception:
            coords = ()
        if len(coords) >= 2:
            ids: list[str] = []
            missing = False
            for first, second in zip(coords, coords[1:]):
                values = index.get(_segment_key(first, second, tolerance))
                if not values:
                    missing = True
                    break
                ids.extend(values)
            if not missing and ids:
                return tuple(sorted(set(ids)))
    return _boundary_entity_ids(boundary, sources, tolerance)


def _clean_ring(coords: Iterable[tuple[float, float]], tolerance: float) -> tuple[Point2, ...]:
    cleaned: list[Point2] = []
    tol = max(float(tolerance), 0.0)
    for coord in coords:
        point = (float(coord[0]), float(coord[1]))
        if cleaned and distance_2d(cleaned[-1], point) <= tol * 1.0e-3:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and distance_2d(cleaned[0], cleaned[-1]) <= max(tol * 1.0e-3, 1.0e-9):
        cleaned.pop()
    return tuple(cleaned)


def _annotate_containment_metadata(sketch: SketchDocument, faces: list[tuple[str, object, str]]) -> None:
    if not faces:
        return
    prepared: list[tuple[str, object, float, Point2, tuple[Point2, ...], tuple[tuple[Point2, ...], ...]]] = []
    for face_id, poly, _signature in faces:
        try:
            sample_geom = poly.representative_point()
            sample = (float(sample_geom.x), float(sample_geom.y))
            exterior = tuple((float(value[0]), float(value[1])) for value in tuple(poly.exterior.coords)[:-1])
            holes = tuple(
                tuple((float(value[0]), float(value[1])) for value in tuple(interior.coords)[:-1])
                for interior in poly.interiors
            )
            prepared.append((face_id, poly, float(poly.area), sample, exterior, holes))
        except Exception:
            continue

    for face_id, poly, area, sample, _exterior, _holes in prepared:
        face = sketch.faces.get(face_id)
        if face is None:
            continue
        containers: list[tuple[object, float]] = []
        hole_parents: list[tuple[object, float]] = []
        for other_id, other, other_area, _other_sample, other_exterior, other_holes in prepared:
            if other_id == face_id or other_area <= area:
                continue
            if _point_in_ring(sample, other_exterior) and not any(_point_in_ring(sample, hole) for hole in other_holes):
                containers.append((other, other_area))
            elif any(_point_in_ring(sample, hole) for hole in other_holes):
                hole_parents.append((other, other_area))
        face.metadata["containment_depth"] = len(containers) + len(hole_parents)
        # Preserve the established nested-loop metadata: an island generated
        # from a hole is any non-hole cell contained by another
        # face *or* exactly filling one of another face's holes.  Shapely's
        # Polygon.contains correctly returns False for points inside holes, so
        # we need the explicit hole-parent check for nested rectangles.
        if (containers or hole_parents) and not face.hole_polygons:
            face.metadata["generated_from_hole"] = True
            _nearest, nearest_area = min([*containers, *hole_parents], key=lambda candidate: candidate[1])
            face.metadata["hole_parent_area"] = float(nearest_area)


def _point_in_ring(point: Point2, ring: tuple[Point2, ...]) -> bool:
    """Even/odd point-in-polygon test for representative points off boundaries."""

    if len(ring) < 3:
        return False
    x, y = float(point[0]), float(point[1])
    inside = False
    previous = ring[-1]
    for current in ring:
        x0, y0 = previous
        x1, y1 = current
        if (y0 > y) != (y1 > y):
            denominator = y1 - y0
            if abs(denominator) > 1.0e-30:
                intersection_x = x0 + (y - y0) * (x1 - x0) / denominator
                if x < intersection_x:
                    inside = not inside
        previous = current
    return inside


def _geometry_sort_key(poly: object) -> tuple[float, float, float]:
    try:
        centroid = poly.centroid
        return (round(float(centroid.x), 6), round(float(centroid.y), 6), round(float(poly.length), 6))
    except Exception:
        return (0.0, 0.0, 0.0)


def _face_timing_enabled() -> bool:
    """Return whether high-frequency face-solver timings may be recorded.

    The arrangement solver is part of the pure sketch kernel and must stay safe
    when the application diagnostics package is unavailable.  A previous merge
    accidentally removed this helper while leaving its call sites in place; the
    resulting ``NameError`` made every Shapely arrangement solve fall back to the
    older loop candidate solver.
    """

    try:
        from laserprog_studio.services.debug_mode import is_debug_mode_enabled

        return bool(is_debug_mode_enabled())
    except Exception:
        return False


def _time_now_if_enabled() -> float | None:
    if not _face_timing_enabled():
        return None
    return time.perf_counter()


def _record_elapsed_if_enabled(name: str, started: float | None) -> None:
    if started is None:
        return
    _record_face_timing(str(name), (time.perf_counter() - float(started)) * 1000.0)


def _record_face_timing(name: str, elapsed_ms: float) -> None:
    if not _face_timing_enabled():
        return
    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.record_timing(f"sketch.face_solver.{name}", float(elapsed_ms))
    except Exception:
        pass
