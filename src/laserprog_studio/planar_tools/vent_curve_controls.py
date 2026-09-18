# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .contracts import Vec2
from .validation import PlanarValidationResult, distance2d
from .vent_path_geometry import segment_control_point

if TYPE_CHECKING:  # pragma: no cover
    from .vent_model import VentPathDraft


def segment_count(draft: "VentPathDraft") -> int:
    return max(len(draft.waypoints) - 1, 0)


def default_curve_offset(draft: "VentPathDraft") -> float:
    # Kept for existing callers.  Pass 36 does not use this as
    # an ADD default: new segments are straight until edited in MOD.
    radius = max(float(draft.curve_radius), 0.0)
    strength = max(-1.0, min(1.0, float(draft.curve_strength)))
    return radius * strength


def _sign(value: float) -> float:
    if float(value) > 1e-9:
        return 1.0
    if float(value) < -1e-9:
        return -1.0
    return 0.0


def sync_curve_offsets(draft: "VentPathDraft") -> None:
    count = segment_count(draft)
    for attr in ("segment_curve_offsets", "segment_curve_radii", "segment_curve_strengths"):
        values = getattr(draft, attr, None)
        if values is None:
            setattr(draft, attr, [])
            values = getattr(draft, attr)
        if len(values) < count:
            values.extend([0.0] * (count - len(values)))
        elif len(values) > count:
            del values[count:]

    # Project-state fallback: if an older project/test only populated offsets, infer the
    # displayed radius/force pair once.  Otherwise radii/strengths remain the
    # source of truth and offsets are derived from them.
    for i in range(count):
        offset = float(draft.segment_curve_offsets[i])
        radius = float(draft.segment_curve_radii[i])
        strength = float(draft.segment_curve_strengths[i])
        if abs(offset) > 1e-9 and radius <= 1e-9 and abs(strength) <= 1e-9:
            draft.segment_curve_radii[i] = abs(offset)
            draft.segment_curve_strengths[i] = _sign(offset)
        else:
            r = max(float(draft.segment_curve_radii[i]), 0.0)
            s = max(-1.0, min(1.0, float(draft.segment_curve_strengths[i])))
            draft.segment_curve_radii[i] = r
            draft.segment_curve_strengths[i] = s
            draft.segment_curve_offsets[i] = r * s


def curve_offsets_for_sampling(draft: "VentPathDraft") -> list[float]:
    sync_curve_offsets(draft)
    return [float(v) for v in draft.segment_curve_offsets]


def segment_handle_points(draft: "VentPathDraft") -> list[Vec2]:
    offsets = curve_offsets_for_sampling(draft)
    return [segment_control_point(a, b, offsets[i]) for i, (a, b) in enumerate(zip(draft.waypoints, draft.waypoints[1:]))]


def nearest_curve_handle_index(draft: "VentPathDraft", point: Vec2, *, max_distance: float | None = None) -> int | None:
    handles = segment_handle_points(draft)
    if not handles:
        return None
    q = (float(point[0]), float(point[1]))
    best = min(range(len(handles)), key=lambda i: distance2d(handles[i], q))
    return None if max_distance is not None and distance2d(handles[best], q) > float(max_distance) else int(best)


def update_curve_handle_plane(draft: "VentPathDraft", index: int, point: Vec2) -> float:
    sync_curve_offsets(draft)
    i = int(index)
    if not (0 <= i < segment_count(draft)):
        raise ValueError("No vent curve handle is selected.")
    a, b = draft.waypoints[i], draft.waypoints[i + 1]
    dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        offset = 0.0
    else:
        nx, ny = -dy / length, dx / length
        mid = ((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5)
        offset = (float(point[0]) - mid[0]) * nx + (float(point[1]) - mid[1]) * ny
    draft.segment_curve_offsets[i] = float(offset)
    draft.segment_curve_radii[i] = abs(float(offset))
    draft.segment_curve_strengths[i] = _sign(float(offset))
    draft.curve_radius = draft.segment_curve_radii[i]
    draft.curve_strength = draft.segment_curve_strengths[i]
    return float(offset)


def curve_handle_candidate_is_valid(draft: "VentPathDraft", index: int, point: Vec2) -> PlanarValidationResult:
    if not (0 <= int(index) < segment_count(draft)):
        return PlanarValidationResult(ok=False, errors=("invalid curve handle",))
    old_offsets = curve_offsets_for_sampling(draft)
    old_radii = list(draft.segment_curve_radii)
    old_strengths = list(draft.segment_curve_strengths)
    old_radius = float(draft.curve_radius)
    old_strength = float(draft.curve_strength)
    try:
        update_curve_handle_plane(draft, index, point)
        return draft.validation_result()
    finally:
        draft.segment_curve_offsets = old_offsets
        draft.segment_curve_radii = old_radii
        draft.segment_curve_strengths = old_strengths
        draft.curve_radius = old_radius
        draft.curve_strength = old_strength


def selected_segment_index(draft: "VentPathDraft") -> int | None:
    """Return the segment edited by the selected waypoint.

    A selected point edits the incoming segment.  The first point is the only
    exception: it edits the first outgoing segment.  This keeps the UI simple
    and avoids separate curve handles in the scene.
    """

    selected = getattr(draft, "selected_index", None)
    count = segment_count(draft)
    if selected is None or count <= 0:
        return None
    i = int(selected)
    if i <= 0:
        return 0
    return max(0, min(i - 1, count - 1))


def selected_segment_offset(draft: "VentPathDraft") -> float:
    offsets = curve_offsets_for_sampling(draft)
    idx = selected_segment_index(draft)
    if idx is None:
        return 0.0
    return float(offsets[int(idx)])


def selected_segment_curve(draft: "VentPathDraft") -> tuple[float, float] | None:
    sync_curve_offsets(draft)
    idx = selected_segment_index(draft)
    if idx is None:
        return None
    return (float(draft.segment_curve_radii[int(idx)]), float(draft.segment_curve_strengths[int(idx)]))


def set_selected_segment_curve(draft: "VentPathDraft", *, radius: float, strength: float) -> int | None:
    sync_curve_offsets(draft)
    idx = selected_segment_index(draft)
    if idx is None:
        return None
    r = max(float(radius), 0.0)
    s = max(-1.0, min(1.0, float(strength)))
    draft.curve_radius = r
    draft.curve_strength = s
    draft.segment_curve_radii[int(idx)] = r
    draft.segment_curve_strengths[int(idx)] = s
    draft.segment_curve_offsets[int(idx)] = r * s
    return int(idx)
