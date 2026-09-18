# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CUSTOM_PRESET_ID = "custom"
BALANCED_PRESET_ID = "balanced"


@dataclass(frozen=True, slots=True)
class RepairMeshPreset:
    id: str
    label: str
    note: str
    values: dict[str, Any]


_PRESETS: tuple[RepairMeshPreset, ...] = (
    RepairMeshPreset(
        CUSTOM_PRESET_ID,
        "Custom",
        "Manual repair settings.",
        {},
    ),
    RepairMeshPreset(
        "safe_scan_cleanup",
        "Safe scan cleanup",
        "Conservative cleanup for scanned/imported parts. Keeps detail while removing obvious defects.",
        {"tolerance_mm": 0.005, "fill_holes": False, "remove_tiny_faces": True},
    ),
    RepairMeshPreset(
        BALANCED_PRESET_ID,
        "Balanced repair",
        "Recommended default: merge close vertices, remove tiny faces and try to close small holes.",
        {"tolerance_mm": 0.01, "fill_holes": True, "remove_tiny_faces": True},
    ),
    RepairMeshPreset(
        "aggressive_print_fix",
        "Aggressive print fix",
        "Stronger cleanup for broken STL/3MF parts before boolean or print operations.",
        {"tolerance_mm": 0.05, "fill_holes": True, "remove_tiny_faces": True},
    ),
    RepairMeshPreset(
        "surface_preserve",
        "Surface preserve",
        "Keeps open design surfaces and avoids hole filling. Useful for panels or deliberate shells.",
        {"tolerance_mm": 0.002, "fill_holes": False, "remove_tiny_faces": False},
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def repair_preset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((preset.id, preset.label) for preset in _PRESETS)


def get_repair_preset(preset_id: str | None) -> RepairMeshPreset:
    return _PRESET_BY_ID.get(str(preset_id or ""), _PRESET_BY_ID[CUSTOM_PRESET_ID])


def repair_preset_values(preset_id: str | None) -> dict[str, Any]:
    return dict(get_repair_preset(preset_id).values)


def repair_preset_note(preset_id: str | None) -> str:
    return get_repair_preset(preset_id).note


def detect_repair_preset(values: dict[str, Any]) -> str:
    """Return the matching preset id, or Custom when manual values diverge."""

    try:
        tolerance = float(values.get("tolerance_mm", 0.01))
    except Exception:
        tolerance = 0.01
    fill_holes = bool(values.get("fill_holes", True))
    tiny = bool(values.get("remove_tiny_faces", True))
    for preset in _PRESETS:
        if preset.id == CUSTOM_PRESET_ID:
            continue
        preset_values = preset.values
        if abs(float(preset_values.get("tolerance_mm", 0.01)) - tolerance) <= 1e-9 and bool(preset_values.get("fill_holes", True)) == fill_holes and bool(preset_values.get("remove_tiny_faces", True)) == tiny:
            return preset.id
    return CUSTOM_PRESET_ID


__all__ = [
    "BALANCED_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "RepairMeshPreset",
    "detect_repair_preset",
    "get_repair_preset",
    "repair_preset_choices",
    "repair_preset_note",
    "repair_preset_values",
]
