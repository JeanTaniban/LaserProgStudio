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
class HollowMeshSettings:
    """Validated user-facing settings for the Hollow Mesh tool."""

    preset_id: str = "balanced"
    thickness_mm: float = 2.0

    @property
    def summary(self) -> str:
        return f"{self.thickness_mm:.2f} mm wall"


def hollow_settings_from_values(values: dict[str, Any]) -> HollowMeshSettings:
    return HollowMeshSettings(
        preset_id=str(values.get("hollow_preset", values.get("preset_id", "balanced")) or "balanced"),
        thickness_mm=_clamp_float(values.get("thickness_mm", 2.0), 2.0, low=0.001, high=100000.0),
    )


__all__ = ["HollowMeshSettings", "hollow_settings_from_values"]
