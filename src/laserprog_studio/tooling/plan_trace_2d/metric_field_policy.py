# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import re
from typing import Any

from .constants import _MODE_ARC, _MODE_CIRCLE, _MODE_HALF_CIRCLE
from .curve_intent import distance_xy
from .state import _PlacementMetricDraft


def apply_metric_field_update(draft: _PlacementMetricDraft, field_id: str, value_text: str) -> bool:
    """Parse and apply one editable metric field to a draft session.

    The overlay-facing service is responsible for rollback and rendering. This
    module owns only field-level policy: unit parsing plus linked field updates
    such as radius/diameter and arc radius/angle synchronisation.
    """

    from laserprog_studio.tool_api.plan2d import metrics as metric_api

    session = draft.session
    field = session.fields.get(field_id)
    if field is None:
        return False
    if draft.mode == _MODE_ARC and field_id == "angle":
        parsed = _parse_arc_sweep_value(value_text)
    else:
        parsed = metric_api.parse_metric_value(value_text, field)
    session.replace_field_value(field_id, parsed)
    _sync_linked_metric_fields(draft, field_id=field_id, parsed=parsed)
    return True



def _parse_arc_sweep_value(value_text: str) -> float:
    """Parse arc sweep as a 0..360 value instead of a signed orientation angle."""

    raw = str(value_text).strip().lower().replace(",", ".").replace("deg", "°")
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(°)?\s*", raw)
    if not match:
        raise ValueError(f"Invalid arc angle {value_text!r}")
    value = abs(float(match.group(1)))
    if not math.isfinite(value):
        raise ValueError(f"Invalid arc angle {value_text!r}")
    # Keep the sweep open at 360 degrees so start/end/control never collapse into
    # an indistinguishable full circle in the three-point sketch representation.
    return max(1.0e-6, min(359.999, value % 360.0 if value >= 360.0 else value))

def _sync_linked_metric_fields(draft: _PlacementMetricDraft, *, field_id: str, parsed: float) -> None:
    session = draft.session
    if draft.mode in {_MODE_CIRCLE, _MODE_HALF_CIRCLE}:
        # Radius and diameter are linked views of the same primitive.
        if field_id == "radius" and "diameter" in session.fields:
            session.replace_field_value("diameter", parsed * 2.0)
        elif field_id == "diameter" and "radius" in session.fields:
            session.replace_field_value("radius", parsed * 0.5)
    if draft.mode == _MODE_ARC and field_id in {"radius", "angle"}:
        _sync_arc_metric_pair(draft, changed_field=field_id)


def _sync_arc_metric_pair(draft: _PlacementMetricDraft, *, changed_field: str) -> None:
    if draft.start_xy is None or draft.end_xy is None:
        return
    start = draft.start_xy
    end = draft.end_xy
    chord = distance_xy(start, end)
    if chord <= 1.0e-8:
        return
    session = draft.session
    values = session.as_values()
    if changed_field == "radius" and "angle" in session.fields:
        radius = max(float(values.get("radius", 0.0)), chord * 0.5 + 1.0e-9)
        try:
            minor_angle = math.degrees(2.0 * math.asin(max(-1.0, min(1.0, chord / (2.0 * radius)))))
            angle = 360.0 - minor_angle if draft.arc_intent is not None and draft.arc_intent.major else minor_angle
            session.replace_field_value("angle", angle)
        except Exception:
            pass
    elif changed_field == "angle" and "radius" in session.fields:
        angle = max(1.0e-6, min(359.999, abs(float(values.get("angle", 0.0)))))
        try:
            radius = chord / max(2.0 * math.sin(math.radians(angle) * 0.5), 1.0e-9)
            session.replace_field_value("radius", radius)
            if draft.arc_intent is not None:
                draft.arc_intent = draft.arc_intent.with_control(draft.control_xy or draft.arc_intent.control_xy, sweep_degrees=angle)
        except Exception:
            pass


__all__ = ["apply_metric_field_update"]
