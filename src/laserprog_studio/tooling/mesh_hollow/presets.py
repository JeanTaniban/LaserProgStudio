# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CUSTOM_PRESET_ID = "custom"
BALANCED_PRESET_ID = "balanced"


@dataclass(frozen=True, slots=True)
class HollowMeshPreset:
    id: str
    label: str
    note: str
    values: dict[str, Any]


_PRESETS: tuple[HollowMeshPreset, ...] = (
    HollowMeshPreset(CUSTOM_PRESET_ID, "Custom", "Manual hollow settings.", {}),
    HollowMeshPreset(
        "thin_shell",
        "Thin shell",
        "Light wall for visual prototypes and small non-structural parts.",
        {"thickness_mm": 1.0},
    ),
    HollowMeshPreset(
        BALANCED_PRESET_ID,
        "Balanced shell",
        "Recommended default for ordinary printable parts.",
        {"thickness_mm": 2.0},
    ),
    HollowMeshPreset(
        "strong_wall",
        "Strong wall",
        "Thicker wall for parts that need more stiffness or sanding margin.",
        {"thickness_mm": 3.2},
    ),
    HollowMeshPreset(
        "large_draft",
        "Large part draft",
        "Fast starting point for larger shells before checking wall feasibility.",
        {"thickness_mm": 5.0},
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def hollow_preset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((preset.id, preset.label) for preset in _PRESETS)


def get_hollow_preset(preset_id: str | None) -> HollowMeshPreset:
    return _PRESET_BY_ID.get(str(preset_id or ""), _PRESET_BY_ID[CUSTOM_PRESET_ID])


def hollow_preset_values(preset_id: str | None) -> dict[str, Any]:
    return dict(get_hollow_preset(preset_id).values)


def hollow_preset_note(preset_id: str | None) -> str:
    return get_hollow_preset(preset_id).note


def detect_hollow_preset(values: dict[str, Any]) -> str:
    try:
        thickness = float(values.get("thickness_mm", 2.0))
    except Exception:
        thickness = 2.0
    for preset in _PRESETS:
        if preset.id == CUSTOM_PRESET_ID:
            continue
        if abs(float(preset.values.get("thickness_mm", 2.0)) - thickness) <= 1e-9:
            return preset.id
    return CUSTOM_PRESET_ID


__all__ = [
    "BALANCED_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "HollowMeshPreset",
    "detect_hollow_preset",
    "get_hollow_preset",
    "hollow_preset_choices",
    "hollow_preset_note",
    "hollow_preset_values",
]
