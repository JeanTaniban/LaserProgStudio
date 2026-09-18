# -*- coding: utf-8 -*-
from __future__ import annotations

from .panel import build_vent_generator_panel
from .settings import VentGeneratorSettings, apply_settings_to_payload, settings_from_payload, vent_report_text
from .workflow import VentRouteMachine, VentRouteResult, vent_route_summary, vent_selected_point_text
from .feedback import VentFeedbackSnapshot, clear_vent_creator_visuals, overlay_action_from_button, overlay_mode_from_button, sync_vent_feedback, sync_vent_route_visuals
from .apply_validation import VentApplyCheck, preflight_vent_apply_mesh, validate_vent_apply_payload, vent_mesh_kind
from .presets import CUSTOM_PRESET_ID, PRESET_CHOICES, VENT_GENERATOR_PRESETS, VentGeneratorPreset, values_for_vent_preset, vent_preset_description
from .snap import VentRouteSnapResult, snap_vent_route_point, vent_route_alignment_targets
from .diagnostics import export_vent_timings, vent_perf_summary_text
from .acoustics import VentAcousticEstimate, estimate_vent_acoustics

__all__ = [
    "CUSTOM_PRESET_ID",
    "PRESET_CHOICES",
    "VENT_GENERATOR_PRESETS",
    "VentGeneratorPreset",
    "VentGeneratorSettings",
    "VentAcousticEstimate",
    "VentFeedbackSnapshot",
    "VentRouteMachine",
    "VentRouteResult",
    "VentRouteSnapResult",
    "clear_vent_creator_visuals",
    "export_vent_timings",
    "apply_settings_to_payload",
    "VentApplyCheck",
    "build_vent_generator_panel",
    "preflight_vent_apply_mesh",
    "validate_vent_apply_payload",
    "vent_mesh_kind",
    "values_for_vent_preset",
    "vent_preset_description",
    "overlay_action_from_button",
    "overlay_mode_from_button",
    "settings_from_payload",
    "sync_vent_feedback",
    "snap_vent_route_point",
    "sync_vent_route_visuals",
    "vent_route_alignment_targets",
    "vent_perf_summary_text",
    "estimate_vent_acoustics",
    "vent_report_text",
    "vent_route_summary",
    "vent_selected_point_text",
]
