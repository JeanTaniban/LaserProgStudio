"""Public curve-intent helpers for Plan 2D creator tools.

The sketch kernel stores arcs as start/end/control references.  Interactive
creator tools also need the user intent that is not explicit in those three ids:
which side of the chord the curve lives on, whether the sweep is major/minor and
how to rebuild a stable control point after numeric edits.  Those contracts are
public here so new Plan 2D tools do not copy Plan Tracer internals.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

Point2 = tuple[float, float]
_EPSILON = 1.0e-9


def _point2(value: Point2) -> Point2:
    return (float(value[0]), float(value[1]))


def signed_side(start: Point2, end: Point2, point: Point2) -> float:
    """Return the signed side of ``point`` relative to the oriented chord."""

    sx, sy = _point2(start)
    ex, ey = _point2(end)
    px, py = _point2(point)
    return (ex - sx) * (py - sy) - (ey - sy) * (px - sx)


def normalize_side(value: float | int | None, *, fallback: float = 1.0) -> float:
    """Normalize a side value to the explicit Plan 2D contract: ``-1.0`` or ``+1.0``."""

    if value is None:
        return 1.0 if fallback >= 0.0 else -1.0
    try:
        numeric = float(value)
    except Exception:
        numeric = float(fallback)
    return 1.0 if numeric >= 0.0 else -1.0


def distance_xy(first: Point2, second: Point2) -> float:
    fx, fy = _point2(first)
    sx, sy = _point2(second)
    return math.hypot(sx - fx, sy - fy)





def sample_circle(center: Point2, radius: float, *, segments: int = 64) -> list[Point2]:
    """Sample a circle through the public Plan 2D geometry facade."""

    from laserprog_studio.tool_core.geometry import sample_circle as _sample

    return _sample(center, radius, segments=segments)


def sample_circular_arc_through_points(
    start: Point2,
    end: Point2,
    control: Point2,
    *,
    segments: int = 24,
) -> list[Point2]:
    """Sample a circular arc through the public Plan 2D geometry facade."""

    from laserprog_studio.tool_core.geometry import sample_circular_arc_through_points as _sample

    return _sample(start, end, control, segments=segments)


def sample_cubic_bezier(
    start: Point2,
    control_1: Point2,
    control_2: Point2,
    end: Point2,
    *,
    segments: int = 48,
) -> list[Point2]:
    """Sample a cubic Bézier through the public Plan 2D curve facade.

    Built-in drawing tools use this public wrapper rather than importing the
    geometry kernel directly. Endpoints are preserved exactly.
    """

    from laserprog_studio.tool_core.geometry import sample_cubic_bezier as _sample

    return _sample(start, control_1, control_2, end, segments=segments)

def circular_arc_length(start: Point2, end: Point2, control: Point2) -> float | None:
    """Return the exact length of the circular arc passing through ``control``.

    ``None`` is returned for collinear/degenerate triples.  Keeping this helper
    in the public Plan 2D curve facade lets creator tools measure arcs without
    importing geometry-kernel internals directly.
    """

    circle = _circle_from_three_points(start, control, end)
    if circle is None:
        return None
    _center, radius = circle
    sweep_degrees = _sweep_degrees_through_control(start, end, control)
    if sweep_degrees <= _EPSILON:
        return None
    return float(radius) * math.radians(float(sweep_degrees))


def _circle_from_three_points(start: Point2, through: Point2, end: Point2) -> tuple[Point2, float] | None:
    sx, sy = _point2(start)
    tx, ty = _point2(through)
    ex, ey = _point2(end)
    det = 2.0 * (sx * (ty - ey) + tx * (ey - sy) + ex * (sy - ty))
    if abs(det) <= 1.0e-12:
        return None
    s2 = sx * sx + sy * sy
    t2 = tx * tx + ty * ty
    e2 = ex * ex + ey * ey
    ox = (s2 * (ty - ey) + t2 * (ey - sy) + e2 * (sy - ty)) / det
    oy = (s2 * (ex - tx) + t2 * (sx - ex) + e2 * (tx - sx)) / det
    radius = math.hypot(sx - ox, sy - oy)
    if radius <= _EPSILON or not math.isfinite(radius):
        return None
    return (ox, oy), radius


def _ccw_delta(start_angle: float, end_angle: float) -> float:
    return (end_angle - start_angle) % math.tau


def _sweep_degrees_through_control(start: Point2, end: Point2, control: Point2) -> float:
    circle = _circle_from_three_points(start, control, end)
    if circle is None:
        return 0.0
    (ox, oy), _radius = circle
    sx, sy = _point2(start)
    ex, ey = _point2(end)
    cx, cy = _point2(control)
    a0 = math.atan2(sy - oy, sx - ox)
    a1 = math.atan2(ey - oy, ex - ox)
    ac = math.atan2(cy - oy, cx - ox)
    ccw_sweep = _ccw_delta(a0, a1)
    control_on_ccw = _ccw_delta(a0, ac) <= ccw_sweep + 1.0e-9
    sweep = ccw_sweep if control_on_ccw else _ccw_delta(a1, a0)
    return math.degrees(sweep)


@dataclass(frozen=True, slots=True)
class ArcIntent:
    """User intent for a three-point circular arc.

    ``side`` is signed relative to the chord from ``start_xy`` to ``end_xy``.
    ``major`` records whether the intended sweep is greater than 180 degrees.
    """

    start_xy: Point2
    end_xy: Point2
    control_xy: Point2
    side: float = 1.0
    major: bool = False
    sweep_degrees: float = 0.0

    @classmethod
    def from_points(cls, start: Point2, end: Point2, control: Point2) -> "ArcIntent":
        side = normalize_side(signed_side(start, end, control))
        sweep = _sweep_degrees_through_control(start, end, control)
        return cls(
            start_xy=_point2(start),
            end_xy=_point2(end),
            control_xy=_point2(control),
            side=side,
            major=bool(sweep > 180.0 + 1.0e-6),
            sweep_degrees=float(sweep),
        )

    def with_control(self, control: Point2, *, sweep_degrees: float | None = None) -> "ArcIntent":
        computed = self.from_points(self.start_xy, self.end_xy, control)
        return ArcIntent(
            start_xy=self.start_xy,
            end_xy=self.end_xy,
            control_xy=_point2(control),
            side=computed.side,
            major=computed.major if sweep_degrees is None else bool(abs(float(sweep_degrees)) > 180.0 + 1.0e-6),
            sweep_degrees=computed.sweep_degrees if sweep_degrees is None else abs(float(sweep_degrees)),
        )


@dataclass(frozen=True, slots=True)
class HalfCircleIntent:
    """User intent for a half-circle defined by a diameter chord."""

    start_xy: Point2
    end_xy: Point2
    side: float = 1.0

    @classmethod
    def from_points(cls, start: Point2, end: Point2, *, side: float = 1.0) -> "HalfCircleIntent":
        return cls(start_xy=_point2(start), end_xy=_point2(end), side=normalize_side(side))

    def control_xy(self) -> Point2:
        return half_circle_control_point(self.start_xy, self.end_xy, side=self.side)


def half_circle_control_point(start: Point2, end: Point2, *, side: float = 1.0) -> Point2:
    sx, sy = _point2(start)
    ex, ey = _point2(end)
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length <= _EPSILON:
        return ((sx + ex) * 0.5, (sy + ey) * 0.5)
    midpoint = ((sx + ex) * 0.5, (sy + ey) * 0.5)
    signed = normalize_side(side)
    # The control point is the apex of the semicircle, not a Bezier handle.
    return (midpoint[0] - dy / length * (length * 0.5) * signed, midpoint[1] + dx / length * (length * 0.5) * signed)


def arc_control_from_intent(
    start: Point2,
    end: Point2,
    *,
    side: float,
    radius: float | None = None,
    angle_degrees: float | None = None,
    major: bool | None = None,
) -> Point2 | None:
    """Build a control point that preserves arc side and major/minor intent."""

    chord = distance_xy(start, end)
    if chord <= _EPSILON:
        return None
    if angle_degrees is not None:
        angle = max(1.0e-6, min(359.999, abs(float(angle_degrees))))
        half = math.radians(angle * 0.5)
        radius_value = chord / max(2.0 * math.sin(half), 1.0e-9)
        use_major = bool(angle > 180.0 + 1.0e-6) if major is None else bool(major)
    else:
        radius_value = max(float(radius if radius is not None else chord * 0.5), chord * 0.5 + 1.0e-9)
        use_major = bool(major) if major is not None else False
    radius_value = max(radius_value, chord * 0.5 + 1.0e-9)
    leg = math.sqrt(max(radius_value * radius_value - (chord * 0.5) ** 2, 0.0))
    sagitta = radius_value + leg if use_major else radius_value - leg
    sx, sy = _point2(start)
    ex, ey = _point2(end)
    midpoint = ((sx + ex) * 0.5, (sy + ey) * 0.5)
    dx, dy = ex - sx, ey - sy
    inv = 1.0 / chord
    perp = (-dy * inv, dx * inv)
    signed = normalize_side(side)
    return (midpoint[0] + perp[0] * sagitta * signed, midpoint[1] + perp[1] * sagitta * signed)


def curve_intent_metadata(*, side: float, major: bool | None = None, kind: str = "arc") -> dict[str, object]:
    """Return stable metadata for generated curve actors/entities."""

    data: dict[str, object] = {
        "curve_intent": str(kind),
        "curve_side": "left" if normalize_side(side) >= 0.0 else "right",
    }
    if major is not None:
        data["curve_major"] = bool(major)
    return data


__all__ = [
    "ArcIntent",
    "HalfCircleIntent",
    "Point2",
    "arc_control_from_intent",
    "circular_arc_length",
    "curve_intent_metadata",
    "distance_xy",
    "half_circle_control_point",
    "normalize_side",
    "sample_circle",
    "sample_circular_arc_through_points",
    "sample_cubic_bezier",
    "signed_side",
]
