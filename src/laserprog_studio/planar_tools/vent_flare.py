# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from .contracts import VentFlareSide


def effective_vent_flare_side(*, requested: VentFlareSide | str, end_finalized: bool) -> VentFlareSide:
    """Return the flare side that is geometrically active right now.

    In the simplified rectangular EVT workflow, the last placed waypoint is the
    current outlet.  The outlet embouchure must therefore be visible and applied
    immediately instead of waiting for a hidden/double-click finalization step.
    ``end_finalized`` is kept in the signature only for backwards-compatible
    callers and is intentionally ignored.
    """

    try:
        return requested if isinstance(requested, VentFlareSide) else VentFlareSide(str(requested))
    except Exception:
        return VentFlareSide.NONE


def vent_flare_transition_length(*, total_length: float, max_inner_dimension: float, wall_thickness: float, factor: float) -> float:
    """Return a bounded transition length for a smooth anti-chuff flare."""

    total = max(float(total_length), 0.0)
    if total <= 1e-9 or float(factor) <= 1.000001:
        return 0.0
    base = max(float(max_inner_dimension), float(wall_thickness) * 2.0, 1.0)
    desired = max(base, base * (1.25 + 0.75 * (float(factor) - 1.0)))
    return min(total * 0.45, desired)


def vent_flare_scale_at(*, distance_from_start: float, total_length: float, transition_length: float, side: VentFlareSide | str, factor: float) -> float:
    """Scale the internal section at a sampled station along the vent."""

    try:
        flare_side = side if isinstance(side, VentFlareSide) else VentFlareSide(str(side))
    except Exception:
        flare_side = VentFlareSide.NONE
    f = max(float(factor), 1.0)
    if f <= 1.000001 or flare_side is VentFlareSide.NONE or float(total_length) <= 1e-9 or float(transition_length) <= 1e-9:
        return 1.0

    def smooth(x: float) -> float:
        t = min(max(float(x), 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)

    transition = max(float(transition_length), 1e-9)
    total = max(float(total_length), 0.0)
    distance = min(max(float(distance_from_start), 0.0), total)
    scale = 1.0
    if flare_side in {VentFlareSide.START, VentFlareSide.BOTH}:
        t = 1.0 - min(distance, transition) / transition
        scale = max(scale, 1.0 + (f - 1.0) * smooth(t))
    if flare_side in {VentFlareSide.END, VentFlareSide.BOTH}:
        t = 1.0 - min(total - distance, transition) / transition
        scale = max(scale, 1.0 + (f - 1.0) * smooth(t))
    return float(scale)
