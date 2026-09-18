# -*- coding: utf-8 -*-
from __future__ import annotations

from .feedback import HOLLOW_FEEDBACK_WINDOW_ID, build_hollow_feedback_window, selected_indices_text
from .preflight import HollowMeshCheck, triangle_count, validate_hollow_targets
from .presets import (
    BALANCED_PRESET_ID,
    CUSTOM_PRESET_ID,
    HollowMeshPreset,
    detect_hollow_preset,
    get_hollow_preset,
    hollow_preset_choices,
    hollow_preset_note,
    hollow_preset_values,
)
from .settings import HollowMeshSettings, hollow_settings_from_values

__all__ = [
    "BALANCED_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "HOLLOW_FEEDBACK_WINDOW_ID",
    "HollowMeshCheck",
    "HollowMeshPreset",
    "HollowMeshSettings",
    "build_hollow_feedback_window",
    "detect_hollow_preset",
    "get_hollow_preset",
    "hollow_preset_choices",
    "hollow_preset_note",
    "hollow_preset_values",
    "hollow_settings_from_values",
    "selected_indices_text",
    "triangle_count",
    "validate_hollow_targets",
]
