# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CUSTOM_PRESET_ID = "custom"
CENTER_Z_PRESET_ID = "center_z"


@dataclass(frozen=True, slots=True)
class SplitPlanePreset:
    id: str
    label: str
    note: str
    values: dict[str, Any]


_PRESETS: tuple[SplitPlanePreset, ...] = (
    SplitPlanePreset(CUSTOM_PRESET_ID, "Custom", "Manual split plane settings.", {}),
    SplitPlanePreset(
        CENTER_Z_PRESET_ID,
        "Center horizontal cut",
        "Cut through the selection center with a horizontal XY plane.",
        {"offset_mm": 0.0, "rx_deg": 0.0, "ry_deg": 0.0, "rz_deg": 0.0, "tolerance": 0.00001},
    ),
    SplitPlanePreset(
        "center_x",
        "Center left/right cut",
        "Cut through the selection center with a vertical YZ plane.",
        {"offset_mm": 0.0, "rx_deg": 0.0, "ry_deg": 90.0, "rz_deg": 0.0, "tolerance": 0.00001},
    ),
    SplitPlanePreset(
        "center_y",
        "Center front/back cut",
        "Cut through the selection center with a vertical XZ plane.",
        {"offset_mm": 0.0, "rx_deg": 90.0, "ry_deg": 0.0, "rz_deg": 0.0, "tolerance": 0.00001},
    ),
    SplitPlanePreset(
        "fine_offset",
        "Fine offset cut",
        "Start from the center plane with a small positive offset for controlled trimming.",
        {"offset_mm": 1.0, "rx_deg": 0.0, "ry_deg": 0.0, "rz_deg": 0.0, "tolerance": 0.00001},
    ),
    SplitPlanePreset(
        "wide_safe",
        "Wide safe plane",
        "Use a larger displayed plane and standard tolerance for broad edits.",
        {"offset_mm": 0.0, "rx_deg": 0.0, "ry_deg": 0.0, "rz_deg": 0.0, "plane_size_factor": 2.0, "tolerance": 0.00001},
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def split_preset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((preset.id, preset.label) for preset in _PRESETS)


def get_split_preset(preset_id: str | None) -> SplitPlanePreset:
    return _PRESET_BY_ID.get(str(preset_id or ""), _PRESET_BY_ID[CUSTOM_PRESET_ID])


def split_preset_values(preset_id: str | None) -> dict[str, Any]:
    return dict(get_split_preset(preset_id).values)


def split_preset_note(preset_id: str | None) -> str:
    return get_split_preset(preset_id).note


def detect_split_preset(values: dict[str, Any]) -> str:
    def close(field_id: str, expected: float) -> bool:
        try:
            return abs(float(values.get(field_id, 0.0)) - float(expected)) <= 1e-9
        except Exception:
            return False

    for preset in _PRESETS:
        if preset.id == CUSTOM_PRESET_ID:
            continue
        preset_values = preset.values
        if all(close(field_id, value) for field_id, value in preset_values.items() if field_id != "plane_size_factor"):
            return preset.id
    return CUSTOM_PRESET_ID


__all__ = [
    "CENTER_Z_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "SplitPlanePreset",
    "detect_split_preset",
    "get_split_preset",
    "split_preset_choices",
    "split_preset_note",
    "split_preset_values",
]
