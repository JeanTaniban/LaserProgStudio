# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Any

from .contracts import Vec2
from .validation import distance2d


@dataclass(frozen=True, slots=True)
class PlanTraceSnapHit:
    """Nearest reusable 2D construction target for the Plan tracer.

    The snap layer stays independent from Qt/PyVista.  The controller only
    needs plain plane coordinates, while the preview decides how to display the
    hit.  ``role`` is intentionally explicit because smart snap now covers both
    exact junction points and projected scene/shape edges.
    """

    point: Vec2
    distance: float
    role: str = "junction"


def _as_vec2(point: Any) -> Vec2 | None:
    try:
        return (float(point[0]), float(point[1]))
    except Exception:
        return None


def _dedupe(points: Iterable[Vec2], *, precision: int = 100_000) -> list[Vec2]:
    out: list[Vec2] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        p = _as_vec2(point)
        if p is None:
            continue
        key = (round(p[0] * int(precision)), round(p[1] * int(precision)))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def collect_plan_trace_snap_points(
    draft: Any,
    *,
    base_points: Iterable[Vec2] = (),
    samples_per_segment: int = 12,
    include_samples: bool = True,
    include_active: bool = True,
) -> list[Vec2]:
    """Collect every useful point that should be reusable as a 2D junction.

    This includes polygon vertices, curve handles/samples, independent
    line/arc/circle control points, sampled curves and currently staged points.
    Heavy scene anchors are intentionally not collected here; the controller
    owns their cache so pointer moves do not rescan the whole scene.
    """

    anchors: list[Vec2] = []
    anchors.extend(_dedupe(base_points))
    anchors.extend(_dedupe(getattr(draft, "points", []) or []))

    if include_samples:
        try:
            anchors.extend(_dedupe(draft.segment_handle_points()))
        except Exception:
            pass
        try:
            anchors.extend(_dedupe(draft.sampled_boundary_points(samples_per_segment=max(4, int(samples_per_segment)))))
        except Exception:
            pass

    for element in getattr(draft, "elements", []) or []:
        try:
            anchors.extend(_dedupe(element.normalized_points()))
        except Exception:
            anchors.extend(_dedupe(getattr(element, "points", []) or []))
        if include_samples:
            try:
                anchors.extend(_dedupe(element.sampled_points(samples=max(12, int(samples_per_segment) * 2))))
            except Exception:
                pass

    if include_active:
        anchors.extend(_dedupe(getattr(draft, "active_element_points", []) or []))

    return _dedupe(anchors)


def _nearest_point_on_segment(point: Vec2, a: Vec2, b: Vec2) -> Vec2 | None:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 <= 1e-12 or not math.isfinite(length2):
        return None
    t = ((px - ax) * vx + (py - ay) * vy) / length2
    # Keep endpoint snaps as junction snaps.  Edge snap should target the real
    # edge body, not steal priority from exact construction points.
    if t <= 1e-5 or t >= 1.0 - 1e-5:
        return None
    t = max(0.0, min(1.0, t))
    return (ax + vx * t, ay + vy * t)


def nearest_plan_trace_snap(
    point: Vec2,
    draft: Any,
    *,
    tolerance: float,
    samples_per_segment: int = 12,
    include_samples: bool = True,
    include_active: bool = True,
    extra_points: Iterable[Vec2] = (),
    edge_segments: Iterable[tuple[Vec2, Vec2]] = (),
) -> PlanTraceSnapHit | None:
    """Return the nearest reusable plan target, or None outside tolerance."""

    q = (float(point[0]), float(point[1]))
    tol = max(float(tolerance), 0.0)
    best: PlanTraceSnapHit | None = None

    anchors = collect_plan_trace_snap_points(
        draft,
        samples_per_segment=samples_per_segment,
        include_samples=include_samples,
        include_active=include_active,
    )
    anchors.extend(_dedupe(extra_points))
    for anchor in _dedupe(anchors):
        d = distance2d(q, anchor)
        if d <= tol and (best is None or d < best.distance):
            best = PlanTraceSnapHit(point=anchor, distance=float(d), role="junction")

    # Edges have slightly lower priority than points, but they make smart snap
    # useful on imported parts: the user can land directly on projected arêtes,
    # not only on sparse vertices/corners.
    edge_bias = min(max(tol * 0.10, 1e-6), 0.25)
    for a, b in edge_segments:
        aa = _as_vec2(a)
        bb = _as_vec2(b)
        if aa is None or bb is None:
            continue
        hit = _nearest_point_on_segment(q, aa, bb)
        if hit is None:
            continue
        d = distance2d(q, hit)
        if d <= tol and (best is None or d + edge_bias < best.distance):
            best = PlanTraceSnapHit(point=hit, distance=float(d), role="edge")
    return best
