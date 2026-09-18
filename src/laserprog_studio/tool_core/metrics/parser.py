"""Parsing and formatting for temporary metric input values."""
from __future__ import annotations

import math
import re

from .types import MetricFieldSpec, MetricKind
from laserprog_studio.tool_core.dimensions.units import DEFAULT_UNIT_SYSTEM, UnitSystem


def format_metric_value(field: MetricFieldSpec) -> str:
    kind_value = field.kind.value if isinstance(field.kind, MetricKind) else str(field.kind)
    kind = MetricKind(kind_value) if kind_value in MetricKind._value2member_map_ else None
    if kind == MetricKind.ANGLE:
        precision = max(int(field.precision), 0)
        text = f"{float(field.value):.{precision}f}"
        if precision > 0:
            text = text.rstrip("0").rstrip(".")
        return f"{text}°"
    units = UnitSystem(unit=str(field.unit or "mm"), precision=int(field.precision or 1), unit_scale=1.0)
    return units.format_length(float(field.value))


def parse_metric_value(text: str, field: MetricFieldSpec, *, unit_system: UnitSystem = DEFAULT_UNIT_SYSTEM) -> float:
    kind_value = field.kind.value if isinstance(field.kind, MetricKind) else str(field.kind)
    kind = MetricKind(kind_value) if kind_value in MetricKind._value2member_map_ else None
    if kind == MetricKind.ANGLE:
        raw = str(text).strip().lower().replace(",", ".").replace("deg", "°")
        match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(°)?\s*", raw)
        if not match:
            raise ValueError(f"Invalid angle {text!r}")
        value = float(match.group(1))
        # Normalize for stable UI, but preserve signed direction.
        if math.isfinite(value):
            while value <= -180.0:
                value += 360.0
            while value > 180.0:
                value -= 360.0
        return value
    return unit_system.parse_length(str(text))
