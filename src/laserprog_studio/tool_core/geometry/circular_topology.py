"""Exact 2D circle/arc topology helpers.

The sketch compiler and snap API use this module for curve intersections and
splitting.  Keeping it separate avoids turning either the public API facade or
the Plan Tracer tool into a geometry monolith.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

Point2 = tuple[float, float]

TAU = math.tau
EPS = 1.0e-10


@dataclass(frozen=True, slots=True)
class Circle2:
    center: Point2
    radius: float


@dataclass(frozen=True, slots=True)
class Arc2:
    center: Point2
    radius: float
    start_angle: float
    sweep_angle: float

    @property
    def end_angle(self) -> float:
        return self.start_angle + self.sweep_angle

    def point_at(self, t: float) -> Point2:
        angle = self.start_angle + self.sweep_angle * max(0.0, min(1.0, float(t)))
        return point_on_circle(self.center, self.radius, angle)

    def contains_angle(self, angle: float, *, tolerance: float = 1.0e-8) -> bool:
        return angle_on_arc(angle, self.start_angle, self.sweep_angle, tolerance=tolerance)

    def parameter_for_angle(self, angle: float) -> float | None:
        if abs(self.sweep_angle) <= EPS:
            return None
        if self.sweep_angle >= 0.0:
            delta = _ccw_delta(self.start_angle, angle)
            if delta > self.sweep_angle + 1.0e-8:
                return None
            return max(0.0, min(1.0, delta / self.sweep_angle))
        delta = _ccw_delta(angle, self.start_angle)
        if delta > abs(self.sweep_angle) + 1.0e-8:
            return None
        return max(0.0, min(1.0, delta / abs(self.sweep_angle)))

    def parameter_for_point(self, point: Point2, *, tolerance: float = 1.0e-5) -> float | None:
        if abs(distance(point, self.center) - self.radius) > tolerance:
            return None
        return self.parameter_for_angle(angle_of(self.center, point))


def distance(a: Point2, b: Point2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def angle_of(center: Point2, point: Point2) -> float:
    return math.atan2(float(point[1]) - float(center[1]), float(point[0]) - float(center[0]))


def normalize_angle(angle: float) -> float:
    value = float(angle) % TAU
    return 0.0 if abs(value - TAU) <= EPS else value


def point_on_circle(center: Point2, radius: float, angle: float) -> Point2:
    return (float(center[0]) + float(radius) * math.cos(float(angle)), float(center[1]) + float(radius) * math.sin(float(angle)))


def circle_from_two_points(center: Point2, radius_point: Point2, *, min_radius: float = 1.0e-10) -> Circle2 | None:
    radius = distance(center, radius_point)
    if not math.isfinite(radius) or radius <= min_radius:
        return None
    return Circle2((float(center[0]), float(center[1])), radius)


def arc_from_three_points(start: Point2, end: Point2, control: Point2, *, min_radius: float = 1.0e-10) -> Arc2 | None:
    circle = circle_through_three_points(start, control, end, min_radius=min_radius)
    if circle is None:
        return None
    a0 = angle_of(circle.center, start)
    a1 = angle_of(circle.center, end)
    ac = angle_of(circle.center, control)
    ccw = _ccw_delta(a0, a1)
    contains_control_ccw = _ccw_delta(a0, ac) <= ccw + 1.0e-8
    sweep = ccw if contains_control_ccw else -_ccw_delta(a1, a0)
    if abs(sweep) <= EPS:
        return None
    return Arc2(circle.center, circle.radius, a0, sweep)


def circle_through_three_points(a: Point2, b: Point2, c: Point2, *, min_radius: float = 1.0e-10) -> Circle2 | None:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    det = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(det) <= 1.0e-12:
        return None
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ox = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / det
    oy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / det
    radius = math.hypot(ax - ox, ay - oy)
    if not math.isfinite(radius) or radius <= min_radius:
        return None
    return Circle2((ox, oy), radius)


def angle_on_arc(angle: float, start_angle: float, sweep_angle: float, *, tolerance: float = 1.0e-8) -> bool:
    if abs(sweep_angle) >= TAU - tolerance:
        return True
    if sweep_angle >= 0.0:
        return _ccw_delta(start_angle, angle) <= sweep_angle + tolerance
    return _ccw_delta(angle, start_angle) <= abs(sweep_angle) + tolerance


def control_point_for_arc_segment(arc: Arc2, t0: float, t1: float) -> Point2:
    return arc.point_at((float(t0) + float(t1)) * 0.5)


def line_circle_intersections(a: Point2, b: Point2, circle: Circle2, *, segment: bool = True, tolerance: float = 1.0e-9) -> list[tuple[Point2, float]]:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = circle.center
    dx, dy = bx - ax, by - ay
    fx, fy = ax - cx, ay - cy
    aa = dx * dx + dy * dy
    if aa <= EPS:
        return []
    bb = 2.0 * (fx * dx + fy * dy)
    cc = fx * fx + fy * fy - circle.radius * circle.radius
    disc = bb * bb - 4.0 * aa * cc
    if disc < -tolerance:
        return []
    if abs(disc) <= tolerance:
        ts = [(-bb) / (2.0 * aa)]
    else:
        root = math.sqrt(max(0.0, disc))
        ts = [(-bb - root) / (2.0 * aa), (-bb + root) / (2.0 * aa)]
    hits: list[tuple[Point2, float]] = []
    seen: set[tuple[int, int]] = set()
    for t in ts:
        if segment and (t < -tolerance or t > 1.0 + tolerance):
            continue
        tt = max(0.0, min(1.0, t)) if segment else t
        point = (ax + dx * tt, ay + dy * tt)
        key = (round(point[0], 9), round(point[1], 9))
        if key in seen:
            continue
        seen.add(key)
        hits.append((point, tt))
    return hits


def line_arc_intersections(a: Point2, b: Point2, arc: Arc2, *, segment: bool = True, tolerance: float = 1.0e-7) -> list[tuple[Point2, float, float]]:
    hits: list[tuple[Point2, float, float]] = []
    circle = Circle2(arc.center, arc.radius)
    for point, line_t in line_circle_intersections(a, b, circle, segment=segment, tolerance=tolerance):
        arc_t = arc.parameter_for_point(point, tolerance=tolerance)
        if arc_t is not None:
            hits.append((point, line_t, arc_t))
    return hits


def circle_circle_intersections(first: Circle2, second: Circle2, *, tolerance: float = 1.0e-9) -> list[Point2]:
    x0, y0 = first.center
    x1, y1 = second.center
    r0, r1 = float(first.radius), float(second.radius)
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    if d <= tolerance or d > r0 + r1 + tolerance or d < abs(r0 - r1) - tolerance:
        return []
    if d <= EPS:
        return []
    a = (r0 * r0 - r1 * r1 + d * d) / (2.0 * d)
    h2 = r0 * r0 - a * a
    if h2 < -tolerance:
        return []
    h = math.sqrt(max(0.0, h2))
    xm = x0 + a * dx / d
    ym = y0 + a * dy / d
    rx = -dy * h / d
    ry = dx * h / d
    p1 = (xm + rx, ym + ry)
    p2 = (xm - rx, ym - ry)
    if distance(p1, p2) <= tolerance:
        return [p1]
    return [p1, p2]


def circle_arc_intersections(circle: Circle2, arc: Arc2, *, tolerance: float = 1.0e-7) -> list[tuple[Point2, float]]:
    hits: list[tuple[Point2, float]] = []
    for point in circle_circle_intersections(circle, Circle2(arc.center, arc.radius), tolerance=tolerance):
        arc_t = arc.parameter_for_point(point, tolerance=tolerance)
        if arc_t is not None:
            hits.append((point, arc_t))
    return hits


def arc_arc_intersections(first: Arc2, second: Arc2, *, tolerance: float = 1.0e-7) -> list[tuple[Point2, float, float]]:
    hits: list[tuple[Point2, float, float]] = []
    for point in circle_circle_intersections(Circle2(first.center, first.radius), Circle2(second.center, second.radius), tolerance=tolerance):
        t_first = first.parameter_for_point(point, tolerance=tolerance)
        t_second = second.parameter_for_point(point, tolerance=tolerance)
        if t_first is not None and t_second is not None:
            hits.append((point, t_first, t_second))
    return hits


def _ccw_delta(a: float, b: float) -> float:
    return (float(b) - float(a)) % TAU
