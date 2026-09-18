# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CUSTOM_PRESET_ID = "custom"
BALANCED_PRESET_ID = "balanced"


@dataclass(frozen=True, slots=True)
class SimplifyMeshPreset:
    id: str
    label: str
    note: str
    values: dict[str, Any]


_PRESETS: tuple[SimplifyMeshPreset, ...] = (
    SimplifyMeshPreset(CUSTOM_PRESET_ID, "Custom", "Manual simplify settings.", {}),
    SimplifyMeshPreset(
        "light_cleanup",
        "Light cleanup",
        "Small reduction for dense imported parts where shape fidelity matters most.",
        {"reduction_percent": 25.0, "preserve_topology": True},
    ),
    SimplifyMeshPreset(
        BALANCED_PRESET_ID,
        "Balanced optimization",
        "Recommended default for cleaner files, faster preview and safe geometry edits.",
        {"reduction_percent": 50.0, "preserve_topology": True},
    ),
    SimplifyMeshPreset(
        "viewport_proxy",
        "Viewport proxy",
        "Strong visual simplification for heavy scans or temporary viewport work.",
        {"reduction_percent": 75.0, "preserve_topology": False},
    ),
    SimplifyMeshPreset(
        "print_safe",
        "Print-safe reduce",
        "Conservative topology-preserving reduction before boolean or print checks.",
        {"reduction_percent": 35.0, "preserve_topology": True},
    ),
)

_PRESET_BY_ID = {preset.id: preset for preset in _PRESETS}


def simplify_preset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((preset.id, preset.label) for preset in _PRESETS)


def get_simplify_preset(preset_id: str | None) -> SimplifyMeshPreset:
    return _PRESET_BY_ID.get(str(preset_id or ""), _PRESET_BY_ID[CUSTOM_PRESET_ID])


def simplify_preset_values(preset_id: str | None) -> dict[str, Any]:
    return dict(get_simplify_preset(preset_id).values)


def simplify_preset_note(preset_id: str | None) -> str:
    return get_simplify_preset(preset_id).note


def detect_simplify_preset(values: dict[str, Any]) -> str:
    try:
        reduction = float(values.get("reduction_percent", 50.0))
    except Exception:
        reduction = 50.0
    preserve = bool(values.get("preserve_topology", True))
    for preset in _PRESETS:
        if preset.id == CUSTOM_PRESET_ID:
            continue
        preset_values = preset.values
        if abs(float(preset_values.get("reduction_percent", 50.0)) - reduction) <= 1e-9 and bool(preset_values.get("preserve_topology", True)) == preserve:
            return preset.id
    return CUSTOM_PRESET_ID


__all__ = [
    "BALANCED_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "SimplifyMeshPreset",
    "detect_simplify_preset",
    "get_simplify_preset",
    "simplify_preset_choices",
    "simplify_preset_note",
    "simplify_preset_values",
]
