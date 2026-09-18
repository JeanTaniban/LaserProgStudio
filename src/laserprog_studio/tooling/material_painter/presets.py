# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MaterialPreset:
    id: str
    label: str
    name: str
    color: str
    opacity: float = 1.0
    metallic: float = 0.0
    roughness: float = 0.55
    note: str = ""

    def values(self) -> dict[str, Any]:
        return {
            "material_name": self.name,
            "material_color": self.color,
            "opacity": self.opacity,
            "metallic": self.metallic,
            "roughness": self.roughness,
        }


MATERIAL_PRESETS: tuple[MaterialPreset, ...] = (
    MaterialPreset("custom", "Custom", "Material", "#336699", 1.0, 0.0, 0.55, "Manual material values."),
    MaterialPreset("neutral_plastic", "Neutral plastic", "Neutral plastic", "#B8B8B8", 1.0, 0.0, 0.48, "Safe default for technical parts."),
    MaterialPreset("matte_black", "Matte black", "Matte black", "#202124", 1.0, 0.0, 0.82, "Low reflection presentation material."),
    MaterialPreset("anodized_aluminum", "Anodized aluminum", "Anodized aluminum", "#8D99A6", 1.0, 0.65, 0.30, "Metal look for machined parts."),
    MaterialPreset("translucent_acrylic", "Translucent acrylic", "Translucent acrylic", "#73C7FF", 0.45, 0.0, 0.18, "Transparent visual check."),
    MaterialPreset("birch_plywood", "Birch plywood", "Birch plywood", "#D8B16A", 1.0, 0.0, 0.62, "Warm laser-cut wood preview."),
)


def _preset_by_id(preset_id: str) -> MaterialPreset:
    wanted = str(preset_id or "custom").strip() or "custom"
    for preset in MATERIAL_PRESETS:
        if preset.id == wanted:
            return preset
    return MATERIAL_PRESETS[0]


def material_preset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((preset.id, preset.label) for preset in MATERIAL_PRESETS)


def material_preset_values(preset_id: str) -> dict[str, Any]:
    return _preset_by_id(preset_id).values()


def material_preset_note(preset_id: str) -> str:
    return _preset_by_id(preset_id).note
