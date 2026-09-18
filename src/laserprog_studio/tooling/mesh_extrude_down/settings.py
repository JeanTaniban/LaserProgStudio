# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clamp_float(value: Any, fallback: float, *, low: float, high: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(fallback)
    return max(float(low), min(float(high), number))


@dataclass(frozen=True, slots=True)
class ExtrudeDownSettings:
    """Validated user-facing settings for the Extrude Down tool."""

    preset_id: str = "support_shelf"
    plane_ratio: float = 33.0
    plane_z: float = 0.0
    ground_z: float = 0.0
    tolerance: float = 0.001

    @property
    def summary(self) -> str:
        return f"plane {self.plane_z:g} mm → ground {self.ground_z:g} mm · tol {self.tolerance:g}"


def extrude_down_settings_from_values(values: dict[str, Any]) -> ExtrudeDownSettings:
    return ExtrudeDownSettings(
        preset_id=str(values.get("extrude_down_preset", values.get("preset_id", "support_shelf")) or "support_shelf"),
        plane_ratio=_clamp_float(values.get("plane_ratio", 33.0), 33.0, low=1.0, high=99.0),
        plane_z=_clamp_float(values.get("plane_z", 0.0), 0.0, low=-1_000_000.0, high=1_000_000.0),
        ground_z=_clamp_float(values.get("ground_z", 0.0), 0.0, low=-1_000_000.0, high=1_000_000.0),
        tolerance=_clamp_float(values.get("tolerance", 0.001), 0.001, low=0.00000001, high=10.0),
    )


__all__ = ["ExtrudeDownSettings", "extrude_down_settings_from_values"]
