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
class RepairMeshSettings:
    """Validated user-facing settings for the Repair Mesh tool."""

    preset_id: str = "balanced"
    tolerance_mm: float = 0.01
    fill_holes: bool = True
    remove_tiny_faces: bool = True

    @property
    def summary(self) -> str:
        holes = "fill holes" if self.fill_holes else "keep holes"
        tiny = "remove tiny faces" if self.remove_tiny_faces else "keep tiny faces"
        return f"tol {self.tolerance_mm:g} mm · {holes} · {tiny}"


def repair_settings_from_values(values: dict[str, Any]) -> RepairMeshSettings:
    return RepairMeshSettings(
        preset_id=str(values.get("repair_preset", "balanced") or "balanced"),
        tolerance_mm=_clamp_float(values.get("tolerance_mm", 0.01), 0.01, low=0.0001, high=10.0),
        fill_holes=_as_bool(values.get("fill_holes", True), True),
        remove_tiny_faces=_as_bool(values.get("remove_tiny_faces", True), True),
    )


__all__ = ["RepairMeshSettings", "repair_settings_from_values"]
