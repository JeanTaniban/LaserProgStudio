"""Topology and local-plane helpers for Cloth panels."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from laserprog_studio.tool_api.tracing import distance3, sample_circular_arc_3d

from .models import ClothCurve, ClothCurveKind, ClothDocument, ClothPatch, Point3

Point2 = tuple[float, float]
_EPS = 1.0e-9
_ARC_CHORD_TOLERANCE_MM = 0.05
_ARC_MAX_SEGMENTS = 512


def _add(a: Point3, b: Point3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(v: Point3, factor: float) -> Point3:
    return (v[0] * factor, v[1] * factor, v[2] * factor)


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v: Point3) -> float:
    return math.sqrt(_dot(v, v))


def _normalize(v: Point3) -> Point3 | None:
    length = _norm(v)
    if length <= _EPS:
        return None
    return _scale(v, 1.0 / length)


def _distance_point_to_segment(point: Point3, start: Point3, end: Point3) -> float:
    segment = _sub(end, start)
    length_sq = _dot(segment, segment)
    if length_sq <= _EPS * _EPS:
        return _norm(_sub(point, start))
    t = max(0.0, min(1.0, _dot(_sub(point, start), segment) / length_sq))
    projected = _add(start, _scale(segment, t))
    return _norm(_sub(point, projected))


def _adaptive_arc_samples(
    start: Point3,
    end: Point3,
    control: Point3,
    *,
    minimum_segments: int,
    chord_tolerance_mm: float = _ARC_CHORD_TOLERANCE_MM,
    maximum_segments: int = _ARC_MAX_SEGMENTS,
) -> tuple[Point3, ...]:
    """Sample a circular arc with a bounded chord error.

    Cloth faces used to rely on a fixed 24-segment approximation.  Tight or
    long arcs could therefore create skinny/crossing triangles between two
    curved boundaries.  The adaptive refinement below is deliberately based on
    the public exact arc sampler, so degenerate quadratic fallbacks keep the
    same semantics as previews and validation.
    """

    segments = max(4, int(minimum_segments))
    limit = max(segments, min(_ARC_MAX_SEGMENTS, int(maximum_segments)))
    tolerance = max(1.0e-6, float(chord_tolerance_mm))
    coarse = sample_circular_arc_3d(start, end, control, segments=segments)
    while segments < limit:
        refined_segments = min(limit, segments * 2)
        refined = sample_circular_arc_3d(start, end, control, segments=refined_segments)
        # When doubling, every odd refined point is the midpoint of one coarse
        # parameter interval.  Its distance to the matching chord is an upper
        # estimate of the visible tessellation error.
        if refined_segments == segments * 2 and len(refined) == refined_segments + 1:
            error = max(
                (
                    _distance_point_to_segment(
                        refined[2 * index + 1],
                        coarse[index],
                        coarse[index + 1],
                    )
                    for index in range(len(coarse) - 1)
                ),
                default=0.0,
            )
            if error <= tolerance:
                break
        coarse = refined
        segments = refined_segments

    # Preserve the exact user control point in the sampled boundary.  This
    # makes the intended side/major arc explicit to triangulation instead of
    # merely approximating it between two samples.
    values = list(coarse)
    if len(values) >= 2 and min(_norm(_sub(value, control)) for value in values) > 1.0e-9:
        segment_index = min(
            range(len(values) - 1),
            key=lambda index: _distance_point_to_segment(control, values[index], values[index + 1]),
        )
        values.insert(segment_index + 1, control)
    return tuple(values)


def best_fit_boundary_frame(points: Sequence[Point3]) -> PatchFrame | None:
    """Return a stable local frame fitted to a complete ordered boundary.

    The previous frame used the first three sampled points.  When the first
    boundary element was an arc, those points were close together and could
    amplify floating-point noise or pick the local plane of only that arc.  A
    Newell normal uses the complete loop and remains deterministic without a
    numerical dependency.
    """

    if len(points) < 3:
        return None
    origin = points[0]
    nx = ny = nz = 0.0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    normal = _normalize((nx, ny, nz))
    if normal is None:
        for index in range(1, len(points) - 1):
            normal = _normalize(_cross(_sub(points[index], origin), _sub(points[index + 1], origin)))
            if normal is not None:
                break
    if normal is None:
        return None

    axis_u: Point3 | None = None
    for point in points[1:]:
        edge = _sub(point, origin)
        projected = _sub(edge, _scale(normal, _dot(edge, normal)))
        axis_u = _normalize(projected)
        if axis_u is not None:
            break
    if axis_u is None:
        return None
    axis_v = _normalize(_cross(normal, axis_u))
    if axis_v is None:
        return None
    return PatchFrame(origin, axis_u, axis_v, normal)


@dataclass(frozen=True, slots=True)
class PatchFrame:
    origin: Point3
    axis_u: Point3
    axis_v: Point3
    normal: Point3

    def project(self, point: Point3) -> Point2:
        delta = _sub(point, self.origin)
        return (_dot(delta, self.axis_u), _dot(delta, self.axis_v))

    def lift(self, point: Point2) -> Point3:
        return _add(self.origin, _add(_scale(self.axis_u, float(point[0])), _scale(self.axis_v, float(point[1]))))

    def deviation(self, point: Point3) -> float:
        return abs(_dot(_sub(point, self.origin), self.normal))


def curve_endpoint_ids(curve: ClothCurve) -> tuple[str, str]:
    if curve.kind is ClothCurveKind.ARC:
        if len(curve.point_ids) < 2:
            return ("", "")
        return (curve.point_ids[0], curve.point_ids[1])
    if len(curve.point_ids) < 2:
        return ("", "")
    if curve.kind is ClothCurveKind.POLYLINE and curve.closed:
        return (curve.point_ids[0], curve.point_ids[0])
    return (curve.point_ids[0], curve.point_ids[-1])


def oriented_curve_point_ids(curve: ClothCurve, *, reverse: bool = False) -> tuple[str, ...]:
    if curve.kind is ClothCurveKind.ARC:
        if len(curve.point_ids) != 3:
            return tuple(reversed(curve.point_ids)) if reverse else curve.point_ids
        start, end, control = curve.point_ids
        return (end, start, control) if reverse else (start, end, control)
    return tuple(reversed(curve.point_ids)) if reverse else curve.point_ids


def order_curve_loop(document: ClothDocument, curve_ids: Sequence[str]) -> tuple[tuple[str, bool], ...] | None:
    """Order connected curves into one closed loop.

    Returns ``(curve_id, reversed)`` tuples.  The algorithm is intentionally
    deterministic and suited to one panel boundary.  Global face discovery from
    an arbitrary intersection arrangement is a separate later service.
    """

    remaining = [str(curve_id) for curve_id in curve_ids]
    if not remaining:
        return None
    first_id = remaining.pop(0)
    first = document.curves.get(first_id)
    if first is None:
        return None
    start, current = curve_endpoint_ids(first)
    if not start or not current:
        return None
    ordered: list[tuple[str, bool]] = [(first_id, False)]
    while remaining:
        found_index = -1
        reverse = False
        next_endpoint = ""
        for index, curve_id in enumerate(remaining):
            curve = document.curves.get(curve_id)
            if curve is None:
                continue
            a, b = curve_endpoint_ids(curve)
            if a == current:
                found_index = index
                reverse = False
                next_endpoint = b
                break
            if b == current:
                found_index = index
                reverse = True
                next_endpoint = a
                break
        if found_index < 0:
            return None
        curve_id = remaining.pop(found_index)
        ordered.append((curve_id, reverse))
        current = next_endpoint
    return tuple(ordered) if current == start else None


def sample_curve(
    document: ClothDocument,
    curve_id: ClothCurve | str,
    *,
    arc_segments: int = 24,
    reverse: bool = False,
    chord_tolerance_mm: float = _ARC_CHORD_TOLERANCE_MM,
) -> tuple[Point3, ...]:
    curve = curve_id if isinstance(curve_id, ClothCurve) else document.curves[str(curve_id)]
    points = document.points
    if curve.kind is ClothCurveKind.LINE:
        ids = oriented_curve_point_ids(curve, reverse=reverse)
        return (points[ids[0]].position, points[ids[1]].position)
    if curve.kind is ClothCurveKind.POLYLINE:
        ids = oriented_curve_point_ids(curve, reverse=reverse)
        sampled = tuple(points[point_id].position for point_id in ids)
        if curve.closed and sampled and distance3(sampled[0], sampled[-1]) > _EPS:
            sampled = (*sampled, sampled[0])
        return sampled
    ids = oriented_curve_point_ids(curve, reverse=reverse)
    start_id, end_id, control_id = ids
    return _adaptive_arc_samples(
        points[start_id].position,
        points[end_id].position,
        points[control_id].position,
        minimum_segments=arc_segments,
        chord_tolerance_mm=chord_tolerance_mm,
    )


def sample_curve_loop_boundary(
    document: ClothDocument,
    curve_ids: Sequence[str],
    *,
    arc_segments: int = 24,
    chord_tolerance_mm: float = _ARC_CHORD_TOLERANCE_MM,
) -> tuple[Point3, ...]:
    ordered = order_curve_loop(document, curve_ids)
    if ordered is None:
        return ()
    result: list[Point3] = []
    for curve_id, reverse in ordered:
        sampled = list(
            sample_curve(
                document,
                curve_id,
                arc_segments=arc_segments,
                reverse=reverse,
                chord_tolerance_mm=chord_tolerance_mm,
            )
        )
        if result and sampled and distance3(result[-1], sampled[0]) <= _EPS:
            sampled = sampled[1:]
        result.extend(sampled)
    if len(result) >= 2 and distance3(result[0], result[-1]) <= _EPS:
        result.pop()
    return tuple(result)


def sample_patch_boundary(
    document: ClothDocument,
    patch: ClothPatch | str,
    *,
    arc_segments: int = 24,
    chord_tolerance_mm: float = _ARC_CHORD_TOLERANCE_MM,
) -> tuple[Point3, ...]:
    item = document.patches[str(patch)] if isinstance(patch, str) else patch
    return sample_curve_loop_boundary(
        document,
        item.outer_curve_ids,
        arc_segments=arc_segments,
        chord_tolerance_mm=chord_tolerance_mm,
    )


def patch_point_ids(document: ClothDocument, patch: ClothPatch | str) -> tuple[str, ...]:
    item = document.patches[str(patch)] if isinstance(patch, str) else patch
    ids: list[str] = []
    for curve_id in (*item.outer_curve_ids, *(value for loop in item.hole_curve_loops for value in loop)):
        curve = document.curves.get(curve_id)
        if curve is None:
            continue
        for point_id in curve.point_ids:
            if point_id not in ids:
                ids.append(point_id)
    return tuple(ids)


def patch_frame(document: ClothDocument, patch: ClothPatch | str) -> PatchFrame | None:
    boundary = sample_patch_boundary(document, patch, arc_segments=12)
    return best_fit_boundary_frame(boundary)


def polygon_signed_area(points: Sequence[Point2]) -> float:
    if len(points) < 3:
        return 0.0
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


def patch_area(document: ClothDocument, patch: ClothPatch | str) -> float:
    frame = patch_frame(document, patch)
    boundary = sample_patch_boundary(document, patch)
    if frame is None or len(boundary) < 3:
        return 0.0
    return abs(polygon_signed_area(tuple(frame.project(point) for point in boundary)))


def curve_patch_incidence(document: ClothDocument) -> dict[str, tuple[str, ...]]:
    values: dict[str, list[str]] = {curve_id: [] for curve_id in document.curves}
    for patch in document.patches.values():
        for curve_id in (*patch.outer_curve_ids, *(item for loop in patch.hole_curve_loops for item in loop)):
            values.setdefault(curve_id, []).append(patch.id)
    return {curve_id: tuple(patch_ids) for curve_id, patch_ids in values.items()}


def chain_length(document: ClothDocument, curve_ids: Iterable[str]) -> float:
    total = 0.0
    for curve_id in curve_ids:
        points = sample_curve(document, curve_id)
        total += sum(distance3(points[index - 1], points[index]) for index in range(1, len(points)))
    return total


__all__ = [
    "PatchFrame",
    "best_fit_boundary_frame",
    "chain_length",
    "curve_endpoint_ids",
    "curve_patch_incidence",
    "order_curve_loop",
    "oriented_curve_point_ids",
    "patch_area",
    "patch_frame",
    "patch_point_ids",
    "polygon_signed_area",
    "sample_curve",
    "sample_curve_loop_boundary",
    "sample_patch_boundary",
]
