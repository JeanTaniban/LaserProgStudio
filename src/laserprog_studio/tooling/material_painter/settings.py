# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from laserprog_studio.domain.material import MeshMaterial

MaterialTargetScope = Literal["selected", "all"]


def safe_hex_color(value: str, fallback: str = "#B8B8B8") -> str:
    raw = str(value or "").strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6:
        return fallback
    try:
        int(raw, 16)
    except Exception:
        return fallback
    return "#" + raw.upper()


def _clamp_float(value: Any, fallback: float, *, low: float, high: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(fallback)
    return max(float(low), min(float(high), number))


@dataclass(frozen=True, slots=True)
class MaterialPainterSettings:
    preset_id: str = "custom"
    name: str = "Material"
    base_color: str = "#336699"
    opacity: float = 1.0
    metallic: float = 0.0
    roughness: float = 0.55
    target_scope: MaterialTargetScope = "selected"

    @property
    def material(self) -> MeshMaterial:
        return MeshMaterial(
            name=self.name,
            base_color=self.base_color,
            opacity=self.opacity,
            metallic=self.metallic,
            roughness=self.roughness,
        )

    @property
    def summary(self) -> str:
        alpha = f"{self.opacity:.0%}"
        return f"{self.name} · {self.base_color} · opacity {alpha} · metal {self.metallic:.2f} · rough {self.roughness:.2f}"


def material_settings_from_values(values: dict[str, Any]) -> MaterialPainterSettings:
    target = str(values.get("target_scope", "selected") or "selected").strip().lower()
    if target not in {"selected", "all"}:
        target = "selected"
    name = str(values.get("material_name", "Material") or "Material").strip() or "Material"
    return MaterialPainterSettings(
        preset_id=str(values.get("preset_id", "custom") or "custom"),
        name=name,
        base_color=safe_hex_color(str(values.get("material_color", "#336699")), "#B8B8B8"),
        opacity=_clamp_float(values.get("opacity", 1.0), 1.0, low=0.05, high=1.0),
        metallic=_clamp_float(values.get("metallic", 0.0), 0.0, low=0.0, high=1.0),
        roughness=_clamp_float(values.get("roughness", 0.55), 0.55, low=0.0, high=1.0),
        target_scope=target,  # type: ignore[arg-type]
    )


def material_from_values(values: dict[str, Any]) -> MeshMaterial:
    return material_settings_from_values(values).material
