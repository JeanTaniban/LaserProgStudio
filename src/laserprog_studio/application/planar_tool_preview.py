# -*- coding: utf-8 -*-
from __future__ import annotations

from .planar_tool_deps import *  # noqa: F401,F403

class PlanarToolPreviewLayer:

    @property
    def preview_service(self) -> PlanarPreviewService:
        service = getattr(self, "_planar_preview_service", None)
        if service is None:
            service = PlanarPreviewService.create(self.context)
            setattr(self, "_planar_preview_service", service)
        return service

    def clear_preview_actors(self, *, render: bool = False, interactive_only: bool = False) -> None:
        self.preview_service.clear_preview_actors(render=render, interactive_only=interactive_only)

    def draw_planar_preview(self, *, render: bool = False, lightweight: bool = False) -> None:
        payload = getattr(self.state, "payload", None)
        if isinstance(payload, VentPathDraft):
            ctx = getattr(self.context, "tool_context", None) or getattr(self.owner, "tool_context", None)
            if ctx is not None:
                try:
                    from laserprog_studio.tooling.vent_generator import sync_vent_route_visuals

                    changed_indices = None
                    if lightweight:
                        mode = getattr(payload, "mode", None)
                        try:
                            from laserprog_studio.planar_tools import PlanarEditMode

                            if not isinstance(mode, PlanarEditMode):
                                mode = PlanarEditMode(str(mode))
                            if mode is PlanarEditMode.MOD and getattr(payload, "selected_index", None) is not None:
                                changed_indices = (int(payload.selected_index),)
                            else:
                                # ADD hover/drag only moves the Plan2D cursor and
                                # pending link; existing route actors are stable.
                                changed_indices = ()
                        except Exception:
                            changed_indices = ()
                    sync_vent_route_visuals(
                        ctx,
                        payload,
                        state=self.state,
                        render=bool(render),
                        full=not bool(lightweight),
                        changed_indices=changed_indices,
                        position_only=bool(lightweight),
                    )
                except Exception:
                    pass
            if lightweight:
                return
        self.preview_service.draw_planar_preview(render=render, lightweight=lightweight)

    def refresh_generated_preview_if_ready(self, *, for_apply: bool = False) -> bool:
        payload = getattr(self.state, "payload", None)
        if payload is None:
            return False
        self.sync_payload_settings_from_ui(payload)
        try:
            base_meshes = [copy.deepcopy(m) for m in self.owner.committed_meshes()]
            generated = None
            reason = ""
            if isinstance(payload, PlanarPolygonDraft) and payload.is_ready_for_extrusion():
                generated = make_extruded_polygon_mesh(payload)
                reason = "Plan tracer extrusion preview"
            elif isinstance(payload, VentPathDraft):
                # EVT preview is intentionally lightweight: no generated mesh is
                # staged while editing.  The mesh is built only on Apply.
                if not bool(for_apply):
                    if self.owner.mesh_store is not None and self.owner.mesh_store.has_preview:
                        self.owner.discard_preview_only("EVT lightweight preview")
                    self._update_preview_button_state()
                    return False
                if payload.is_ready_for_mesh():
                    generated = make_vent_path_mesh(payload)
                    reason = "Vent generator apply"
            if generated is not None:
                self.owner.set_preview_meshes(base_meshes + [generated], reason)
                return True
            if self.owner.mesh_store is not None and self.owner.mesh_store.has_preview:
                self.owner.discard_preview_only("planar draft not ready")
        except Exception as exc:
            log_exception("refresh_planar_generated_preview")
            try:
                _qmessagebox().warning(self.owner, "Planar tool", str(exc))
            except Exception:
                pass
        return False

    def has_applyable_draft(self) -> bool:
        payload = getattr(self.state, "payload", None)
        try:
            self.sync_payload_settings_from_ui(payload)
        except Exception:
            pass
        if isinstance(payload, VentPathDraft):
            return bool(payload.is_ready_for_mesh())
        if isinstance(payload, PlanarPolygonDraft):
            return bool(payload.is_ready_for_extrusion())
        return False

    def ensure_preview_before_apply(self) -> bool:
        if not self.is_active_planar_tool():
            return False
        if self.owner.has_preview():
            return True
        return self.refresh_generated_preview_if_ready(for_apply=True)

    def sync_plan_curve_fields_from_payload(self, payload: PlanarPolygonDraft | None = None) -> None:
        payload = getattr(self.state, "payload", None) if payload is None else payload
        if not isinstance(payload, PlanarPolygonDraft):
            return
        segment = payload.selected_segment_index() if hasattr(payload, "selected_segment_index") else None
        if segment is None:
            values = {"plan_trace_curve_radius": 0.0, "plan_trace_curve_strength": 0.0}
            enabled = False
            label = "Curve: select a MOD point"
        else:
            payload._sync_curve_offsets()
            radius = float(payload.segment_curve_radii[int(segment)]) if int(segment) < len(payload.segment_curve_radii) else 0.0
            strength = float(payload.segment_curve_strengths[int(segment)]) if int(segment) < len(payload.segment_curve_strengths) else 0.0
            values = {"plan_trace_curve_radius": max(radius, 0.0), "plan_trace_curve_strength": max(-1.0, min(1.0, strength))}
            enabled = True
            label = f"Curve segment {int(segment) + 1}: point selected"
            payload.curve_radius = values["plan_trace_curve_radius"]
            payload.curve_strength = values["plan_trace_curve_strength"]
        for attr, value in values.items():
            widget = getattr(self.owner, attr, None)
            if widget is None:
                continue
            try:
                blocked = bool(widget.blockSignals(True))
                widget.setValue(float(value))
                widget.setEnabled(bool(enabled))
                widget.blockSignals(blocked)
            except Exception:
                try:
                    widget.blockSignals(False)
                except Exception:
                    pass
        for attr, value in (("plan_trace_curve_radius_slider", values["plan_trace_curve_radius"]), ("plan_trace_curve_strength_slider", values["plan_trace_curve_strength"])):
            slider = getattr(self.owner, attr, None)
            if slider is None:
                continue
            try:
                blocked = bool(slider.blockSignals(True))
                if attr.endswith("radius_slider"):
                    slider.setValue(int(round(max(float(value), 0.0) * 10.0)))
                else:
                    slider.setValue(int(round(max(-1.0, min(1.0, float(value))) * 100.0)))
                slider.setEnabled(bool(enabled))
                slider.blockSignals(blocked)
            except Exception:
                try:
                    slider.blockSignals(False)
                except Exception:
                    pass
        label_widget = getattr(self.owner, "plan_trace_selected_segment_label", None)
        if label_widget is not None:
            try:
                label_widget.setText(label)
            except Exception:
                pass

    def sync_vent_curve_fields_from_payload(self, payload: VentPathDraft | None = None) -> None:
        payload = getattr(self.state, "payload", None) if payload is None else payload
        if not isinstance(payload, VentPathDraft):
            return
        segment = payload.selected_segment_index()
        if segment is None:
            values = {"vent_curve_radius": 0.0, "vent_curve_strength": 0.0}
            enabled = False
            label = "Curve: select a MOD point"
        else:
            payload._sync_curve_offsets()
            radius = float(payload.segment_curve_radii[int(segment)]) if int(segment) < len(payload.segment_curve_radii) else 0.0
            strength = float(payload.segment_curve_strengths[int(segment)]) if int(segment) < len(payload.segment_curve_strengths) else 0.0
            values = {"vent_curve_radius": max(radius, 0.0), "vent_curve_strength": max(-1.0, min(1.0, strength))}
            enabled = True
            label = f"Curve segment {int(segment) + 1}: point selected"
            payload.curve_radius = values["vent_curve_radius"]
            payload.curve_strength = values["vent_curve_strength"]
        settings = getattr(self.owner, "vent_generator_settings", None)
        if isinstance(settings, dict):
            settings.update({key: float(value) for key, value in values.items()})
        tool_context = getattr(self.owner, "tool_context", None)
        inspector = getattr(tool_context, "inspector", None) if tool_context is not None else None
        try:
            if inspector is not None and getattr(getattr(inspector, "panel", None), "id", "") == "vent.generator":
                for field_id, value in values.items():
                    inspector.update_value(field_id, float(value), notify=False)
                    inspector.update_field_state(field_id, enabled=bool(enabled), visible=True)
        except Exception:
            pass
        for attr, value in values.items():
            widget = getattr(self.owner, attr, None)
            if widget is None:
                continue
            try:
                blocked = bool(widget.blockSignals(True))
                widget.setValue(float(value))
                widget.setEnabled(bool(enabled))
                widget.blockSignals(blocked)
            except Exception:
                try:
                    widget.blockSignals(False)
                except Exception:
                    pass
        for attr, value in (("vent_curve_radius_slider", values["vent_curve_radius"]), ("vent_curve_strength_slider", values["vent_curve_strength"])):
            slider = getattr(self.owner, attr, None)
            if slider is None:
                continue
            try:
                blocked = bool(slider.blockSignals(True))
                if attr.endswith("radius_slider"):
                    slider.setValue(int(round(max(float(value), 0.0) * 10.0)))
                else:
                    slider.setValue(int(round(max(-1.0, min(1.0, float(value))) * 100.0)))
                slider.setEnabled(bool(enabled))
                slider.blockSignals(blocked)
            except Exception:
                try:
                    slider.blockSignals(False)
                except Exception:
                    pass
        label_widget = getattr(self.owner, "vent_selected_segment_label", None)
        if label_widget is not None:
            try:
                label_widget.setText(label)
            except Exception:
                pass

    def sync_selected_point_to_transform_fields(self) -> None:
        payload = getattr(self.state, "payload", None)
        if payload is None:
            return
        idx = getattr(payload, "selected_index", None)
        try:
            if idx is None and isinstance(payload, PlanarPolygonDraft):
                eidx = getattr(payload, "selected_element_index", None)
                pidx = getattr(payload, "selected_element_point_index", None)
                if eidx is not None and pidx is not None and 0 <= int(eidx) < len(payload.elements):
                    element = payload.elements[int(eidx)]
                    if 0 <= int(pidx) < len(element.points):
                        point = element.points[int(pidx)]
                        world = plane_to_world(payload.plane, point[0], point[1])
                    else:
                        self.sync_plan_curve_fields_from_payload(payload)
                        return
                else:
                    self.sync_plan_curve_fields_from_payload(payload)
                    return
            elif idx is None:
                if isinstance(payload, VentPathDraft):
                    self.sync_vent_curve_fields_from_payload(payload)
                return
            else:
                source = getattr(payload, "points", getattr(payload, "waypoints", []))
                if not (0 <= int(idx) < len(source)):
                    return
                world = plane_to_world(payload.plane, source[int(idx)][0], source[int(idx)][1])
            previous = bool(getattr(self.owner, "_updating_transform_fields", False))
            self.owner._updating_transform_fields = True
            try:
                self.owner.pos_x.setValue(float(world[0]))
                self.owner.pos_y.setValue(float(world[1]))
                self.owner.pos_z.setValue(float(world[2]))
            finally:
                self.owner._updating_transform_fields = previous
            if isinstance(payload, VentPathDraft):
                self.sync_vent_curve_fields_from_payload(payload)
            elif isinstance(payload, PlanarPolygonDraft):
                self.sync_plan_curve_fields_from_payload(payload)
        except Exception:
            log_exception("sync_planar_selected_point_fields")

    def _sync_planar_mode_buttons(self, mode: str) -> None:
        active_tool = getattr(self.state, "active_tool_id", None)
        if active_tool == TOOL_PLAN_TRACE:
            payload = getattr(self.state, "payload", None)
            active_label = "mod"
            if isinstance(payload, PlanarPolygonDraft) and getattr(payload, "mode", PlanarEditMode.MOD) is PlanarEditMode.ADD:
                kind = getattr(payload, "add_kind", PlanTraceAddKind.POLYGON)
                active_label = {
                    PlanTraceAddKind.POLYGON: "polygon",
                    PlanTraceAddKind.LINE: "line",
                    PlanTraceAddKind.SEMICIRCLE: "semicircle",
                    PlanTraceAddKind.CIRCLE: "circle",
                }.get(kind, "polygon")
            for label in ("mod", "polygon", "line", "semicircle", "circle"):
                button = getattr(self.owner, f"plan_trace_mode_{label}", None)
                if button is None:
                    continue
                try:
                    blocked = bool(button.blockSignals(True))
                    button.setChecked(label == active_label)
                    button.blockSignals(blocked)
                except Exception:
                    pass
            self._sync_plan_trace_action_buttons()
            return
        prefix = "vent_generator"
        for label in ("add", "mod", "supp", "rst"):
            button = getattr(self.owner, f"{prefix}_mode_{label}", None)
            if button is None:
                continue
            try:
                blocked = bool(button.blockSignals(True))
                button.setChecked(label.upper() == str(mode).upper())
                button.blockSignals(blocked)
            except Exception:
                pass

    @property
    def report_service(self) -> PlanarReportService:
        service = getattr(self, "_planar_report_service", None)
        if service is None:
            service = PlanarReportService.create(self.context)
            setattr(self, "_planar_report_service", service)
        return service

    def update_planar_tool_report(self) -> None:
        self.report_service.update_report()

# Transitional import alias; the concrete implementation is a Layer, not a mixin class.
PlanarToolPreviewLayer = PlanarToolPreviewLayer

