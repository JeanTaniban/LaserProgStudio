# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable

from ..app_context import AppContext
from .action_controller import WindowController
from .fabrication_preview_controller import FabricationPreviewController
from .modifier_preview_controller import ModifierPreviewController


FABRICATION_PREVIEW_METHODS = {
    "_lay_fusion_code",
    "_lay_pack_code",
    "generate_layflat_preview",
    "generate_joint_preview",
    "_clear_joint_selection_state",
    "update_joint_info",
}

MODIFIER_PREVIEW_METHODS = {
    "_mesh_triangle_count",
    "_clear_relief_modifier_preview_state",
    "_initialize_relief_modifier_from_selection",
    "_relief_target_index",
    "_relief_mode_code",
    "_relief_align_code",
    "_relief_font_family",
    "_on_relief_params_changed",
    "_set_relief_anchor_from_pick",
    "generate_relief_modifier_preview",
    "_clear_extrude_down_modifier_state",
    "_extrude_down_selected_indices",
    "_extrude_down_limits",
    "_suggested_extrude_down_plane_size",
    "_set_extrude_down_values_blocked",
    "_clamp_extrude_down_z",
    "_initialize_extrude_down_modifier_from_selection",
    "_extrude_down_plane_origin",
    "_sync_extrude_down_plane_actor",
    "_on_extrude_down_params_changed",
    "_schedule_extrude_down_preview",
    "_run_extrude_down_preview_if_current",
    "_update_extrude_down_report",
    "generate_extrude_down_modifier_preview",
    "_start_extrude_down_handle_drag",
    "_update_extrude_down_handle_drag",
    "_finish_extrude_down_handle_drag",
}


class ToolPreviewController(WindowController):
    """Route UI preview requests to focused preview controllers."""

    @classmethod
    def create(cls, context: AppContext) -> "ToolPreviewController":
        return cls(context)

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.fabrication = FabricationPreviewController.create(context)
        self.modifiers = ModifierPreviewController.create(context)

    def resolve(self, method_name: str) -> Callable:
        if method_name in FABRICATION_PREVIEW_METHODS:
            return getattr(self.fabrication, method_name)
        if method_name in MODIFIER_PREVIEW_METHODS:
            return getattr(self.modifiers, method_name)
        raise AttributeError(method_name)

    def call(self, method_name: str, *args, **kwargs):
        return self.resolve(method_name)(*args, **kwargs)
