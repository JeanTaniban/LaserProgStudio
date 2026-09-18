# -*- coding: utf-8 -*-
from __future__ import annotations


class ToolPreviewLayer:
    """Window-facing facade for preview generators owned by application controllers."""

    def _tool_preview_controller(self):
        controller = getattr(self, "tool_preview_controller", None)
        if controller is None:
            from ..application.tool_preview_controller import ToolPreviewController
            controller = ToolPreviewController.create(self.context)
            self.tool_preview_controller = controller
        return controller







    def _lay_fusion_code(self, *args, **kwargs):
        return self._tool_preview_controller().call("_lay_fusion_code", *args, **kwargs)

    def _lay_pack_code(self, *args, **kwargs):
        return self._tool_preview_controller().call("_lay_pack_code", *args, **kwargs)

    def generate_layflat_preview(self, *args, **kwargs):
        return self._tool_preview_controller().call("generate_layflat_preview", *args, **kwargs)

    def generate_joint_preview(self, *args, **kwargs):
        return self._tool_preview_controller().call("generate_joint_preview", *args, **kwargs)

    def _clear_joint_selection_state(self, *args, **kwargs):
        return self._tool_preview_controller().call("_clear_joint_selection_state", *args, **kwargs)

    def update_joint_info(self, *args, **kwargs):
        return self._tool_preview_controller().call("update_joint_info", *args, **kwargs)

    def _mesh_triangle_count(self, *args, **kwargs):
        return self._tool_preview_controller().call("_mesh_triangle_count", *args, **kwargs)

    def _clear_relief_modifier_preview_state(self, *args, **kwargs):
        return self._tool_preview_controller().call("_clear_relief_modifier_preview_state", *args, **kwargs)

    def _initialize_relief_modifier_from_selection(self, *args, **kwargs):
        return self._tool_preview_controller().call("_initialize_relief_modifier_from_selection", *args, **kwargs)

    def _relief_target_index(self, *args, **kwargs):
        return self._tool_preview_controller().call("_relief_target_index", *args, **kwargs)

    def _relief_mode_code(self, *args, **kwargs):
        return self._tool_preview_controller().call("_relief_mode_code", *args, **kwargs)

    def _relief_align_code(self, *args, **kwargs):
        return self._tool_preview_controller().call("_relief_align_code", *args, **kwargs)

    def _relief_font_family(self, *args, **kwargs):
        return self._tool_preview_controller().call("_relief_font_family", *args, **kwargs)

    def _on_relief_params_changed(self, *args, **kwargs):
        return self._tool_preview_controller().call("_on_relief_params_changed", *args, **kwargs)

    def _set_relief_anchor_from_pick(self, *args, **kwargs):
        try:
            from ..tooling.ids import TOOL_MOD_RELIEF
            from ..tooling.registry import get_studio_tool

            if getattr(self, "active_tool", None) == TOOL_MOD_RELIEF:
                tool = get_studio_tool(TOOL_MOD_RELIEF)
                context = getattr(self, "app_context", None) or getattr(self, "context", None)
                if tool is not None and hasattr(tool, "set_anchor_from_pick") and context is not None:
                    return tool.set_anchor_from_pick(context, *args, **kwargs)
        except Exception:
            pass
        return self._tool_preview_controller().call("_set_relief_anchor_from_pick", *args, **kwargs)

    def generate_relief_modifier_preview(self, *args, **kwargs):
        return self._tool_preview_controller().call("generate_relief_modifier_preview", *args, **kwargs)

    def _clear_extrude_down_modifier_state(self, *args, **kwargs):
        return self._tool_preview_controller().call("_clear_extrude_down_modifier_state", *args, **kwargs)

    def _extrude_down_selected_indices(self, *args, **kwargs):
        return self._tool_preview_controller().call("_extrude_down_selected_indices", *args, **kwargs)

    def _extrude_down_limits(self, *args, **kwargs):
        return self._tool_preview_controller().call("_extrude_down_limits", *args, **kwargs)

    def _suggested_extrude_down_plane_size(self, *args, **kwargs):
        return self._tool_preview_controller().call("_suggested_extrude_down_plane_size", *args, **kwargs)

    def _set_extrude_down_values_blocked(self, *args, **kwargs):
        return self._tool_preview_controller().call("_set_extrude_down_values_blocked", *args, **kwargs)

    def _clamp_extrude_down_z(self, *args, **kwargs):
        return self._tool_preview_controller().call("_clamp_extrude_down_z", *args, **kwargs)

    def _initialize_extrude_down_modifier_from_selection(self, *args, **kwargs):
        return self._tool_preview_controller().call("_initialize_extrude_down_modifier_from_selection", *args, **kwargs)

    def _extrude_down_plane_origin(self, *args, **kwargs):
        return self._tool_preview_controller().call("_extrude_down_plane_origin", *args, **kwargs)

    def _sync_extrude_down_plane_actor(self, *args, **kwargs):
        return self._tool_preview_controller().call("_sync_extrude_down_plane_actor", *args, **kwargs)

    def _on_extrude_down_params_changed(self, *args, **kwargs):
        return self._tool_preview_controller().call("_on_extrude_down_params_changed", *args, **kwargs)

    def _schedule_extrude_down_preview(self, *args, **kwargs):
        return self._tool_preview_controller().call("_schedule_extrude_down_preview", *args, **kwargs)

    def _run_extrude_down_preview_if_current(self, *args, **kwargs):
        return self._tool_preview_controller().call("_run_extrude_down_preview_if_current", *args, **kwargs)

    def _update_extrude_down_report(self, *args, **kwargs):
        return self._tool_preview_controller().call("_update_extrude_down_report", *args, **kwargs)

    def generate_extrude_down_modifier_preview(self, *args, **kwargs):
        return self._tool_preview_controller().call("generate_extrude_down_modifier_preview", *args, **kwargs)

    def _start_extrude_down_handle_drag(self, *args, **kwargs):
        return self._tool_preview_controller().call("_start_extrude_down_handle_drag", *args, **kwargs)

    def _update_extrude_down_handle_drag(self, *args, **kwargs):
        return self._tool_preview_controller().call("_update_extrude_down_handle_drag", *args, **kwargs)

    def _finish_extrude_down_handle_drag(self, *args, **kwargs):
        return self._tool_preview_controller().call("_finish_extrude_down_handle_drag", *args, **kwargs)
