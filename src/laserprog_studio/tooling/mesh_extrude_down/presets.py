# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CUSTOM_PRESET_ID = "custom"
SUPPORT_SHELF_PRESET_ID = "support_shelf"


@dataclass(frozen=True, slots=True)
class ExtrudeDownPreset:
    id: str
    label: str
    note: str
    values: dict[str, Any]


_PRESETS: tuple[ExtrudeDownPreset, ...] = (
    ExtrudeDownPreset(CUSTOM_PRESET_ID, "Custom", "Manual extrusion settings.", {}),
    ExtrudeDownPreset(
        "low_foot",
        "Low support foot",
        "Use a low cut plane for small feet and underside support pads.",
        {"plane_ratio": 22.0, "ground_z": 0.0, "tolerance": 0.001},
    ),
    ExtrudeDownPreset(
        SUPPORT_SHELF_PRESET_ID,
        "Support shelf",
        "Balanced starting point for vertical support down to the grid.",
        {"plane_ratio": 33.0, "ground_z": 0.0, "tolerance": 0.001},
    ),
    ExtrudeDownPreset(
        "mid_body",
        "Mid body drop",
        "Cut around the middle of the selected part when a larger landing is needed.",
        {"plane_ratio": 50.0, "ground_z": 0.0, "tolerance": 0.001},
    ),
    ExtrudeDownPreset(
        "upper_detail_safe",
        "Preserve upper detail",
        "Keep more top detail by placing the cut plane higher on the selected part.",
        {"plane_ratio": 68.0, "ground_z": 0.0, "tolerance": 0.001},
    ),
    ExtrudeDownPreset(
        "loose_scan",
        "Loose scan cleanup",
        "Use a slightly wider tolerance for noisy scans or imported meshes.",
        {"plane_ratio": 33.0, "ground_z": 0.0, "tolerance": 0.01},
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def extrude_down_preset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((preset.id, preset.label) for preset in _PRESETS)


def get_extrude_down_preset(preset_id: str | None) -> ExtrudeDownPreset:
    return _PRESET_BY_ID.get(str(preset_id or ""), _PRESET_BY_ID[CUSTOM_PRESET_ID])


def extrude_down_preset_values(preset_id: str | None) -> dict[str, Any]:
    return dict(get_extrude_down_preset(preset_id).values)


def extrude_down_preset_note(preset_id: str | None) -> str:
    return get_extrude_down_preset(preset_id).note


def detect_extrude_down_preset(values: dict[str, Any]) -> str:
    def close(field_id: str, expected: float) -> bool:
        try:
            return abs(float(values.get(field_id, 0.0)) - float(expected)) <= 1e-9
        except Exception:
            return False

    for preset in _PRESETS:
        if preset.id == CUSTOM_PRESET_ID:
            continue
        preset_values = preset.values
        if all(close(field_id, value) for field_id, value in preset_values.items()):
            return preset.id
    return CUSTOM_PRESET_ID


__all__ = [
    "CUSTOM_PRESET_ID",
    "SUPPORT_SHELF_PRESET_ID",
    "ExtrudeDownPreset",
    "detect_extrude_down_preset",
    "extrude_down_preset_choices",
    "extrude_down_preset_note",
    "extrude_down_preset_values",
    "get_extrude_down_preset",
]
