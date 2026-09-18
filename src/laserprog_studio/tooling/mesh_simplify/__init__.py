# -*- coding: utf-8 -*-
from __future__ import annotations

from .feedback import SIMPLIFY_FEEDBACK_WINDOW_ID, build_simplify_feedback_window, selected_indices_text
from .preflight import SimplifyMeshCheck, triangle_count, validate_simplify_targets
from .presets import (
    BALANCED_PRESET_ID,
    CUSTOM_PRESET_ID,
    SimplifyMeshPreset,
    detect_simplify_preset,
    get_simplify_preset,
    simplify_preset_choices,
    simplify_preset_note,
    simplify_preset_values,
)
from .settings import SimplifyMeshSettings, simplify_settings_from_values

__all__ = [
    "BALANCED_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "SIMPLIFY_FEEDBACK_WINDOW_ID",
    "SimplifyMeshCheck",
    "SimplifyMeshPreset",
    "SimplifyMeshSettings",
    "build_simplify_feedback_window",
    "detect_simplify_preset",
    "get_simplify_preset",
    "selected_indices_text",
    "simplify_preset_choices",
    "simplify_preset_note",
    "simplify_preset_values",
    "simplify_settings_from_values",
    "triangle_count",
    "validate_simplify_targets",
]
