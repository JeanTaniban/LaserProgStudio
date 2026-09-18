# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .contracts import Vec2, VentFlareSide
from .validation import distance2d

if TYPE_CHECKING:  # pragma: no cover
    from .vent_model import VentPathDraft


def sampled_centerline_with_flare_scales(draft: "VentPathDraft", *, samples_per_segment: int = 18) -> tuple[list[Vec2], list[float]]:
    """Return sampled EVT path points plus local embouchure scale.

    The embouchure is anchored to the user waypoints, not to distance samples
    that can shift when curve radius/force changes.  Start flare is evaluated
    only on segment 0 and is exactly maximal at waypoint 0.  End flare is
    evaluated only on the last segment and is exactly maximal at the last
    waypoint.  Preview, snapping and Apply use this helper together.
    """

    pts = [(float(u), float(v)) for u, v in getattr(draft, "waypoints", [])]
    if not pts:
        return ([], [])
    if len(pts) == 1:
        return ([pts[0]], [draft.normalized_flare_factor() if draft.has_active_flare() else 1.0])

    offsets = draft.curve_offsets_for_sampling()
    count = len(pts) - 1
    samples = max(2, int(samples_per_segment))
    factor = draft.normalized_flare_factor()
    side = draft.effective_flare_side()

    def smooth(x: float) -> float:
        t = min(max(float(x), 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)

    def scale_for(segment_index: int, t: float) -> float:
        if factor <= 1.000001 or side is VentFlareSide.NONE:
            return 1.0
        value = 1.0
        if side in {VentFlareSide.START, VentFlareSide.BOTH} and int(segment_index) == 0:
            value = max(value, 1.0 + (factor - 1.0) * smooth(1.0 - float(t)))
        if side in {VentFlareSide.END, VentFlareSide.BOTH} and int(segment_index) == count - 1:
            value = max(value, 1.0 + (factor - 1.0) * smooth(float(t)))
        return float(value)

    out: list[Vec2] = [pts[0]]
    scales: list[float] = [scale_for(0, 0.0)]
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        if distance2d(a, b) <= 1e-9:
            continue
        offset = float(offsets[i]) if i < len(offsets) else 0.0
        needs_dense = abs(offset) > 1e-9 or (factor > 1.000001 and (
            (side in {VentFlareSide.START, VentFlareSide.BOTH} and i == 0) or
            (side in {VentFlareSide.END, VentFlareSide.BOTH} and i == count - 1)
        ))
        step_count = samples if needs_dense else 1
        if abs(offset) <= 1e-9:
            for step in range(1, step_count + 1):
                t = step / step_count
                pnt = (float(a[0]) + (float(b[0]) - float(a[0])) * t, float(a[1]) + (float(b[1]) - float(a[1])) * t)
                if distance2d(out[-1], pnt) > 1e-6:
                    out.append(pnt)
                    scales.append(scale_for(i, t))
            continue
        mid = ((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5)
        dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
        length = math.hypot(dx, dy)
        nx, ny = ((-dy / length, dx / length) if length > 1e-12 else (0.0, 1.0))
        control = (mid[0] + nx * offset, mid[1] + ny * offset)
        for step in range(1, samples + 1):
            t = step / samples
            u = 1.0 - t
            pnt = (
                u * u * float(a[0]) + 2.0 * u * t * float(control[0]) + t * t * float(b[0]),
                u * u * float(a[1]) + 2.0 * u * t * float(control[1]) + t * t * float(b[1]),
            )
            if distance2d(out[-1], pnt) > 1e-6:
                out.append(pnt)
                scales.append(scale_for(i, t))
    if len(scales) != len(out):
        scales = [scales[min(i, len(scales) - 1)] if scales else 1.0 for i in range(len(out))]
    return (out, scales)
