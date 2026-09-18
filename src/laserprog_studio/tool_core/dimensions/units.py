"""Unit formatting/parsing for sketch dimensions."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class UnitSystem:
    """Length unit policy for passive dimensions.

    The sketch kernel stores lengths in document units.  For now the Plan Tracer
    treats those units as millimetres; callers can override ``unit`` and
    ``unit_scale`` without changing dimension entities.
    """

    unit: str = "mm"
    precision: int = 1
    unit_scale: float = 1.0

    def format_length(self, value: float | None) -> str:
        if value is None:
            return "—"
        scaled = float(value) / max(float(self.unit_scale), 1.0e-12)
        precision = max(int(self.precision), 0)
        text = f"{scaled:.{precision}f}"
        if precision > 0:
            text = text.rstrip("0").rstrip(".")
        return f"{text} {self.unit}"

    def parse_length(self, text: str) -> float:
        raw = str(text).strip().lower().replace(",", ".")
        match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-z]*)\s*", raw)
        if not match:
            raise ValueError(f"Invalid length {text!r}")
        value = float(match.group(1))
        unit = match.group(2) or self.unit.lower()
        factors = {
            "mm": 1.0,
            "millimeter": 1.0,
            "millimetre": 1.0,
            "cm": 10.0,
            "m": 1000.0,
            "in": 25.4,
            "inch": 25.4,
            "inches": 25.4,
        }
        if unit not in factors:
            raise ValueError(f"Unsupported length unit {unit!r}")
        # Convert parsed value back to document units.
        return value * factors[unit] * max(float(self.unit_scale), 1.0e-12)


DEFAULT_UNIT_SYSTEM = UnitSystem()
