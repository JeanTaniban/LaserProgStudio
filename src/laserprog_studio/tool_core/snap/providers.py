"""Reusable snap providers."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from math import atan2, cos, isfinite, radians, sqrt, sin
from typing import Any, Callable

from .types import Point2, Point3, SnapKind, SnapResult, SnapSource, SnapTarget, snap_kind_for_source
from ..events import screen_distance
from ..geometry import (
    Arc2,
    Circle2,
    arc_arc_intersections,
    arc_from_three_points,
    circle_arc_intersections,
    circle_circle_intersections,
    line_arc_intersections,
    line_circle_intersections,
    point3_to_xy,
)


def _world_to_screen(ctx: Any, pos: Point3) -> Point2:
    if hasattr(ctx, "viewport") and hasattr(ctx.viewport, "world_to_screen"):
        return ctx.viewport.world_to_screen(pos)
    return (float(pos[0]), float(pos[1]))


def _metadata_screen_pos(metadata: dict[str, Any], key: str) -> Point2 | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except Exception:
        return None


def _world_to_screen_cached(ctx: Any, pos: Point3, metadata: dict[str, Any], key: str) -> Point2:
    cached = _metadata_screen_pos(metadata, key)
    if cached is not None:
        return cached
    return _world_to_screen(ctx, pos)


def _closest_point_on_segment_2d_with_t(p: Point2, a: Point2, b: Point2) -> tuple[Point2, float]:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    px, py = float(p[0]), float(p[1])
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom <= 1.0e-12:
        return (ax, ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return (ax + abx * t, ay + aby * t), t


def _closest_point_on_segment_2d(p: Point2, a: Point2, b: Point2) -> Point2:
    projected, _t = _closest_point_on_segment_2d_with_t(p, a, b)
    return projected


def _lerp_point3(a: Point3, b: Point3, t: float) -> Point3:
    u = max(0.0, min(1.0, float(t)))
    return (
        float(a[0]) + (float(b[0]) - float(a[0])) * u,
        float(a[1]) + (float(b[1]) - float(a[1])) * u,
        float(a[2]) + (float(b[2]) - float(a[2])) * u,
    )


def _target_label(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("snap_label", metadata.get("label"))
    return None if value is None else str(value)


@dataclass(slots=True)
class GridSnapProvider:
    grid_size: float = 1.0
    priority: int = 900
    enabled: bool = True
    id: str = "grid"

    def build_cache(self, ctx: Any) -> None:  # noqa: ARG002
        return None

    def query(self, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:  # noqa: ARG002
        if not self.enabled or self.grid_size <= 0:
            return []
        size = self.grid_size
        snapped = (round(world_pos[0] / size) * size, round(world_pos[1] / size) * size, round(world_pos[2] / size) * size)
        return [SnapResult(True, snapped, SnapSource.GRID, distance_px=0.0, priority=self.priority, kind=SnapKind.GRID)]


@dataclass(slots=True)
class PointSnapProvider:
    source: SnapSource
    point_getter: Callable[[Any], list[tuple[str, Point3]]]
    radius_px: float = 18.0
    priority: int = 20
    enabled: bool = True
    id: str = "point"
    _points: list[tuple[str, Point3]] = field(default_factory=list)

    def build_cache(self, ctx: Any) -> None:
        self._points = list(self.point_getter(ctx)) if self.enabled else []

    def query(self, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:  # noqa: ARG002
        if not self.enabled:
            return []
        results: list[SnapResult] = []
        for point_id, point in self._points:
            dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
            if dist <= self.radius_px:
                results.append(SnapResult(True, point, self.source, point_id, dist, self.priority, kind=SnapKind.VERTEX))
        return results


@dataclass(slots=True)
class SegmentSnapProvider:
    source: SnapSource
    segment_getter: Callable[[Any], list[tuple[str, Point3, Point3]]]
    radius_px: float = 14.0
    priority: int = 80
    enabled: bool = True
    id: str = "segment"
    _segments: list[tuple[str, Point3, Point3]] = field(default_factory=list)

    def build_cache(self, ctx: Any) -> None:
        self._segments = list(self.segment_getter(ctx)) if self.enabled else []

    def query(self, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:  # noqa: ARG002
        if not self.enabled:
            return []
        results: list[SnapResult] = []
        results.extend(
            _segment_intersection_results(
                tuple(
                    _SegmentCandidate(
                        id=str(seg_id),
                        source=self.source,
                        start=start,
                        end=end,
                        radius_px=float(self.radius_px),
                        priority=int(self.priority),
                        metadata={},
                    )
                    for seg_id, start, end in self._segments
                ),
                screen_pos,
                ctx,
            )
        )
        for seg_id, start, end in self._segments:
            midpoint = midpoint_on_segment_3d(start, end)
            midpoint_dist = screen_distance(_world_to_screen(ctx, midpoint), screen_pos)
            midpoint_radius = min(float(self.radius_px), 12.0)
            if midpoint_dist <= midpoint_radius:
                results.append(
                    SnapResult(
                        True,
                        midpoint,
                        self.source,
                        f"{seg_id}:midpoint",
                        midpoint_dist,
                        max(0, int(self.priority) - 10),
                        metadata={"snap_kind": SnapKind.MIDPOINT.value, "parent_segment_id": str(seg_id)},
                        kind=SnapKind.MIDPOINT,
                    )
                )
            point = closest_point_on_segment_3d(world_pos, start, end)
            dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
            if dist <= self.radius_px:
                results.append(SnapResult(True, point, self.source, seg_id, dist, self.priority, kind=SnapKind.EDGE))
        return results


@dataclass(slots=True)
class ExtraSnapProvider:
    """Provider backed by explicit ``SnapTarget`` objects."""

    targets: tuple[SnapTarget, ...] = ()
    id: str = "extra"
    priority: int = 50
    enabled: bool = True

    def build_cache(self, ctx: Any) -> None:  # noqa: ARG002
        return None

    def query(self, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:
        if not self.enabled:
            return []
        return snap_targets_to_results(self.targets, world_pos, screen_pos, ctx)


def snap_targets_to_results(targets: tuple[SnapTarget, ...] | list[SnapTarget], world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:
    with _measure_perf(ctx, "snap.targets_to_results.total"):
        results: list[SnapResult] = []
        segment_candidates: list[_SegmentCandidate] = []
        circle_candidates: list[_CircleCandidate] = []
        arc_candidates: list[_ArcCandidate] = []
        _increment_perf(ctx, "snap.targets_to_results.targets", len(targets))
        with _measure_perf(ctx, "snap.targets_to_results.classify"):
            for target in targets:
                if target.is_arc and target.start is not None and target.end is not None and target.control is not None:
                    arc = _arc_candidate_from_target(target)
                    if arc is not None:
                        arc_candidates.append(arc)
                    continue
                if target.is_circle:
                    circle = _circle_candidate_from_target(target)
                    if circle is not None:
                        circle_candidates.append(circle)
                    continue
                if target.is_segment and target.start is not None and target.end is not None:
                    segment_candidates.append(
                        _SegmentCandidate(
                            id=str(target.id),
                            source=target.source,
                            start=target.start,
                            end=target.end,
                            radius_px=float(target.radius_px),
                            priority=int(target.priority),
                            metadata=dict(target.metadata),
                        )
                    )
        _increment_perf(ctx, "snap.targets_to_results.segments", len(segment_candidates))
        _increment_perf(ctx, "snap.targets_to_results.circles", len(circle_candidates))
        _increment_perf(ctx, "snap.targets_to_results.arcs", len(arc_candidates))
        with _measure_perf(ctx, "snap.targets_to_results.segment_intersections"):
            results.extend(_segment_intersection_results(tuple(segment_candidates), screen_pos, ctx))
        with _measure_perf(ctx, "snap.targets_to_results.curve_intersections"):
            results.extend(_curve_intersection_results(tuple(segment_candidates), tuple(circle_candidates), tuple(arc_candidates), screen_pos, ctx))
        with _measure_perf(ctx, "snap.targets_to_results.direct_snaps"):
            for target in targets:
                metadata = dict(target.metadata)
                if target.is_arc and target.start is not None and target.end is not None and target.control is not None:
                    results.extend(_arc_snap_results(target, world_pos, screen_pos, ctx))
                    continue
                if target.is_circle:
                    results.extend(_circle_snap_results(target, world_pos, screen_pos, ctx))
                    continue
                if target.is_segment and target.start is not None and target.end is not None:
                    midpoint = midpoint_on_segment_3d(target.start, target.end)
                    midpoint_dist = screen_distance(_world_to_screen_cached(ctx, midpoint, metadata, "snap_midpoint_screen"), screen_pos)
                    midpoint_radius = min(float(target.radius_px), float(target.metadata.get("midpoint_radius_px", 12.0)))
                    include_midpoint = bool(target.metadata.get("include_midpoint_snap", True))
                    if include_midpoint and midpoint_dist <= midpoint_radius:
                        midpoint_metadata = {**dict(target.metadata), "snap_kind": SnapKind.MIDPOINT.value, "parent_segment_id": str(target.id)}
                        results.append(
                            SnapResult(
                                True,
                                midpoint,
                                target.source,
                                source_id=f"{target.id}:midpoint",
                                distance_px=midpoint_dist,
                                priority=max(0, int(target.priority) - 10),
                                metadata=midpoint_metadata,
                                kind=SnapKind.MIDPOINT,
                                label=_target_label(midpoint_metadata),
                            )
                        )
                    point = closest_point_on_segment_3d(world_pos, target.start, target.end)
                    start_screen = _metadata_screen_pos(metadata, "snap_start_screen")
                    end_screen = _metadata_screen_pos(metadata, "snap_end_screen")
                    if start_screen is not None and end_screen is not None:
                        projected, screen_t = _closest_point_on_segment_2d_with_t(screen_pos, start_screen, end_screen)
                        # Edge snap acceptance is screen-space based.  The snapped
                        # world point must therefore use the same screen-space
                        # parameter, otherwise a locked-plan candidate that is not
                        # close to the scene edge in 3D can project to a different
                        # place on the same edge.  That manifested as the cursor
                        # jumping far along an edge with a wrong motion ratio while
                        # vertex snaps stayed correct.
                        screen_point = _lerp_point3(target.start, target.end, screen_t)
                        world_t = _segment_parameter_3d(point, target.start, target.end)
                        if abs(float(screen_t) - float(world_t)) > 0.15:
                            _increment_perf(ctx, "snap.segment.screen_world_t_mismatch")
                            _set_perf_value(ctx, "snap.segment.last_screen_t", float(screen_t))
                            _set_perf_value(ctx, "snap.segment.last_world_t", float(world_t))
                            _set_perf_value(ctx, "snap.segment.last_source_id", str(target.id))
                        point = screen_point
                        metadata["snap_segment_screen_t"] = float(screen_t)
                    else:
                        projected = _world_to_screen(ctx, point)
                    kind = target.kind or SnapKind.EDGE
                else:
                    if target.world_pos is None and target.screen_pos is None:
                        continue
                    point = target.world_pos if target.world_pos is not None else world_pos
                    projected = target.screen_pos if target.screen_pos is not None else _world_to_screen_cached(ctx, point, dict(target.metadata), "snap_screen_pos")
                    kind = target.kind or snap_kind_for_source(target.source, metadata=target.metadata)
                dist = screen_distance(projected, screen_pos)
                if dist <= float(target.radius_px):
                    results.append(
                        SnapResult(
                            True,
                            point,
                            target.source,
                            source_id=target.id,
                            distance_px=dist,
                            priority=target.priority,
                            metadata=dict(metadata),
                            kind=kind,
                            label=_target_label(dict(metadata)),
                        )
                    )
        _increment_perf(ctx, "snap.targets_to_results.results", len(results))
        return results


def _circle_snap_results(target: SnapTarget, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:
    if target.center is None or target.radius is None or float(target.radius) <= 0.0:
        return []
    center = target.center
    radius = float(target.radius)
    basis_u, basis_v = _circle_basis(target)
    metadata = dict(target.metadata)
    results: list[SnapResult] = []

    if bool(metadata.get("include_center_snap", True)):
        center_radius = float(metadata.get("center_radius_px", min(float(target.radius_px), 4.0)))
        center_dist = screen_distance(_world_to_screen(ctx, center), screen_pos)
        if center_dist <= center_radius:
            results.append(
                SnapResult(
                    True,
                    center,
                    SnapSource.CENTER,
                    source_id=f"{target.id}:center",
                    distance_px=center_dist,
                    priority=max(0, int(target.priority) - 25),
                    metadata={**metadata, "snap_kind": SnapKind.CENTER.value, "parent_curve_id": str(target.id)},
                    kind=SnapKind.CENTER,
                )
            )

    if bool(metadata.get("include_quadrant_snap", True)):
        quadrant_radius = float(metadata.get("quadrant_radius_px", min(float(target.radius_px), 3.5)))
        for angle in (0.0, 90.0, 180.0, 270.0):
            point = _point_on_circle(center, radius, basis_u, basis_v, angle)
            dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
            if dist <= quadrant_radius:
                results.append(
                    SnapResult(
                        True,
                        point,
                        target.source,
                        source_id=f"{target.id}:quadrant:{int(angle)}",
                        distance_px=dist,
                        priority=max(0, int(target.priority) - 15),
                        metadata={**metadata, "snap_kind": SnapKind.QUADRANT.value, "parent_curve_id": str(target.id), "angle_degrees": angle},
                        kind=SnapKind.QUADRANT,
                    )
                )

    angle_values = _angle_snap_values(metadata)
    if angle_values:
        angle_radius = float(metadata.get("angle_radius_px", min(float(target.radius_px), 3.5)))
        for angle in angle_values:
            normalized = _normalize_angle_degrees(angle)
            # Quadrants already have a stronger, clearer kind.  Avoid duplicate
            # candidates fighting over the same screen point.
            if abs((normalized % 90.0)) <= 1.0e-9 or abs((normalized % 90.0) - 90.0) <= 1.0e-9:
                continue
            point = _point_on_circle(center, radius, basis_u, basis_v, normalized)
            dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
            if dist <= angle_radius:
                results.append(
                    SnapResult(
                        True,
                        point,
                        target.source,
                        source_id=f"{target.id}:angle:{_angle_id(normalized)}",
                        distance_px=dist,
                        priority=max(0, int(target.priority) - 18),
                        metadata={**metadata, "snap_kind": SnapKind.ANGLE.value, "parent_curve_id": str(target.id), "angle_degrees": normalized},
                        kind=SnapKind.ANGLE,
                    )
                )

    if bool(metadata.get("include_curve_snap", True)):
        curve_radius = float(metadata.get("curve_radius_px", float(target.radius_px)))
        point = closest_point_on_circle_3d(world_pos, center, radius, basis_u, basis_v)
        dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
        if dist <= curve_radius:
            results.append(
                SnapResult(
                    True,
                    point,
                    target.source,
                    source_id=str(target.id),
                    distance_px=dist,
                    priority=int(target.priority),
                    metadata={**metadata, "snap_kind": SnapKind.EDGE.value, "parent_curve_id": str(target.id), "curve_type": "circle"},
                    kind=target.kind or SnapKind.EDGE,
                )
            )
    return results



def _arc_snap_results(target: SnapTarget, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]:
    candidate = _arc_candidate_from_target(target)
    if candidate is None:
        return []
    point, t = _closest_point_on_arc_candidate(world_pos, candidate)
    dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
    if dist > float(target.radius_px):
        return []
    metadata = {**dict(target.metadata), "snap_kind": SnapKind.EDGE.value, "parent_curve_id": str(target.id), "curve_type": "arc", "arc_t": t}
    return [
        SnapResult(
            True,
            point,
            target.source,
            source_id=str(target.id),
            distance_px=dist,
            priority=int(target.priority),
            metadata=metadata,
            kind=target.kind or SnapKind.EDGE,
        )
    ]


def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if not callable(increment):
        return
    try:
        increment(str(name), int(value))
    except Exception:
        pass


def _set_perf_value(ctx: Any, name: str, value: Any) -> None:
    profiler = getattr(ctx, "profiler", None)
    setter = getattr(profiler, "set_value", None)
    if not callable(setter):
        return
    try:
        setter(str(name), value)
    except Exception:
        pass


def _measure_perf(ctx: Any, name: str) -> Any:
    profiler = getattr(ctx, "profiler", None)
    measure = getattr(profiler, "measure", None)
    if callable(measure):
        try:
            return measure(str(name))
        except Exception:
            pass
    return nullcontext()


def _curve_intersection_results(
    segments: tuple["_SegmentCandidate", ...],
    circles: tuple["_CircleCandidate", ...],
    arcs: tuple["_ArcCandidate", ...],
    screen_pos: Point2,
    ctx: Any,
) -> list[SnapResult]:
    if not (segments and (circles or arcs)) and len(circles) < 2 and not (circles and arcs) and len(arcs) < 2:
        return []
    results: list[SnapResult] = []
    emitted: list[Point3] = []

    def emit(point: Point3, source_id: str, priority: int, radius: float, metadata: dict[str, Any]) -> None:
        if any(_distance3(point, existing) <= 1.0e-7 for existing in emitted):
            return
        dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
        if dist > radius:
            return
        emitted.append(point)
        results.append(
            SnapResult(
                True,
                point,
                SnapSource.INTERSECTION,
                source_id=source_id,
                distance_px=dist,
                priority=max(0, int(priority) - 25),
                metadata={**metadata, "snap_kind": SnapKind.INTERSECTION.value},
                kind=SnapKind.INTERSECTION,
            )
        )

    for segment in segments:
        if not bool(segment.metadata.get("include_intersection_snap", True)):
            continue
        a2 = point3_to_xy(segment.start)
        b2 = point3_to_xy(segment.end)
        for circle in circles:
            if not bool(circle.metadata.get("include_intersection_snap", True)):
                continue
            radius = min(_intersection_radius(segment.radius_px, segment.metadata), _intersection_radius(circle.radius_px, circle.metadata))
            for point2, t in line_circle_intersections(a2, b2, circle.circle, tolerance=1.0e-7):
                if not (1.0e-8 < t < 1.0 - 1.0e-8):
                    continue
                emit(_segment_point_at(segment.start, segment.end, t), f"{segment.id}&{circle.id}:intersection", min(segment.priority, circle.priority), radius, {"source_ids": (segment.id, circle.id), "intersection_type": "line_circle"})
        for arc in arcs:
            if not bool(arc.metadata.get("include_intersection_snap", True)):
                continue
            radius = min(_intersection_radius(segment.radius_px, segment.metadata), _intersection_radius(arc.radius_px, arc.metadata))
            for point2, t_line, t_arc in line_arc_intersections(a2, b2, arc.arc, tolerance=1.0e-7):
                if not (1.0e-8 < t_line < 1.0 - 1.0e-8 and 1.0e-8 < t_arc < 1.0 - 1.0e-8):
                    continue
                emit(_segment_point_at(segment.start, segment.end, t_line), f"{segment.id}&{arc.id}:intersection", min(segment.priority, arc.priority), radius, {"source_ids": (segment.id, arc.id), "intersection_type": "line_arc", "arc_t": t_arc})

    for index, first in enumerate(circles):
        if not bool(first.metadata.get("include_intersection_snap", True)):
            continue
        for second in circles[index + 1 :]:
            if not bool(second.metadata.get("include_intersection_snap", True)):
                continue
            radius = min(_intersection_radius(first.radius_px, first.metadata), _intersection_radius(second.radius_px, second.metadata))
            for point2 in circle_circle_intersections(first.circle, second.circle, tolerance=1.0e-7):
                z = (first.z + second.z) * 0.5
                emit((point2[0], point2[1], z), f"{first.id}&{second.id}:intersection", min(first.priority, second.priority), radius, {"source_ids": (first.id, second.id), "intersection_type": "circle_circle"})
        for arc in arcs:
            if not bool(arc.metadata.get("include_intersection_snap", True)):
                continue
            radius = min(_intersection_radius(first.radius_px, first.metadata), _intersection_radius(arc.radius_px, arc.metadata))
            for point2, t_arc in circle_arc_intersections(first.circle, arc.arc, tolerance=1.0e-7):
                if not (1.0e-8 < t_arc < 1.0 - 1.0e-8):
                    continue
                emit(_arc_point_at(arc, t_arc), f"{first.id}&{arc.id}:intersection", min(first.priority, arc.priority), radius, {"source_ids": (first.id, arc.id), "intersection_type": "circle_arc", "arc_t": t_arc})

    for index, first in enumerate(arcs):
        if not bool(first.metadata.get("include_intersection_snap", True)):
            continue
        for second in arcs[index + 1 :]:
            if not bool(second.metadata.get("include_intersection_snap", True)):
                continue
            radius = min(_intersection_radius(first.radius_px, first.metadata), _intersection_radius(second.radius_px, second.metadata))
            for point2, t_first, t_second in arc_arc_intersections(first.arc, second.arc, tolerance=1.0e-7):
                if not (1.0e-8 < t_first < 1.0 - 1.0e-8 and 1.0e-8 < t_second < 1.0 - 1.0e-8):
                    continue
                p1 = _arc_point_at(first, t_first)
                p2 = _arc_point_at(second, t_second)
                point = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5, (p1[2] + p2[2]) * 0.5)
                emit(point, f"{first.id}&{second.id}:intersection", min(first.priority, second.priority), radius, {"source_ids": (first.id, second.id), "intersection_type": "arc_arc", "t_values": (t_first, t_second)})
    return results



def _angle_snap_values(metadata: dict[str, Any]) -> tuple[float, ...]:
    explicit = metadata.get("angle_degrees") or metadata.get("snap_angles_degrees")
    values: list[float] = []
    if explicit is not None:
        if isinstance(explicit, (int, float)):
            values.append(float(explicit))
        else:
            try:
                values.extend(float(value) for value in explicit)
            except TypeError:
                pass
    include_step = bool(metadata.get("include_angle_snap", False))
    step = float(metadata.get("angle_step_degrees", 0.0) or 0.0)
    if include_step and isfinite(step) and 0.0 < abs(step) <= 180.0:
        current = 0.0
        guard = 0
        while current < 360.0 - 1.0e-9 and guard < 720:
            values.append(current)
            current += abs(step)
            guard += 1
    seen: set[float] = set()
    ordered: list[float] = []
    for value in values:
        normalized = round(_normalize_angle_degrees(value), 9)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _normalize_angle_degrees(value: float) -> float:
    normalized = float(value) % 360.0
    return 0.0 if abs(normalized - 360.0) <= 1.0e-9 else normalized


def _angle_id(angle: float) -> str:
    rounded = round(float(angle), 6)
    if abs(rounded - round(rounded)) <= 1.0e-9:
        return str(int(round(rounded)))
    return (f"{rounded:.6f}".rstrip("0").rstrip(".")).replace("-", "m").replace(".", "p")


def _circle_basis(target: SnapTarget) -> tuple[Point3, Point3]:
    u = _normalize3(target.basis_u or _metadata_vec3(target.metadata, "basis_u") or (1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    raw_v = _metadata_vec3(target.metadata, "basis_v") or target.basis_v or (0.0, 1.0, 0.0)
    dot_uv = _dot3(u, raw_v)
    v_ortho = (float(raw_v[0]) - dot_uv * u[0], float(raw_v[1]) - dot_uv * u[1], float(raw_v[2]) - dot_uv * u[2])
    v = _normalize3(v_ortho, (0.0, 1.0, 0.0))
    if abs(_dot3(u, v)) > 1.0e-6:
        v = (0.0, 1.0, 0.0) if abs(u[1]) < 0.9 else (1.0, 0.0, 0.0)
        dot_uv = _dot3(u, v)
        v = _normalize3((v[0] - dot_uv * u[0], v[1] - dot_uv * u[1], v[2] - dot_uv * u[2]), (0.0, 1.0, 0.0))
    return u, v


def _metadata_vec3(metadata: dict[str, Any], key: str) -> Point3 | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return None


def _dot3(a: Point3, b: Point3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _normalize3(value: Point3, fallback: Point3) -> Point3:
    length = sqrt(max(_dot3(value, value), 0.0))
    if not isfinite(length) or length <= 1.0e-12:
        return fallback
    return (float(value[0]) / length, float(value[1]) / length, float(value[2]) / length)


def _point_on_circle(center: Point3, radius: float, basis_u: Point3, basis_v: Point3, angle_degrees: float) -> Point3:
    angle = radians(float(angle_degrees))
    ca = cos(angle)
    sa = sin(angle)
    return (
        float(center[0]) + float(radius) * (ca * basis_u[0] + sa * basis_v[0]),
        float(center[1]) + float(radius) * (ca * basis_u[1] + sa * basis_v[1]),
        float(center[2]) + float(radius) * (ca * basis_u[2] + sa * basis_v[2]),
    )


def closest_point_on_circle_3d(p: Point3, center: Point3, radius: float, basis_u: Point3, basis_v: Point3) -> Point3:
    rel = (float(p[0]) - float(center[0]), float(p[1]) - float(center[1]), float(p[2]) - float(center[2]))
    u = _dot3(rel, basis_u)
    v = _dot3(rel, basis_v)
    length = sqrt(u * u + v * v)
    if length <= 1.0e-12:
        return _point_on_circle(center, radius, basis_u, basis_v, 0.0)
    return (
        float(center[0]) + float(radius) * (u / length * basis_u[0] + v / length * basis_v[0]),
        float(center[1]) + float(radius) * (u / length * basis_u[1] + v / length * basis_v[1]),
        float(center[2]) + float(radius) * (u / length * basis_u[2] + v / length * basis_v[2]),
    )




@dataclass(frozen=True, slots=True)
class _CircleCandidate:
    id: str
    source: SnapSource
    circle: Circle2
    z: float
    radius_px: float
    priority: int
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ArcCandidate:
    id: str
    source: SnapSource
    arc: Arc2
    start: Point3
    end: Point3
    control: Point3
    radius_px: float
    priority: int
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _SegmentCandidate:
    id: str
    source: SnapSource
    start: Point3
    end: Point3
    radius_px: float
    priority: int
    metadata: dict[str, Any]


def _segment_intersection_results(segments: tuple[_SegmentCandidate, ...], screen_pos: Point2, ctx: Any) -> list[SnapResult]:
    """Return semantic line-line intersection snap candidates.

    The calculation is intentionally local to the pointer: only segments whose
    screen-space bounding box touches the snap radius are paired.  This keeps the
    API-side richness cheap enough for dense scene caches and lets tools benefit
    without implementing their own geometry filters.
    """

    if len(segments) < 2:
        return []
    near: list[_SegmentCandidate] = []
    for segment in segments:
        if not bool(segment.metadata.get("include_intersection_snap", True)):
            continue
        radius = float(segment.metadata.get("intersection_radius_px", min(segment.radius_px, 12.0)))
        start_screen = _world_to_screen_cached(ctx, segment.start, segment.metadata, "snap_start_screen")
        end_screen = _world_to_screen_cached(ctx, segment.end, segment.metadata, "snap_end_screen")
        if _screen_bbox_contains(screen_pos, start_screen, end_screen, radius):
            near.append(segment)
    if len(near) < 2:
        return []

    results: list[SnapResult] = []
    emitted: set[tuple[str, str]] = set()
    for index, first in enumerate(near):
        for second in near[index + 1 :]:
            key = tuple(sorted((first.id, second.id)))
            if key in emitted:
                continue
            emitted.add(key)
            intersection = _segment_intersection_xy(first.start, first.end, second.start, second.end)
            if intersection is None:
                continue
            point, t_first, t_second = intersection
            # Endpoint hits are better represented as VERTEX snap targets.  Keep
            # INTERSECTION reserved for true crossing geometry so priority remains
            # predictable instead of competing with existing vertices.
            if not (1.0e-9 < t_first < 1.0 - 1.0e-9 and 1.0e-9 < t_second < 1.0 - 1.0e-9):
                continue
            dist = screen_distance(_world_to_screen(ctx, point), screen_pos)
            radius = min(
                float(first.metadata.get("intersection_radius_px", min(first.radius_px, 12.0))),
                float(second.metadata.get("intersection_radius_px", min(second.radius_px, 12.0))),
            )
            if dist > radius:
                continue
            metadata = {
                "snap_kind": SnapKind.INTERSECTION.value,
                "segments": (first.id, second.id),
                "t_values": (t_first, t_second),
                "source_ids": (first.id, second.id),
            }
            priority = max(0, min(int(first.priority), int(second.priority)) - 20)
            results.append(
                SnapResult(
                    True,
                    point,
                    SnapSource.INTERSECTION,
                    source_id=f"{first.id}&{second.id}:intersection",
                    distance_px=dist,
                    priority=priority,
                    metadata=metadata,
                    kind=SnapKind.INTERSECTION,
                )
            )
    return results


def _screen_bbox_contains(point: Point2, a: Point2, b: Point2, margin: float) -> bool:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    return min(ax, bx) - margin <= px <= max(ax, bx) + margin and min(ay, by) - margin <= py <= max(ay, by) + margin


def _segment_intersection_xy(a: Point3, b: Point3, c: Point3, d: Point3) -> tuple[Point3, float, float] | None:
    ax, ay, az = float(a[0]), float(a[1]), float(a[2])
    bx, by, bz = float(b[0]), float(b[1]), float(b[2])
    cx, cy, cz = float(c[0]), float(c[1]), float(c[2])
    dx, dy, dz = float(d[0]), float(d[1]), float(d[2])
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    denom = rx * sy - ry * sx
    if abs(denom) <= 1.0e-12:
        return None
    qpx, qpy = cx - ax, cy - ay
    t = (qpx * sy - qpy * sx) / denom
    u = (qpx * ry - qpy * rx) / denom
    if t < -1.0e-9 or t > 1.0 + 1.0e-9 or u < -1.0e-9 or u > 1.0 + 1.0e-9:
        return None
    t_clamped = max(0.0, min(1.0, t))
    u_clamped = max(0.0, min(1.0, u))
    point = (ax + rx * t_clamped, ay + ry * t_clamped, (az + (bz - az) * t_clamped + cz + (dz - cz) * u_clamped) * 0.5)
    return point, t_clamped, u_clamped



def _circle_candidate_from_target(target: SnapTarget) -> _CircleCandidate | None:
    if target.center is None or target.radius is None or float(target.radius) <= 0.0:
        return None
    return _CircleCandidate(
        id=str(target.id),
        source=target.source,
        circle=Circle2(point3_to_xy(target.center), float(target.radius)),
        z=float(target.center[2]),
        radius_px=float(target.radius_px),
        priority=int(target.priority),
        metadata=dict(target.metadata),
    )


def _arc_candidate_from_target(target: SnapTarget) -> _ArcCandidate | None:
    if target.start is None or target.end is None or target.control is None:
        return None
    arc = arc_from_three_points(point3_to_xy(target.start), point3_to_xy(target.end), point3_to_xy(target.control))
    if arc is None:
        return None
    return _ArcCandidate(
        id=str(target.id),
        source=target.source,
        arc=arc,
        start=target.start,
        end=target.end,
        control=target.control,
        radius_px=float(target.radius_px),
        priority=int(target.priority),
        metadata=dict(target.metadata),
    )


def _closest_point_on_arc_candidate(p: Point3, arc: _ArcCandidate) -> tuple[Point3, float]:
    angle = atan2(float(p[1]) - arc.arc.center[1], float(p[0]) - arc.arc.center[0])
    t = arc.arc.parameter_for_angle(angle)
    if t is None:
        start_dist = _distance2(point3_to_xy(p), point3_to_xy(arc.start))
        end_dist = _distance2(point3_to_xy(p), point3_to_xy(arc.end))
        t = 0.0 if start_dist <= end_dist else 1.0
    return _arc_point_at(arc, t), t


def _arc_point_at(arc: _ArcCandidate, t: float) -> Point3:
    point2 = arc.arc.point_at(t)
    z = float(arc.start[2]) + (float(arc.end[2]) - float(arc.start[2])) * max(0.0, min(1.0, float(t)))
    return (point2[0], point2[1], z)


def _segment_point_at(start: Point3, end: Point3, t: float) -> Point3:
    tt = max(0.0, min(1.0, float(t)))
    return (
        float(start[0]) + (float(end[0]) - float(start[0])) * tt,
        float(start[1]) + (float(end[1]) - float(start[1])) * tt,
        float(start[2]) + (float(end[2]) - float(start[2])) * tt,
    )


def _intersection_radius(radius_px: float, metadata: dict[str, Any]) -> float:
    return float(metadata.get("intersection_radius_px", min(float(radius_px), 12.0)))


def _distance3(a: Point3, b: Point3) -> float:
    return sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2 + (float(a[2]) - float(b[2])) ** 2)


def _distance2(a: Point2, b: Point2) -> float:
    return sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def _segment_parameter_3d(p: Point3, a: Point3, b: Point3) -> float:
    ax, ay, az = float(a[0]), float(a[1]), float(a[2])
    bx, by, bz = float(b[0]), float(b[1]), float(b[2])
    px, py, pz = float(p[0]), float(p[1]), float(p[2])
    abx, aby, abz = bx - ax, by - ay, bz - az
    denom = abx * abx + aby * aby + abz * abz
    if denom <= 1.0e-12:
        return 0.0
    return max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby + (pz - az) * abz) / denom))


def closest_point_on_segment_3d(p: Point3, a: Point3, b: Point3) -> Point3:
    ax, ay, az = a
    bx, by, bz = b
    px, py, pz = p
    ab = (bx - ax, by - ay, bz - az)
    ap = (px - ax, py - ay, pz - az)
    denom = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2]
    if denom <= 1e-12:
        return a
    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / denom))
    return (ax + ab[0] * t, ay + ab[1] * t, az + ab[2] * t)


def midpoint_on_segment_3d(a: Point3, b: Point3) -> Point3:
    return ((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5, (float(a[2]) + float(b[2])) * 0.5)
