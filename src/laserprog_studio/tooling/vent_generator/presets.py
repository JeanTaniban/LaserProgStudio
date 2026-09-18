# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from laserprog_studio.planar_tools import VentFlareSide, VentSectionKind


CUSTOM_PRESET_ID = "custom"


@dataclass(frozen=True, slots=True)
class VentGeneratorPreset:
    """Named user-facing starter values for common vent shapes."""

    id: str
    label: str
    description: str
    values: dict[str, Any]


VENT_GENERATOR_PRESETS: tuple[VentGeneratorPreset, ...] = (
    VentGeneratorPreset(
        CUSTOM_PRESET_ID,
        "Custom",
        "Keep the current manual values.",
        {},
    ),
    VentGeneratorPreset(
        "rect_compact",
        "Compact rectangular duct",
        "Small 10 × 6 mm rectangular duct with printable 2 mm walls.",
        {
            "section_kind": VentSectionKind.RECTANGLE.value,
            "rect_width": 10.0,
            "rect_height": 6.0,
            "wall_thickness": 2.0,
            "fill_area": False,
            "flare_side": VentFlareSide.NONE.value,
            "flare_factor": 1.0,
        },
    ),
    VentGeneratorPreset(
        "rect_airbox",
        "Airbox adapter",
        "Wide 28 × 14 mm rectangular duct with inlet/outlet flare enabled.",
        {
            "section_kind": VentSectionKind.RECTANGLE.value,
            "rect_width": 28.0,
            "rect_height": 14.0,
            "wall_thickness": 2.4,
            "fill_area": False,
            "flare_side": VentFlareSide.BOTH.value,
            "flare_factor": 1.35,
        },
    ),
    VentGeneratorPreset(
        "rect_fill_block",
        "Filled rectangular block",
        "Solid exterior block around a 20 × 10 mm internal airway.",
        {
            "section_kind": VentSectionKind.RECTANGLE.value,
            "rect_width": 20.0,
            "rect_height": 10.0,
            "wall_thickness": 3.0,
            "fill_area": True,
            "flare_side": VentFlareSide.NONE.value,
            "flare_factor": 1.0,
        },
    ),
    VentGeneratorPreset(
        "round_small",
        "Small round pipe",
        "Round pipe around 12 mm diameter, expressed as flow area.",
        {
            "section_kind": VentSectionKind.ROUND.value,
            "section_area": 113.1,
            "wall_thickness": 2.0,
            "fill_area": False,
            "flare_side": VentFlareSide.NONE.value,
            "flare_factor": 1.0,
        },
    ),
    VentGeneratorPreset(
        "round_large_flared",
        "Large flared round pipe",
        "Flared round pipe around 25 mm diameter with both openings widened.",
        {
            "section_kind": VentSectionKind.ROUND.value,
            "section_area": 490.9,
            "wall_thickness": 2.5,
            "fill_area": False,
            "flare_side": VentFlareSide.BOTH.value,
            "flare_factor": 1.45,
        },
    ),
)


PRESET_CHOICES: tuple[tuple[str, str], ...] = tuple((preset.id, preset.label) for preset in VENT_GENERATOR_PRESETS)
_PRESET_BY_ID = {preset.id: preset for preset in VENT_GENERATOR_PRESETS}


def vent_preset_description(preset_id: str | None) -> str:
    preset = _PRESET_BY_ID.get(str(preset_id or CUSTOM_PRESET_ID), _PRESET_BY_ID[CUSTOM_PRESET_ID])
    return preset.description


def values_for_vent_preset(preset_id: str | None) -> dict[str, Any]:
    """Return a safe value update for a preset id."""

    preset = _PRESET_BY_ID.get(str(preset_id or CUSTOM_PRESET_ID))
    if preset is None or preset.id == CUSTOM_PRESET_ID:
        return {}
    values = dict(preset.values)
    values["quick_preset"] = preset.id
    values["preset_help"] = preset.description
    return values


__all__ = [
    "CUSTOM_PRESET_ID",
    "PRESET_CHOICES",
    "VENT_GENERATOR_PRESETS",
    "VentGeneratorPreset",
    "values_for_vent_preset",
    "vent_preset_description",
]
