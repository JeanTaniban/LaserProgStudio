# -*- coding: utf-8 -*-
from __future__ import annotations

from .planar_tool_deps import *  # noqa: F401,F403

class PlanarToolInteractionLayer:

    @property
    def pick_service(self) -> PlanarPickService:
        service = getattr(self, "_planar_pick_service", None)
        if service is None:
            service = PlanarPickService.create(self.context)
            setattr(self, "_planar_pick_service", service)
        return service

    def _resolve_first_point_depth_if_needed(self, qx: float, qy: float) -> None:
        state = self.state
        payload = getattr(state, "payload", None)
        if state is None or bool(getattr(state, "first_point_depth_resolved", False)):
            return
        point_count = len(getattr(payload, "points", getattr(payload, "waypoints", [])))
        if point_count > 0:
            state.first_point_depth_resolved = True
            return
        hit = self.pick_service.first_mesh_hit_from_qt_pos(qx, qy)
        if hit is not None and state.locked_view is not None:
            plane = plane_from_first_hit(state.locked_view, hit)
            state.locked_plane = plane
            if hasattr(payload, "plane"):
                payload.plane = plane
            if isinstance(payload, PlanarPolygonDraft):
                self.rebuild_plan_trace_scene_snap_cache()
            elif isinstance(payload, VentPathDraft):
                self.rebuild_vent_scene_snap_cache()
            self.ui_log(f"[PLANAR] First point depth from hit: {plane.depth:.3f}")
        state.first_point_depth_resolved = True

    def _nearest_tolerance(self) -> float:
        cfg = self.snap_config_from_owner()
        return max(float(cfg.smart_snap_tolerance) * 3.0, float(cfg.grid_step) * 0.75, 3.0)

    def _set_planar_edit_warning(self, message: str = "", *, raw_point: tuple[float, float] | None = None) -> None:
        state = self.state
        if state is None:
            return
        state.last_edit_warning = str(message or "")
        state.last_pointer_raw_plane = raw_point

    def _clear_planar_snap_preview(self) -> None:
        state = self.state
        if state is None:
            return
        try:
            state.snap_preview_plane_point = None
            state.snap_preview_raw_plane = None
            state.snap_preview_label = ""
        except Exception:
            pass

    def _record_planar_snap_preview(self, result: PlanarPointerResult | None) -> None:
        state = self.state
        if state is None:
            return
        label = str(getattr(result, "snap_label", "") or "") if result is not None else ""
        try:
            if result is not None and label:
                state.snap_preview_plane_point = (float(result.snapped_plane[0]), float(result.snapped_plane[1]))
                state.snap_preview_raw_plane = (float(result.raw_plane[0]), float(result.raw_plane[1]))
                state.snap_preview_label = label
            else:
                self._clear_planar_snap_preview()
        except Exception:
            self._clear_planar_snap_preview()

    def _constrain_polygon_candidate(
        self,
        payload: PlanarPolygonDraft,
        point: tuple[float, float],
        *,
        index: int | None = None,
        anchor: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        result = payload.clamp_point_candidate(
            point,
            index=index,
            anchor=anchor,
        )
        if result.was_clamped:
            self._set_planar_edit_warning(result.message or "point clamped to avoid self-intersection", raw_point=result.raw_point)
        elif not result.valid:
            self._set_planar_edit_warning(result.message or "invalid position", raw_point=result.raw_point)
        else:
            self._set_planar_edit_warning("")
        return result.point

    def _constrain_vent_candidate(
        self,
        payload: VentPathDraft,
        point: tuple[float, float],
        *,
        index: int | None = None,
        anchor: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        result = payload.clamp_waypoint_candidate(
            point,
            index=index,
            anchor=anchor,
        )
        if not result.valid:
            self._set_planar_edit_warning(result.message or "invalid position", raw_point=result.raw_point)
        else:
            self._set_planar_edit_warning("")
        return result.point

    def _constrained_plane_point_for_payload(
        self,
        payload: Any,
        point: tuple[float, float],
        *,
        index: int | None = None,
        anchor: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        if isinstance(payload, PlanarPolygonDraft):
            return self._constrain_polygon_candidate(payload, point, index=index, anchor=anchor)
        if isinstance(payload, VentPathDraft):
            return self._constrain_vent_candidate(payload, point, index=index, anchor=anchor)
        self._set_planar_edit_warning("")
        return (float(point[0]), float(point[1]))

    def _shift_constrained_vent_point(
        self,
        payload: Any,
        point: tuple[float, float],
        *,
        mode: str,
        selected_index: int | None = None,
    ) -> tuple[float, float]:
        """Apply the same Shift 45-degree lock used by Plan Tracer to EVT."""

        if not isinstance(payload, VentPathDraft):
            return (float(point[0]), float(point[1]))
        anchor: tuple[float, float] | None = None
        waypoints = list(getattr(payload, "waypoints", []) or [])
        if str(mode) == "add" and waypoints:
            anchor = tuple(float(v) for v in waypoints[-1])
        elif str(mode) == "mod" and selected_index is not None and waypoints:
            idx = int(selected_index)
            if 0 <= idx < len(waypoints):
                if idx > 0:
                    anchor = tuple(float(v) for v in waypoints[idx - 1])
                elif len(waypoints) > 1:
                    anchor = tuple(float(v) for v in waypoints[1])
        if anchor is None:
            return (float(point[0]), float(point[1]))
        try:
            from laserprog_studio.tool_api import plan2d

            result = plan2d.constrain_angle_step_on_plan(
                payload.plane,
                plane_to_world(payload.plane, anchor[0], anchor[1]),
                plane_to_world(payload.plane, float(point[0]), float(point[1])),
                angle_step_degrees=45.0,
            )
            if bool(getattr(result, "applied", False)):
                constrained = world_to_plane(payload.plane, tuple(float(v) for v in result.world_pos))
                state = self.state
                if state is not None:
                    state.snap_preview_label = (str(getattr(state, "snap_preview_label", "") or "Free") + " · 45°").strip()
                return (float(constrained[0]), float(constrained[1]))
        except Exception:
            pass
        return (float(point[0]), float(point[1]))

    def _draw_planar_preview_interactive(self, *, min_interval: float = 1.0 / 30.0) -> bool:
        state = self.state
        payload = getattr(state, "payload", None) if state is not None else None
        # Vent Generator has heavier duct-footprint feedback than Plan Tracer.
        # During drag we repaint only the editable route HUD and throttle harder;
        # the precise material footprint is rebuilt once on release/apply.
        if isinstance(payload, VentPathDraft):
            min_interval = max(float(min_interval), 1.0 / 22.0)
            try:
                ctx_perf = getattr(getattr(self, "context", None), "tool_context", None)
                from laserprog_studio.tooling.vent_generator.diagnostics import increment_perf
                increment_perf(ctx_perf, "vent.visual.interactive_attempt")
            except Exception:
                pass
        now = time.monotonic()
        if state is not None and now - float(getattr(state, "last_preview_draw_monotonic", 0.0) or 0.0) < float(min_interval):
            if isinstance(payload, VentPathDraft):
                try:
                    ctx_perf = getattr(getattr(self, "context", None), "tool_context", None)
                    from laserprog_studio.tooling.vent_generator.diagnostics import increment_perf
                    increment_perf(ctx_perf, "vent.visual.interactive_throttled")
                except Exception:
                    pass
            return False
        if state is not None:
            state.last_preview_draw_monotonic = now
        # The lightweight path refreshes only interactive actors.  Full face
        # reconstruction, triangulation and generated mesh preview happen on
        # release/apply, not at every mouse position.
        if isinstance(payload, VentPathDraft):
            try:
                ctx = getattr(self.context, "tool_context", None)
                if ctx is not None:
                    from laserprog_studio.tooling.vent_generator.feedback import sync_vent_route_visuals

                    try:
                        from laserprog_studio.tooling.vent_generator.diagnostics import measure_perf
                        measure = measure_perf(ctx, "vent.visual.interactive_sync")
                    except Exception:
                        from contextlib import nullcontext
                        measure = nullcontext()
                    with measure:
                        sync_vent_route_visuals(ctx, payload, state=state, render=True, full=False, position_only=True)
                    return True
            except Exception:
                pass
        self.draw_planar_preview(render=True, lightweight=True)
        return True

    def _begin_planar_drag_snap_cache(self) -> None:
        state = self.state
        if state is None:
            return
        anchors = list(self.payload_anchor_points(include_pending=False))
        # When modifying a point, do not include the point being dragged in the
        # smart-snap cache.  Otherwise it snaps to its own previous location and
        # feels like lag/stiction before the cursor escapes the tolerance radius.
        payload = getattr(state, "payload", None)
        dragged_point = None
        try:
            if getattr(state, "pointer_drag_mode", None) == "mod" and isinstance(payload, PlanarPolygonDraft):
                if getattr(payload, "selected_element_index", None) is not None and getattr(payload, "selected_element_point_index", None) is not None:
                    element = payload.elements[int(payload.selected_element_index)]
                    dragged_point = element.points[int(payload.selected_element_point_index)]
                elif getattr(payload, "selected_index", None) is not None:
                    dragged_point = payload.points[int(payload.selected_index)]
            elif getattr(state, "pointer_drag_mode", None) == "mod" and isinstance(payload, VentPathDraft) and getattr(payload, "selected_index", None) is not None:
                dragged_point = payload.waypoints[int(payload.selected_index)]
        except Exception:
            dragged_point = None
        if dragged_point is not None:
            du, dv = float(dragged_point[0]), float(dragged_point[1])
            anchors = [(u, v) for u, v in anchors if math.hypot(float(u) - du, float(v) - dv) > 1e-6]
        state.drag_snap_anchor_cache = tuple(anchors)
        state.drag_snap_edge_cache = self.payload_edge_segments()
        state.drag_snap_compiled_cache = compile_planar_snap_cache(state.drag_snap_anchor_cache, state.drag_snap_edge_cache)

    def _end_planar_drag_snap_cache(self) -> None:
        state = self.state
        if state is None:
            return
        state.drag_snap_anchor_cache = None
        state.drag_snap_edge_cache = None
        state.drag_snap_compiled_cache = None

    def on_plan_trace_snap_settings_changed(self) -> None:
        try:
            self.owner.plan_trace_smart_snap_enabled = bool(self.owner.plan_trace_smart_snap_btn.isChecked())
        except Exception:
            pass
        try:
            self.owner.plan_trace_grid_snap_enabled = bool(self.owner.plan_trace_grid_snap_btn.isChecked())
        except Exception:
            pass
        self._clear_planar_snap_preview()
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()

    def handle_pointer_press(self, qx: float, qy: float, *, shift_down: bool = False) -> bool:
        if not self.is_active_planar_tool():
            return False
        payload = getattr(self.state, "payload", None)
        if payload is None:
            return True
        self.sync_payload_settings_from_ui(payload)
        mode = getattr(payload, "mode", PlanarEditMode.ADD)
        if not isinstance(mode, PlanarEditMode):
            mode = PlanarEditMode(str(mode))
        if mode is PlanarEditMode.RST:
            self.reset_payload()
            return True
        self._resolve_first_point_depth_if_needed(qx, qy)
        result = self.resolve_qt_pos_on_active_plane(qx, qy, snap=True)
        if result is None:
            return True
        state = self.state
        if mode is PlanarEditMode.ADD:
            state.pointer_drag_active = True
            state.pointer_drag_mode = "add"
            self._begin_planar_drag_snap_cache()
            if isinstance(payload, PlanarPolygonDraft) and getattr(payload, "add_kind", PlanTraceAddKind.POLYGON) is not PlanTraceAddKind.POLYGON:
                point = (float(result.snapped_plane[0]), float(result.snapped_plane[1]))
                self._set_planar_edit_warning("")
            else:
                point = self._constrained_plane_point_for_payload(payload, result.snapped_plane)
            if bool(shift_down) and isinstance(payload, VentPathDraft):
                point = self._shift_constrained_vent_point(payload, point, mode="add")
            state.pending_plane_point = point
            self.draw_planar_preview(render=True)
            self.update_planar_tool_report()
            self._update_preview_button_state()
            self._sync_plan_trace_action_buttons()
            return True
        if mode is PlanarEditMode.SUPP:
            if isinstance(payload, PlanarPolygonDraft):
                payload.delete_nearest_plane(result.snapped_plane, max_distance=self._nearest_tolerance())
            elif isinstance(payload, VentPathDraft):
                payload.delete_nearest_plane(result.snapped_plane, max_distance=self._nearest_tolerance())
            state.pending_plane_point = None
            self._set_planar_edit_warning("")
            self.refresh_generated_preview_if_ready()
            self.draw_planar_preview(render=True)
            self.update_planar_tool_report()
            self._update_preview_button_state()
            return True
        if mode is PlanarEditMode.MOD:
            selected = None
            drag_mode = "mod"
            if isinstance(payload, PlanarPolygonDraft):
                selected = payload.select_nearest_plane(result.snapped_plane, max_distance=self._nearest_tolerance())
            elif isinstance(payload, VentPathDraft):
                # EVT MOD stays simple: only waypoints are selectable/draggable.
                # Segment curve parameters are edited in the toolbox sliders for
                # the selected waypoint; there are no scene handles anymore.
                tol = self._nearest_tolerance()
                selected = payload.select_nearest_plane(result.snapped_plane, max_distance=tol)
                drag_mode = "mod"
            state.pointer_drag_active = selected is not None
            state.pointer_drag_mode = drag_mode if selected is not None else None
            if selected is not None:
                self._begin_planar_drag_snap_cache()
            self.sync_selected_point_to_transform_fields()
            self._sync_plan_trace_action_buttons()
            self.draw_planar_preview(render=True)
            self.update_planar_tool_report()
            self._update_preview_button_state()
            return True
        return True

    def handle_pointer_move(self, qx: float, qy: float, *, shift_down: bool = False) -> bool:
        if not self.is_active_planar_tool():
            return False
        state = self.state
        payload = getattr(state, "payload", None) if state is not None else None
        if state is None:
            return True
        if not bool(getattr(state, "pointer_drag_active", False)):
            if payload is not None:
                try:
                    mode = getattr(payload, "mode", PlanarEditMode.ADD)
                    if not isinstance(mode, PlanarEditMode):
                        mode = PlanarEditMode(str(mode))
                    if mode is PlanarEditMode.ADD:
                        result = self.resolve_qt_pos_on_active_plane(qx, qy, snap=True, include_pending_anchor=False)
                        if result is not None:
                            if isinstance(payload, PlanarPolygonDraft) and getattr(payload, "add_kind", PlanTraceAddKind.POLYGON) is not PlanTraceAddKind.POLYGON:
                                state.pending_plane_point = (float(result.snapped_plane[0]), float(result.snapped_plane[1]))
                                self._set_planar_edit_warning("")
                            else:
                                point = self._constrained_plane_point_for_payload(payload, result.snapped_plane)
                                if bool(shift_down) and isinstance(payload, VentPathDraft):
                                    point = self._shift_constrained_vent_point(payload, point, mode="add")
                                state.pending_plane_point = point
                            if self._draw_planar_preview_interactive():
                                self.update_planar_tool_report()
                    else:
                        state.pending_plane_point = None
                        result = self.resolve_qt_pos_on_active_plane(qx, qy, snap=True, include_pending_anchor=False)
                        self._draw_planar_preview_interactive()
                except Exception:
                    pass
            return True
        result = self.resolve_qt_pos_on_active_plane(qx, qy, snap=True, include_pending_anchor=False)
        if result is None:
            return True
        if state.pointer_drag_mode == "add":
            if isinstance(payload, PlanarPolygonDraft) and getattr(payload, "add_kind", PlanTraceAddKind.POLYGON) is not PlanTraceAddKind.POLYGON:
                point = (float(result.snapped_plane[0]), float(result.snapped_plane[1]))
                self._set_planar_edit_warning("")
            else:
                point = self._constrained_plane_point_for_payload(payload, result.snapped_plane)
            if bool(shift_down) and isinstance(payload, VentPathDraft):
                point = self._shift_constrained_vent_point(payload, point, mode="add")
            state.pending_plane_point = point
        elif state.pointer_drag_mode == "mod" and payload is not None:
            try:
                selected = getattr(payload, "selected_index", None)
                anchor = None
                if isinstance(payload, PlanarPolygonDraft) and selected is not None and 0 <= int(selected) < len(payload.points):
                    anchor = payload.points[int(selected)]
                elif isinstance(payload, VentPathDraft) and selected is not None and 0 <= int(selected) < len(payload.waypoints):
                    anchor = payload.waypoints[int(selected)]
                if isinstance(payload, PlanarPolygonDraft) and getattr(payload, "selected_element_index", None) is not None:
                    point = (float(result.snapped_plane[0]), float(result.snapped_plane[1]))
                    self._set_planar_edit_warning("")
                else:
                    point = self._constrained_plane_point_for_payload(payload, result.snapped_plane, index=selected, anchor=anchor)
                if bool(shift_down) and isinstance(payload, VentPathDraft) and selected is not None:
                    point = self._shift_constrained_vent_point(payload, point, mode="mod", selected_index=int(selected))
                    point = self._constrained_plane_point_for_payload(payload, point, index=selected, anchor=anchor)
                if not (isinstance(payload, VentPathDraft) and getattr(self.state, "last_edit_warning", "")):
                    payload.update_selected_plane(point)
                # Updating inspector spinboxes on every Vent drag is costly and
                # visually irrelevant; sync once on release instead.
                if not isinstance(payload, VentPathDraft):
                    self.sync_selected_point_to_transform_fields()
            except Exception:
                pass
        self._draw_planar_preview_interactive()
        return True

    def handle_pointer_release(self, qx: float, qy: float, *, shift_down: bool = False) -> bool:
        if not self.is_active_planar_tool():
            return False
        state = self.state
        payload = getattr(state, "payload", None)
        if state is None or payload is None:
            return True
        if bool(getattr(state, "pointer_drag_active", False)):
            result = self.resolve_qt_pos_on_active_plane(qx, qy, snap=True)
            point = result.snapped_plane if result is not None else state.pending_plane_point
            try:
                if point is not None and state.pointer_drag_mode == "add":
                    if bool(shift_down) and isinstance(payload, VentPathDraft):
                        point = self._shift_constrained_vent_point(payload, (float(point[0]), float(point[1])), mode="add")
                    if isinstance(payload, PlanarPolygonDraft):
                        if getattr(payload, "add_kind", PlanTraceAddKind.POLYGON) is PlanTraceAddKind.POLYGON:
                            safe_point = state.pending_plane_point or self._constrained_plane_point_for_payload(payload, point)
                            payload.add_point_plane(safe_point, min_spacing=max(self._nearest_tolerance() * 0.05, 1e-6))
                        else:
                            safe_point = state.pending_plane_point or (float(point[0]), float(point[1]))
                            completed = payload.add_trace_point_plane(safe_point)
                            self._set_planar_edit_warning("")
                            if completed:
                                self.ui_log(f"[PLAN] Added {payload.add_kind.value}")
                    elif isinstance(payload, VentPathDraft):
                        safe_point = state.pending_plane_point or self._constrained_plane_point_for_payload(payload, point)
                        check = payload.clamp_waypoint_candidate(safe_point)
                        if check.valid:
                            payload.add_waypoint_plane(safe_point, min_spacing=max(self._nearest_tolerance() * 0.05, 1e-6))
                            self._set_planar_edit_warning("")
                        else:
                            self._set_planar_edit_warning(check.message or "invalid position", raw_point=check.raw_point)
                            self.ui_log(f"[EVT] Point rejected: {check.message}")
                elif point is not None and state.pointer_drag_mode == "mod":
                    selected = getattr(payload, "selected_index", None)
                    if bool(shift_down) and isinstance(payload, VentPathDraft) and selected is not None:
                        point = self._shift_constrained_vent_point(payload, (float(point[0]), float(point[1])), mode="mod", selected_index=int(selected))
                    if isinstance(payload, PlanarPolygonDraft) and getattr(payload, "selected_element_index", None) is not None:
                        safe_point = (float(point[0]), float(point[1]))
                        self._set_planar_edit_warning("")
                    else:
                        safe_point = self._constrained_plane_point_for_payload(payload, point, index=selected)
                    if not (isinstance(payload, VentPathDraft) and getattr(self.state, "last_edit_warning", "")):
                        payload.update_selected_plane(safe_point)
            except Exception as exc:
                self.ui_log(f"[PLANAR] Edit ignored: {exc}")
        state.pointer_drag_active = False
        state.pointer_drag_mode = None
        state.pending_plane_point = None
        self._end_planar_drag_snap_cache()
        self._clear_planar_snap_preview()
        self.sync_selected_point_to_transform_fields()
        self.refresh_generated_preview_if_ready()
        self.draw_planar_preview(render=True)
        self.update_planar_tool_report()
        self._update_preview_button_state()
        return True

    def handle_pointer_double_click(self, qx: float, qy: float) -> bool:
        if not self.is_active_planar_tool():
            return False
        payload = getattr(self.state, "payload", None)
        if isinstance(payload, PlanarPolygonDraft):
            if getattr(payload, "mode", PlanarEditMode.MOD) is not PlanarEditMode.ADD or getattr(payload, "add_kind", PlanTraceAddKind.POLYGON) is not PlanTraceAddKind.POLYGON:
                return self.exit_plan_trace_add_mode()
            close_validation = payload.close_validation_result()
            if payload.close_polygon():
                self._set_planar_edit_warning("")
                self.ui_log("[PLAN] Polygon closed")
            else:
                message = close_validation.message() or "cannot close polygon"
                self._set_planar_edit_warning(message)
                self.ui_log(f"[PLAN] {message}")
            if self.state is not None:
                self.state.pointer_drag_active = False
                self.state.pointer_drag_mode = None
                self.state.pending_plane_point = None
                self._clear_planar_snap_preview()
            self.refresh_generated_preview_if_ready()
            self.draw_planar_preview(render=True)
            self.update_planar_tool_report()
            self._update_preview_button_state()
            return True
        if isinstance(payload, VentPathDraft):
            # Rectangular EVT has no hidden outlet-finalization step anymore.
            # The inlet is always waypoint 0 and the outlet is always the last
            # user waypoint.  Double-click must therefore not mark, clamp or
            # reinterpret the mouth position; it simply clears the transient
            # pointer preview and redraws the current anchored state.
            if self.state is not None:
                self.state.pointer_drag_active = False
                self.state.pointer_drag_mode = None
                self.state.pending_plane_point = None
                self._clear_planar_snap_preview()
            self._set_planar_edit_warning("")
            self.ui_log("[EVT] Flare anchored on first/last waypoint")
            self.refresh_generated_preview_if_ready()
            self.draw_planar_preview(render=True)
            self.update_planar_tool_report()
            self._update_preview_button_state()
            return True
        return True

    def update_selected_from_transform_fields(self) -> bool:
        if not self.is_active_planar_tool():
            return False
        payload = getattr(self.state, "payload", None)
        if payload is None:
            return False
        has_point_selection = getattr(payload, "selected_index", None) is not None or (isinstance(payload, PlanarPolygonDraft) and getattr(payload, "selected_element_index", None) is not None)
        if not has_point_selection:
            return False
        try:
            world = (float(self.owner.pos_x.value()), float(self.owner.pos_y.value()), float(self.owner.pos_z.value()))
            point = world_to_plane(payload.plane, world)
            selected = getattr(payload, "selected_index", None)
            if isinstance(payload, PlanarPolygonDraft):
                if getattr(payload, "selected_element_index", None) is not None:
                    point = (float(point[0]), float(point[1]))
                    self._set_planar_edit_warning("")
                else:
                    anchor = payload.points[int(selected)] if selected is not None and 0 <= int(selected) < len(payload.points) else None
                    point = self._constrained_plane_point_for_payload(payload, point, index=selected, anchor=anchor)
            elif isinstance(payload, VentPathDraft):
                point = self._constrained_plane_point_for_payload(payload, point, index=selected)
            else:
                self._set_planar_edit_warning("")
            payload.update_selected_plane(point)
            self.refresh_generated_preview_if_ready()
            self.draw_planar_preview(render=True)
            self.sync_selected_point_to_transform_fields()
            self.update_planar_tool_report()
            self._update_preview_button_state()
            return True
        except Exception:
            log_exception("planar_update_selected_from_transform_fields")
            return True

# Transitional import alias; the concrete implementation is a Layer, not a mixin class.
PlanarToolInteractionLayer = PlanarToolInteractionLayer

