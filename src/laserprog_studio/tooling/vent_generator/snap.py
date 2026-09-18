# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from laserprog_studio.planar_tools import VentPathDraft, plane_to_world

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]

# Vent routing must stay easy to move freely: snaps are suggestions, not magnets.
# The world-space tolerance is used by the legacy Qt planar path; the pixel
# radii are used by the Creator/Plan2D API path.
VENT_ROUTE_SNAP_TOLERANCE = 1.5
VENT_ROUTE_API_SNAP_RADIUS_PX = 5.0
VENT_ROUTE_ALIGNMENT_RADIUS_PX = 4.0


@dataclass(frozen=True, slots=True)
class VentRouteSnapResult:
    """Result of the Vent Generator routing smart snap.

    Vent routing deliberately does **not** snap directly to the existing route
    waypoints/segments.  Existing waypoints are used only as alignment guides so
    the path stays readable instead of collapsing onto itself.  Real snap targets
    come from scene geometry supplied by the caller/API.
    """

    point: Vec2
    snapped: bool = False
    label: str | None = None
    kind: str = "free"
    source_id: str | None = None


def _distance(a: Vec2, b: Vec2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _as_vec2(value: Any) -> Vec2 | None:
    try:
        return (float(value[0]), float(value[1]))
    except Exception:
        return None


def _nearest_on_segment(point: Vec2, a: Vec2, b: Vec2) -> tuple[Vec2, float] | None:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 <= 1.0e-12 or not math.isfinite(length2):
        return None
    t = ((px - ax) * vx + (py - ay) * vy) / length2
    if t <= 1.0e-5 or t >= 1.0 - 1.0e-5:
        return None
    t = max(0.0, min(1.0, t))
    return (ax + vx * t, ay + vy * t), t


def _line_intersection(a: Vec2, b: Vec2, c: Vec2, d: Vec2, *, eps: float = 1.0e-9) -> Vec2 | None:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    dx, dy = float(d[0]), float(d[1])
    r_x, r_y = bx - ax, by - ay
    s_x, s_y = dx - cx, dy - cy
    denom = r_x * s_y - r_y * s_x
    if abs(denom) <= float(eps):
        return None
    qpx, qpy = cx - ax, cy - ay
    t = (qpx * s_y - qpy * s_x) / denom
    u = (qpx * r_y - qpy * r_x) / denom
    if -eps <= t <= 1.0 + eps and -eps <= u <= 1.0 + eps:
        return (ax + t * r_x, ay + t * r_y)
    return None


def _route_points(payload: VentPathDraft) -> list[Vec2]:
    return [(float(u), float(v)) for u, v in (getattr(payload, "waypoints", []) or [])]


def _near_any_route_point(point: Vec2, waypoints: Iterable[Vec2], *, tolerance: float = 1.0e-6) -> bool:
    return any(_distance(point, route_point) <= float(tolerance) for route_point in waypoints)


def _choose_best(candidates: list[tuple[int, float, Vec2, str, str, str]]) -> VentRouteSnapResult | None:
    if not candidates:
        return None
    _priority, _dist, point, label, kind, source_id = min(candidates, key=lambda item: (int(item[0]), float(item[1])))
    return VentRouteSnapResult(point=point, snapped=True, label=label, kind=kind, source_id=source_id)


def _route_alignment_candidates(raw: Vec2, waypoints: list[Vec2], *, excluded: set[int], tolerance: float) -> list[tuple[int, float, Vec2, str, str, str]]:
    candidates: list[tuple[int, float, Vec2, str, str, str]] = []
    best_u: tuple[float, float, int] | None = None
    best_v: tuple[float, float, int] | None = None
    raw_u, raw_v = float(raw[0]), float(raw[1])

    for index, point in enumerate(waypoints):
        if int(index) in excluded:
            continue
        u, v = float(point[0]), float(point[1])
        du = abs(u - raw_u)
        dv = abs(v - raw_v)
        if du <= tolerance and (best_u is None or du < best_u[0]):
            best_u = (du, u, index)
        if dv <= tolerance and (best_v is None or dv < best_v[0]):
            best_v = (dv, v, index)

    if best_u is not None and best_v is not None and best_u[2] != best_v[2]:
        point = (float(best_u[1]), float(best_v[1]))
        dist = _distance(raw, point)
        if dist <= tolerance and not _near_any_route_point(point, waypoints):
            candidates.append((36, dist, point, "Align U+V", "alignment", f"vent.generator.route.align.cross.{best_u[2]:02d}.{best_v[2]:02d}"))

    if best_u is not None:
        point = (float(best_u[1]), raw_v)
        if not _near_any_route_point(point, waypoints):
            candidates.append((42, float(best_u[0]), point, "Align vertical", "alignment", f"vent.generator.route.align.u.{best_u[2]:02d}"))
    if best_v is not None:
        point = (raw_u, float(best_v[1]))
        if not _near_any_route_point(point, waypoints):
            candidates.append((42, float(best_v[0]), point, "Align horizontal", "alignment", f"vent.generator.route.align.v.{best_v[2]:02d}"))
    return candidates


def _scene_candidates(
    raw: Vec2,
    *,
    scene_points: Iterable[Vec2] = (),
    scene_segments: Iterable[tuple[Vec2, Vec2]] = (),
    tolerance: float,
) -> list[tuple[int, float, Vec2, str, str, str]]:
    candidates: list[tuple[int, float, Vec2, str, str, str]] = []
    tol = float(tolerance)
    for index, point in enumerate(scene_points or ()):  # real scene points are allowed snap targets.
        p = _as_vec2(point)
        if p is None:
            continue
        dist = _distance(raw, p)
        if dist <= tol:
            candidates.append((10, dist, p, "Scene vertex", "scene_vertex", f"scene.point.{index:03d}"))

    for index, segment in enumerate(scene_segments or ()):  # edge midpoint and body snap, not route segments.
        try:
            a = _as_vec2(segment[0])
            b = _as_vec2(segment[1])
        except Exception:
            a = b = None
        if a is None or b is None:
            continue
        midpoint = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
        midpoint_dist = _distance(raw, midpoint)
        if midpoint_dist <= tol:
            candidates.append((20, midpoint_dist, midpoint, "Scene midpoint", "scene_midpoint", f"scene.edge.{index:03d}:midpoint"))
        hit = _nearest_on_segment(raw, a, b)
        if hit is None:
            continue
        projected, _t = hit
        dist = _distance(raw, projected)
        if dist <= tol:
            candidates.append((30, dist, projected, "Scene edge", "scene_edge", f"scene.edge.{index:03d}"))
    return candidates


def _alignment_scene_intersection_candidates(
    raw: Vec2,
    waypoints: list[Vec2],
    *,
    excluded: set[int],
    scene_segments: Iterable[tuple[Vec2, Vec2]],
    tolerance: float,
) -> list[tuple[int, float, Vec2, str, str, str]]:
    candidates: list[tuple[int, float, Vec2, str, str, str]] = []
    tol = float(tolerance)
    if not waypoints:
        return candidates
    span = max(1000.0, tol * 200.0)
    for wp_index, waypoint in enumerate(waypoints):
        if int(wp_index) in excluded:
            continue
        u, v = float(waypoint[0]), float(waypoint[1])
        guide_segments = (
            ("vertical", (u, raw[1] - span), (u, raw[1] + span)),
            ("horizontal", (raw[0] - span, v), (raw[0] + span, v)),
        )
        for seg_index, segment in enumerate(scene_segments or ()):  # intersections between route guides and real scene edges.
            try:
                a = _as_vec2(segment[0])
                b = _as_vec2(segment[1])
            except Exception:
                a = b = None
            if a is None or b is None:
                continue
            for axis, start, end in guide_segments:
                hit = _line_intersection(start, end, a, b)
                if hit is None:
                    continue
                dist = _distance(raw, hit)
                if dist <= tol:
                    candidates.append((15, dist, hit, f"Scene × {axis} align", "intersection", f"scene.edge.{seg_index:03d}&vent.align.{wp_index:02d}"))
    return candidates


def _angle_step_candidate(raw: Vec2, anchor: Vec2 | None, *, tolerance: float, angle_step_degrees: float) -> tuple[int, float, Vec2, str, str, str] | None:
    if anchor is None:
        return None
    step = abs(float(angle_step_degrees))
    if step <= 0.0 or step > 180.0:
        return None
    ax, ay = float(anchor[0]), float(anchor[1])
    dx, dy = float(raw[0]) - ax, float(raw[1]) - ay
    length = math.hypot(dx, dy)
    if length <= 1.0e-7:
        return None
    step_rad = math.radians(step)
    snapped_angle = round(math.atan2(dy, dx) / step_rad) * step_rad
    projected = (ax + math.cos(snapped_angle) * length, ay + math.sin(snapped_angle) * length)
    dist = _distance(raw, projected)
    if dist <= float(tolerance):
        return (55, dist, projected, f"Angle {step:g}°", "angle", "vent.generator.route.angle")
    return None


def _anchor_for_payload(payload: VentPathDraft, *, selected_index: int | None = None) -> Vec2 | None:
    waypoints = _route_points(payload)
    if selected_index is not None and 0 <= int(selected_index) < len(waypoints):
        idx = int(selected_index)
        if idx > 0:
            return waypoints[idx - 1]
        if len(waypoints) > 1:
            return waypoints[1]
        return None
    if waypoints:
        return waypoints[-1]
    return None


def snap_vent_route_point(
    payload: VentPathDraft,
    candidate: Vec2,
    *,
    enabled: bool = True,
    exclude_indices: Iterable[int] = (),
    tolerance: float = VENT_ROUTE_SNAP_TOLERANCE,
    scene_points: Iterable[Vec2] = (),
    scene_segments: Iterable[tuple[Vec2, Vec2]] = (),
    anchor: Vec2 | None = None,
    angle_step_degrees: float | None = None,
) -> VentRouteSnapResult:
    """Snap a Vent route edit using routing-safe targets.

    Allowed targets:
    - scene vertices/edges/midpoints provided by the caller/API;
    - intersections between scene edges and route alignment guides;
    - horizontal/vertical alignment with other route waypoints;
    - optional angle-step guide from the current route anchor.

    Forbidden targets:
    - direct snap on existing Vent waypoints;
    - direct snap on Vent route segments or their midpoints;
    - generated Vent preview geometry.
    """

    raw = (float(candidate[0]), float(candidate[1]))
    if not bool(enabled):
        return VentRouteSnapResult(raw)
    try:
        tol = max(float(tolerance), 0.0)
    except Exception:
        tol = 6.0
    if tol <= 0.0:
        return VentRouteSnapResult(raw)

    excluded = {int(value) for value in exclude_indices}
    waypoints = _route_points(payload)
    scene_segments_tuple = tuple(scene_segments or ())
    candidates: list[tuple[int, float, Vec2, str, str, str]] = []
    candidates.extend(_scene_candidates(raw, scene_points=scene_points, scene_segments=scene_segments_tuple, tolerance=tol))
    candidates.extend(_alignment_scene_intersection_candidates(raw, waypoints, excluded=excluded, scene_segments=scene_segments_tuple, tolerance=tol))
    candidates.extend(_route_alignment_candidates(raw, waypoints, excluded=excluded, tolerance=tol))

    if angle_step_degrees is not None:
        angle_anchor = anchor if anchor is not None else _anchor_for_payload(payload, selected_index=next(iter(excluded), None))
        angle_candidate = _angle_step_candidate(raw, angle_anchor, tolerance=tol, angle_step_degrees=float(angle_step_degrees))
        if angle_candidate is not None and not _near_any_route_point(angle_candidate[2], waypoints):
            candidates.append(angle_candidate)

    best = _choose_best(candidates)
    return best if best is not None else VentRouteSnapResult(raw)


def vent_route_alignment_targets(
    payload: VentPathDraft,
    candidate: Vec2,
    *,
    exclude_indices: Iterable[int] = (),
    tolerance: float = VENT_ROUTE_SNAP_TOLERANCE,
    owner_tool: str = "vent_generator",
) -> tuple[Any, ...]:
    """Return API SnapTargets for route alignment guides only.

    These are finite guide segments centred around the current pointer so the
    public snap API can do fast closest-point and scene/intersection snapping
    without treating route waypoints as direct point targets.
    """

    try:
        from laserprog_studio.tool_api import snap as snap_api
    except Exception:  # pragma: no cover - API unavailable in very old hosts.
        return ()

    waypoints = _route_points(payload)
    if not waypoints:
        return ()
    excluded = {int(value) for value in exclude_indices}
    raw_u, raw_v = float(candidate[0]), float(candidate[1])
    us = [raw_u, *(point[0] for point in waypoints)]
    vs = [raw_v, *(point[1] for point in waypoints)]
    extent = max(max(us) - min(us), max(vs) - min(vs), float(tolerance) * 24.0, 250.0) + float(tolerance) * 4.0
    targets: list[Any] = []
    for index, (u, v) in enumerate(waypoints):
        if int(index) in excluded:
            continue
        metadata_base = {
            "owner_tool": str(owner_tool),
            "vent_generator_snap_role": "alignment_guide",
            "include_midpoint_snap": False,
            "include_intersection_snap": True,
        }
        targets.append(
            snap_api.segment(
                f"vent.generator.snap.align.u.{index:02d}",
                plane_to_world(payload.plane, float(u), raw_v - extent),
                plane_to_world(payload.plane, float(u), raw_v + extent),
                source=snap_api.SnapSource.CUSTOM_EDGE,
                radius_px=VENT_ROUTE_ALIGNMENT_RADIUS_PX,
                priority=42,
                metadata={**metadata_base, "snap_label": "Align vertical", "axis": "u", "waypoint_index": index},
                kind=snap_api.SnapKind.EDGE,
            )
        )
        targets.append(
            snap_api.segment(
                f"vent.generator.snap.align.v.{index:02d}",
                plane_to_world(payload.plane, raw_u - extent, float(v)),
                plane_to_world(payload.plane, raw_u + extent, float(v)),
                source=snap_api.SnapSource.CUSTOM_EDGE,
                radius_px=VENT_ROUTE_ALIGNMENT_RADIUS_PX,
                priority=42,
                metadata={**metadata_base, "snap_label": "Align horizontal", "axis": "v", "waypoint_index": index},
                kind=snap_api.SnapKind.EDGE,
            )
        )
    return tuple(targets)


__all__ = [
    "VENT_ROUTE_ALIGNMENT_RADIUS_PX",
    "VENT_ROUTE_API_SNAP_RADIUS_PX",
    "VENT_ROUTE_SNAP_TOLERANCE",
    "VentRouteSnapResult",
    "snap_vent_route_point",
    "vent_route_alignment_targets",
]
