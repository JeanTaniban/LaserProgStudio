# -*- coding: utf-8 -*-
from __future__ import annotations

from ..app_context import AppContext
from ..planar_tools import FixedPlanarView, PlanTraceAddKind, PlanarEditMode, PlanarPolygonDraft, VentPathDraft
from .action_controller import WindowController


class PlanarReportService(WindowController):
    """Right-panel status text for locked-plane tools."""

    @classmethod
    def create(cls, context: AppContext) -> "PlanarReportService":
        return cls(context)

    @property
    def state(self):
        return getattr(self.owner, "planar_tool_state", None)

    def update_report(self) -> None:
        state = self.state
        payload = getattr(state, "payload", None)
        view = getattr(state, "locked_view", None)
        plane = getattr(state, "locked_plane", None)
        view_label = view.value if isinstance(view, FixedPlanarView) else "—"
        depth = getattr(plane, "depth", 0.0) if plane is not None else 0.0
        try:
            if isinstance(payload, PlanarPolygonDraft):
                self._update_plan_report(payload, view_label=view_label, depth=float(depth))
            elif isinstance(payload, VentPathDraft):
                self._update_vent_report(payload, view_label=view_label)
            else:
                self._set_idle_reports()
        except Exception:
            pass

    def _update_plan_report(self, payload: PlanarPolygonDraft, *, view_label: str, depth: float) -> None:
        validation = payload.validation_result()
        segment = payload.selected_segment_index() if hasattr(payload, "selected_segment_index") else None
        curve_note = "no segment" if segment is None else f"seg {int(segment) + 1} R {getattr(payload, 'curve_radius', 0.0):.1f} / F {getattr(payload, 'curve_strength', 0.0):.2f}"
        mode = getattr(payload, "mode", PlanarEditMode.MOD)
        mode_label = "Modify"
        if mode is PlanarEditMode.ADD:
            add_kind = getattr(payload, "add_kind", PlanTraceAddKind.POLYGON)
            mode_label = {
                PlanTraceAddKind.POLYGON: "Add Polygon",
                PlanTraceAddKind.LINE: "Add Line",
                PlanTraceAddKind.SEMICIRCLE: "Add Semi-circle",
                PlanTraceAddKind.CIRCLE: "Add Circle",
            }.get(add_kind, "Add")
        staged = len(getattr(payload, "active_element_points", []) or [])
        element_count = len(getattr(payload, "elements", []) or [])
        selected = "yes" if getattr(payload, "has_selection", lambda: False)() else "no"
        snap_label = str(getattr(self.state, "snap_preview_label", "") or "")
        smart = bool(getattr(self.owner, "plan_trace_smart_snap_enabled", True))
        grid = bool(getattr(self.owner, "plan_trace_grid_snap_enabled", False))
        snap_note = f"snap: {snap_label}" if snap_label else f"snap: smart {'on' if smart else 'off'} / grid {'on' if grid else 'off'}"
        try:
            face_count = len(payload.closed_trace_regions())
        except Exception:
            face_count = 1 if bool(getattr(payload, "closed", False)) else 0
        text = (
            f"Locked view: {view_label} | mode: {mode_label} | polygon pts: {len(payload.points)} | "
            f"2D elements: {element_count} | faces: {face_count} | staged: {staged} | selected: {selected} | "
            f"closed: {'yes' if (payload.closed or face_count) else 'no'} | area: {payload.polygon_area():.1f} mm² | "
            f"{snap_note} | curve: {curve_note} | "
            f"plan={depth:.3f} | Apply: {'ready' if validation.ok else validation.message()}"
        )
        getattr(self.owner, "plan_trace_report").setText(text)

    def _update_vent_report(self, payload: VentPathDraft, *, view_label: str) -> None:
        metrics = payload.metrics()
        validation = payload.validation_result()
        warning = str(getattr(self.state, "last_edit_warning", "") or "")
        target_note = "" if metrics.target_delta is None else f" | target: {metrics.target_length:.1f} mm ({metrics.target_delta:+.1f} mm)"
        text = (
            f"Locked view: {view_label} | waypoints: {len(payload.waypoints)} | "
            f"length: {metrics.centerline_length:.1f} mm{target_note} | "
            f"inner: {metrics.inner_width:.1f} x {metrics.inner_height:.1f} mm | "
            f"outer: {metrics.outer_width:.1f} x {metrics.outer_height:.1f} mm | "
            f"EVT grid: {metrics.snap_grid_step:.2f} mm | "
            f"curve: R {metrics.curve_radius:.1f} mm / I {metrics.curve_strength:.2f} | "
            f"Fill area: {'yes' if metrics.fill_area else 'no'}{self._flare_note(payload)} | "
            f"Apply: {'ready' if validation.ok else validation.message()}"
            f"{(' | Clamp: ' + warning) if warning else ''}"
        )
        report_widget = getattr(self.owner, "vent_generator_report", None)
        if report_widget is not None:
            try:
                report_widget.setText(text)
            except Exception:
                pass
        tool_context = getattr(self.owner, "tool_context", None)
        inspector = getattr(tool_context, "inspector", None) if tool_context is not None else None
        try:
            if inspector is not None and getattr(getattr(inspector, "panel", None), "id", "") == "vent.generator":
                inspector.set_display_value("vent_report", text)
                if validation.ok:
                    inspector.clear_error("vent_report")
                else:
                    inspector.set_error("vent_report", validation.message())
        except Exception:
            pass

    def _flare_note(self, payload: VentPathDraft) -> str:
        if not payload.has_flare():
            return ""
        labels = {"none": "none", "start": "inlet", "end": "outlet", "both": "inlet+outlet"}
        requested = labels.get(payload.normalized_flare_side().value, payload.normalized_flare_side().value)
        active = labels.get(payload.effective_flare_side().value, payload.effective_flare_side().value)
        return f" | flare: {requested} x{payload.normalized_flare_factor():.2f} (active: {active})"

    def _set_idle_reports(self) -> None:
        if hasattr(self.owner, "plan_trace_report"):
            self.owner.plan_trace_report.setText("Open the tool to lock a planar view.")
        if hasattr(self.owner, "vent_generator_report"):
            self.owner.vent_generator_report.setText("Open the tool to lock a planar view.")
