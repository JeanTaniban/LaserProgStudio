# -*- coding: utf-8 -*-
from __future__ import annotations

from .planar_tool_deps import *  # noqa: F401,F403

class PlanarToolPayloadLayer:

    def _make_plan_trace_payload(self, plane: LockedPlaneSpec | None = None) -> PlanarPolygonDraft:
        target_plane = plane or getattr(self.state, "locked_plane", None) or plane_from_first_hit(FixedPlanarView.TOP)
        depth = 10.0
        try:
            depth = max(float(getattr(getattr(self.owner, "plan_trace_depth", None), "value")()), 0.001)
        except Exception:
            pass
        return PlanarPolygonDraft(target_plane, extrusion_depth=depth)

    def _make_vent_payload(self, plane: LockedPlaneSpec | None = None) -> VentPathDraft:
        target_plane = plane or getattr(self.state, "locked_plane", None) or plane_from_first_hit(FixedPlanarView.TOP)
        payload = VentPathDraft(target_plane)
        self.sync_payload_settings_from_ui(payload)
        return payload

    def sync_payload_settings_from_ui(self, payload: Any | None = None) -> None:
        payload = getattr(self.state, "payload", None) if payload is None else payload
        if isinstance(payload, PlanarPolygonDraft):
            try:
                payload.extrusion_depth = max(float(self.owner.plan_trace_depth.value()), 0.001)
            except Exception:
                pass
            try:
                radius_widget = getattr(self.owner, "plan_trace_curve_radius", None)
                payload.curve_radius = max(float(radius_widget.value()) if radius_widget is not None else float(payload.curve_radius), 0.0)
            except Exception:
                pass
            try:
                strength_widget = getattr(self.owner, "plan_trace_curve_strength", None)
                payload.curve_strength = max(-1.0, min(1.0, float(strength_widget.value()) if strength_widget is not None else float(payload.curve_strength)))
            except Exception:
                pass
            try:
                mode = getattr(payload, "mode", PlanarEditMode.ADD)
                if not isinstance(mode, PlanarEditMode):
                    mode = PlanarEditMode(str(mode))
                if mode is PlanarEditMode.MOD and getattr(payload, "selected_index", None) is not None:
                    payload.set_selected_segment_curve(radius=float(payload.curve_radius), strength=float(payload.curve_strength))
            except Exception:
                pass
            return
        if not isinstance(payload, VentPathDraft):
            return
        try:
            from ..tooling.vent_generator import VentGeneratorSettings, apply_settings_to_payload

            settings_values = getattr(self.owner, "vent_generator_settings", None)
            settings = VentGeneratorSettings.from_values(settings_values if isinstance(settings_values, dict) else {})
            apply_settings_to_payload(payload, settings)
        except Exception:
            pass
        try:
            # Curves are edited from MOD on the selected waypoint/segment.
            mode = getattr(payload, "mode", PlanarEditMode.ADD)
            if not isinstance(mode, PlanarEditMode):
                mode = PlanarEditMode(str(mode))
            if mode is PlanarEditMode.MOD and getattr(payload, "selected_index", None) is not None:
                payload.set_selected_segment_curve(radius=float(payload.curve_radius), strength=float(payload.curve_strength))
        except Exception:
            pass

    def initialize_plan_trace_tool(self) -> None:
        plane = self.begin_locked_planar_tool(TOOL_PLAN_TRACE)
        self.set_payload(self._make_plan_trace_payload(plane))
        self.rebuild_plan_trace_scene_snap_cache()
        self.clear_preview_actors(render=False)
        self._sync_planar_mode_buttons(PlanarEditMode.MOD.value)
        self._sync_plan_trace_action_buttons()
        self.update_planar_tool_report()
        self.draw_planar_preview(render=True)

    def initialize_vent_generator_tool(self) -> None:
        plane = self.begin_locked_planar_tool(TOOL_VENT_GENERATOR)
        self.set_payload(self._make_vent_payload(plane))
        self.rebuild_vent_scene_snap_cache()
        self.clear_preview_actors(render=False)
        self.update_planar_tool_report()
        self.draw_planar_preview(render=True)

    def set_payload_mode(self, mode: str) -> None:
        payload = getattr(self.state, "payload", None)
        if isinstance(payload, PlanarPolygonDraft):
            self.set_plan_trace_mode(mode)
            return
        if hasattr(payload, "set_mode"):
            payload.set_mode(mode)
        state = self.state
        if state is not None:
            state.pointer_drag_active = False
            state.pointer_drag_mode = None
            state.pending_plane_point = None
            self._set_planar_edit_warning("")
            self._clear_planar_snap_preview()
        if str(mode).upper() == PlanarEditMode.RST.value:
            self._sync_planar_mode_buttons(PlanarEditMode.ADD.value)
        self.sync_selected_point_to_transform_fields()
        self.refresh_generated_preview_if_ready()
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()
        self._update_preview_button_state()

    def set_plan_trace_mode(self, mode: str) -> None:
        payload = getattr(self.state, "payload", None)
        if not isinstance(payload, PlanarPolygonDraft):
            return
        raw = str(mode or "MOD").strip().upper()
        add_map = {
            "ADD": PlanTraceAddKind.POLYGON,
            "POLYGON": PlanTraceAddKind.POLYGON,
            "LINE": PlanTraceAddKind.LINE,
            "TRAIT": PlanTraceAddKind.LINE,
            "SEMICIRCLE": PlanTraceAddKind.SEMICIRCLE,
            "DEMI_CERCLE": PlanTraceAddKind.SEMICIRCLE,
            "ARC": PlanTraceAddKind.SEMICIRCLE,
            "CIRCLE": PlanTraceAddKind.CIRCLE,
        }
        state = self.state
        if state is not None:
            state.pointer_drag_active = False
            state.pointer_drag_mode = None
            state.pending_plane_point = None
            self._set_planar_edit_warning("")
            self._clear_planar_snap_preview()
        if raw in {"RST", "RESET"}:
            self.reset_payload()
            return
        if raw in {"SUPP", "DELETE", "DEL"}:
            self.delete_plan_trace_selection()
            return
        if raw in add_map:
            kind = add_map[raw]
            same_add_button = getattr(payload, "mode", PlanarEditMode.MOD) is PlanarEditMode.ADD and getattr(payload, "add_kind", PlanTraceAddKind.POLYGON) is kind
            if same_add_button:
                payload.set_mode(PlanarEditMode.MOD)
                payload.add_kind = kind
            else:
                payload.set_add_kind(kind)
        else:
            payload.set_mode(PlanarEditMode.MOD)
        self.sync_selected_point_to_transform_fields()
        self.refresh_generated_preview_if_ready()
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()
        self._update_preview_button_state()
        self._sync_planar_mode_buttons(getattr(payload, "mode", PlanarEditMode.MOD).value)
        self._sync_plan_trace_action_buttons()

    def exit_plan_trace_add_mode(self) -> bool:
        payload = getattr(self.state, "payload", None)
        if not isinstance(payload, PlanarPolygonDraft):
            return False
        payload.set_mode(PlanarEditMode.MOD)
        state = self.state
        if state is not None:
            state.pointer_drag_active = False
            state.pointer_drag_mode = None
            state.pending_plane_point = None
            self._set_planar_edit_warning("")
            self._clear_planar_snap_preview()
        self.sync_selected_point_to_transform_fields()
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()
        self._sync_planar_mode_buttons(PlanarEditMode.MOD.value)
        self._sync_plan_trace_action_buttons()
        return True

    def delete_plan_trace_selection(self) -> bool:
        payload = getattr(self.state, "payload", None)
        if not isinstance(payload, PlanarPolygonDraft):
            return False
        deleted = bool(payload.delete_selected())
        if deleted:
            self._set_planar_edit_warning("")
            self.refresh_generated_preview_if_ready()
            self.draw_planar_preview(render=True)
            self.update_planar_tool_report()
            self._update_preview_button_state()
        self._sync_plan_trace_action_buttons()
        return deleted

    def _sync_plan_trace_action_buttons(self) -> None:
        payload = getattr(self.state, "payload", None)
        selected = bool(isinstance(payload, PlanarPolygonDraft) and payload.has_selection())
        btn = getattr(self.owner, "plan_trace_delete_selection", None)
        if btn is not None:
            try:
                btn.setEnabled(selected)
            except Exception:
                pass

    def reset_payload(self) -> None:
        payload = getattr(self.state, "payload", None)
        if hasattr(payload, "reset"):
            payload.reset()
        state = self.state
        if state is not None:
            state.pointer_drag_active = False
            state.pointer_drag_mode = None
            state.pending_plane_point = None
            self._set_planar_edit_warning("")
            self._clear_planar_snap_preview()
        if self.owner.mesh_store is not None and self.owner.mesh_store.has_preview:
            try:
                self.owner.discard_preview_only("planar reset")
            except Exception:
                pass
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()
        self._update_preview_button_state()

    def on_payload_settings_changed(self) -> None:
        self.sync_payload_settings_from_ui()
        self.refresh_generated_preview_if_ready()
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()
        self._update_preview_button_state()


