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


def _as_bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return bool(fallback)
    return bool(value)


@dataclass(frozen=True, slots=True)
class SimplifyMeshSettings:
    """Validated user-facing settings for the Simplify Mesh tool."""

    preset_id: str = "balanced"
    reduction_percent: float = 50.0
    preserve_topology: bool = True

    @property
    def reduction_ratio(self) -> float:
        return max(0.0, min(0.95, self.reduction_percent / 100.0))

    @property
    def summary(self) -> str:
        mode = "preserve topology" if self.preserve_topology else "allow stronger decimation"
        return f"{self.reduction_percent:.0f} % reduction · {mode}"


def simplify_settings_from_values(values: dict[str, Any]) -> SimplifyMeshSettings:
    return SimplifyMeshSettings(
        preset_id=str(values.get("simplify_preset", values.get("preset_id", "balanced")) or "balanced"),
        reduction_percent=_clamp_float(values.get("reduction_percent", 50.0), 50.0, low=0.0, high=95.0),
        preserve_topology=_as_bool(values.get("preserve_topology", True), True),
    )


__all__ = ["SimplifyMeshSettings", "simplify_settings_from_values"]
