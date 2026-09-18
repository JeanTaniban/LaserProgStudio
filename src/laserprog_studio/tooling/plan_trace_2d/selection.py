# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api.core import MouseButton, ToolEvent, ToolEventType

from .services import _PlanTrace2DService

class PlanTrace2DSelectionService(_PlanTrace2DService):
    def _configure_modify_selection_api(self, ctx: Any) -> None:
        """Configure API-owned rectangle selection for Plan tracer Modify mode.

        Tool authors should not have to implement rubber-band selection policy.
        Plan tracer only opts into the API service and receives a semantic
        completion callback; the service handles screen-space collection,
        additive/subtractive modes and future overlay rendering.
        """

        try:
            ctx.selection_box.configure(
                enabled=True,
                targets=("tool_actors",),
                mode="replace",
                inside_policy="partial",
                owner_tool=self.id,
                min_drag_px=6.0,
                selectable_only=True,
                clear_on_empty=True,
                require_empty_press=True,
                activation_modifier="shift",
                on_complete=self._on_modify_box_selection_complete,
            )
        except Exception:
            pass

    def _handle_modify_selection_api_event(self, ctx: Any, event: ToolEvent) -> bool:
        if event.screen_pos is None:
            return False
        world_to_screen = getattr(ctx.viewport, "world_to_screen", None)
        if event.shift and event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "selection.event.begin",
                    owner=getattr(ctx, "owner", None),
                    ctx=ctx,
                    include_selection=True,
                    include_inspector=True,
                    screen_pos=event.screen_pos,
                    world_pos=getattr(event, "world_pos", None),
                    shift=bool(getattr(event, "shift", False)),
                    ctrl=bool(getattr(event, "ctrl", False)),
                    active_tool=str(getattr(self._state, "active_tool", "")),
                )
            except Exception:
                pass
            # Shift-click toggles a single sketch entity. Shift-drag from empty
            # space is left to ctx.selection_box below. This keeps box selection
            # useful without breaking the CAD-standard additive click gesture.
            try:
                from laserprog_studio.tool_api.scene import projection_cache_signature

                projection_key = projection_cache_signature(ctx)
            except Exception:
                projection_key = None
            hit = ctx.selection.hit_test(
                event.screen_pos,
                world_to_screen or (lambda p: (float(p[0]), float(p[1]))),
                owner_tool=self.id,
                selectable_only=True,
                projection_key=projection_key,
            )
            if hit is not None:
                try:
                    from laserprog_studio.diagnostics.plan_trace_selection_length_debug import actor_snapshot, record_selection_length_event

                    record_selection_length_event(
                        "selection.hit.received",
                        owner=getattr(ctx, "owner", None),
                        ctx=ctx,
                        include_selection=True,
                        hit={
                            "actor_id": str(hit.actor_id),
                            "distance_px": float(hit.distance_px),
                            "kind": str(hit.kind),
                            "priority": int(getattr(hit, "priority", 0)),
                        },
                        actor=actor_snapshot(ctx.selection.actor(hit.actor_id)),
                    )
                except Exception:
                    pass
                was_selected = bool(ctx.selection.is_selected(hit.actor_id))
                mutation_result = True
                if was_selected:
                    ctx.selection.deselect(hit.actor_id)
                    action = "Deselected"
                else:
                    mutation_result = bool(ctx.selection.select(hit.actor_id, replace=False))
                    action = "Selected"
                try:
                    from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                    record_selection_length_event(
                        "selection.mutation.done",
                        owner=getattr(ctx, "owner", None),
                        ctx=ctx,
                        include_selection=True,
                        include_inspector=True,
                        action=action,
                        actor_id=str(hit.actor_id),
                        was_selected=was_selected,
                        mutation_result=mutation_result,
                    )
                except Exception:
                    pass
                self.services.overlay._sync_reports(ctx)
                try:
                    from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                    record_selection_length_event(
                        "selection.reports.synced",
                        owner=getattr(ctx, "owner", None),
                        ctx=ctx,
                        include_selection=True,
                        include_inspector=True,
                    )
                    from laserprog_studio.diagnostics.plan_trace_selection_length_debug import export_selection_length_summary

                    export_selection_length_summary(ctx=ctx, sketch=getattr(self._state, "sketch", None), reason="shift_click")
                except Exception:
                    pass
                self.services.rendering._render(ctx, sync_overlays=True, render=True)
                try:
                    ctx.status.info(f"{action} Plan tracer {self._role_label_for_actor_id(ctx, hit.actor_id)}.")
                except Exception:
                    pass
                return True
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "selection.hit.missed",
                    owner=getattr(ctx, "owner", None),
                    ctx=ctx,
                    include_selection=True,
                    include_inspector=True,
                    screen_pos=event.screen_pos,
                )
            except Exception:
                pass
        try:
            handled = bool(ctx.selection_box.handle_event(event, world_to_screen=world_to_screen))
        except Exception:
            handled = False
        if handled:
            # Mouse-move while drawing the blue rubber-band is a purely visual
            # screen-space operation.  The application bridge updates the two
            # persistent VTK Actor2D props directly; rebuilding Plan Tracer
            # reports and rendering the complete projected sketch for every
            # pointer pixel made dense sketches stutter badly.  Semantic hit
            # collection and selection repaint remain release-time work through
            # ``_on_modify_box_selection_complete``.
            if event.type is ToolEventType.MOUSE_MOVE:
                return True
            # The completion callback already performs the one report/visual
            # synchronization required after release.  Avoid duplicating that
            # full frame here.
            if event.type is ToolEventType.MOUSE_RELEASE:
                return True
            return True
        # A pending shift-drag press/move should not fall through to drawing logic.
        try:
            return bool(ctx.selection_box.pending)
        except Exception:
            return False

    def _on_modify_box_selection_complete(self, result: Any, ctx: Any) -> None:
        # Keep the explicit box result intact. Support points are promoted only
        # when the user presses one of them to begin a group drag; this preserves
        # face-only deletion and clear, predictable selection counts.
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            count = len(tuple(getattr(result, "tool_actor_ids", ()) or ()))
            ctx.status.info(f"Plan tracer box selection: {count} item(s).")
        except Exception:
            pass

    def _role_label_for_actor_id(self, ctx: Any, actor_id: str) -> str:
        actor = ctx.selection.actor(actor_id)
        if actor is None:
            return "item"
        role = str(actor.metadata.get("plan_trace_role", "item") or "item")
        return role.replace("_", " ")

    def _delete_selected_points(self, ctx: Any) -> bool:
        selected_ids = tuple(str(value) for value in ctx.selection.ids())
        point_ids: list[str] = []
        line_ids: list[str] = []
        face_ids: list[str] = []
        circle_ids: list[str] = []
        arc_ids: list[str] = []
        bezier_ids: list[str] = []
        dimension_ids: list[str] = []
        for actor_id in selected_ids:
            actor = ctx.selection.actor(actor_id)
            if actor is None or actor.owner_tool != self.id:
                continue
            role = actor.metadata.get("plan_trace_role")
            if role == "point":
                point_ids.append(actor_id)
            elif role == "edge":
                sketch_line_id = actor.metadata.get("plan_trace_sketch_line_id")
                if sketch_line_id is not None:
                    line_ids.append(str(sketch_line_id))
            elif role == "face":
                sketch_face_id = actor.metadata.get("plan_trace_sketch_face_id")
                if sketch_face_id is not None:
                    face_ids.append(str(sketch_face_id))
            elif role == "circle":
                sketch_circle_id = actor.metadata.get("plan_trace_sketch_circle_id")
                if sketch_circle_id is not None:
                    circle_ids.append(str(sketch_circle_id))
            elif role == "arc":
                sketch_arc_id = actor.metadata.get("plan_trace_sketch_arc_id")
                sketch_bezier_id = actor.metadata.get("plan_trace_sketch_bezier_id")
                if sketch_arc_id is not None:
                    arc_ids.append(str(sketch_arc_id))
                if sketch_bezier_id is not None:
                    bezier_ids.append(str(sketch_bezier_id))
            elif role == "dimension":
                sketch_dimension_id = actor.metadata.get("plan_trace_sketch_dimension_id")
                if sketch_dimension_id is not None:
                    dimension_ids.append(str(sketch_dimension_id))
        if not point_ids and not line_ids and not face_ids and not circle_ids and not arc_ids and not bezier_ids and not dimension_ids:
            return False
        before = self.services.history._snapshot_state()
        if self._state.pending_line_start_id in point_ids:
            self._state.pending_line_start_id = None
        if self._state.pending_rectangle_corner_id in point_ids:
            self._state.pending_rectangle_corner_id = None
        if self._state.pending_circle_center_id in point_ids:
            self._state.pending_circle_center_id = None
        if self._state.pending_arc_start_id in point_ids:
            self._state.pending_arc_start_id = None
            self._state.pending_arc_end_id = None
        if self._state.pending_arc_end_id in point_ids:
            self._state.pending_arc_end_id = None
        if self._state.pending_bezier_start_id in point_ids:
            self._state.pending_bezier_start_id = None
            self._state.pending_bezier_end_id = None
            self._state.pending_bezier_control_1_id = None
        if self._state.pending_bezier_end_id in point_ids:
            self._state.pending_bezier_end_id = None
            self._state.pending_bezier_control_1_id = None
        if self._state.pending_bezier_control_1_id in point_ids:
            self._state.pending_bezier_control_1_id = None
        if self._state.pending_half_circle_start_id in point_ids:
            self._state.pending_half_circle_start_id = None
        if self._state.pending_dimension_start_id in point_ids:
            self._state.pending_dimension_start_id = None
        if self._state.pending_dimension_line_id in line_ids:
            self._state.pending_dimension_line_id = None
        for point_id in point_ids:
            self._state.sketch.delete_point_cascade(point_id, compile_after=False)
        for line_id in line_ids:
            self._state.sketch.delete_line_cascade(line_id, compile_after=False)
        for face_id in face_ids:
            self._state.sketch.delete_face_only(face_id, compile_after=False)
        for circle_id in circle_ids:
            self._state.sketch.delete_entity(circle_id)
        for arc_id in arc_ids:
            self._state.sketch.delete_arc_cascade(arc_id, compile_after=False)
        for bezier_id in bezier_ids:
            self._state.sketch.delete_bezier_cascade(bezier_id, compile_after=False)
        for dimension_id in dimension_ids:
            self._state.sketch.delete_dimension(dimension_id)
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            pass

        # A generated face is only a suppressible fill over unchanged boundary
        # geometry.  Re-running the complete sketch compiler/face solver just to
        # hide that fill is unnecessary and becomes very visible on large plans.
        # Remove its projected primitive directly, persist the suppression in the
        # compile signature, and keep a single viewport render.
        only_generated_faces = bool(face_ids) and not any(
            (point_ids, line_ids, circle_ids, arc_ids, bezier_ids, dimension_ids)
        )
        if only_generated_faces:
            registry = ctx.projected_drawing.for_tool(self.id)
            actor_ids = tuple(self.services.sketch_sync._face_actor_id(face_id) for face_id in face_ids)
            registry.remove_many(actor_ids, render=False)
            for actor_id in actor_ids:
                self._state.plan_trace_actor_visual_signatures.pop(str(actor_id), None)
            self._state.plan_trace_last_compile_signature = self.services.sketch_sync._compile_signature()
            self.services.overlay._sync_reports(ctx)
            self.services.sketch_sync._sync_apply_button_state(ctx)
            self.services.history._record_snapshot_command(
                ctx,
                "Delete Plan tracer selection",
                before,
                assume_changed=True,
            )
            registry.render(render=True)
        else:
            # Topology entities genuinely require one compile, but that compile
            # already synchronizes actors and renders the final projected frame.
            # The historical second full render after history bookkeeping doubled
            # Delete latency for no visual benefit.
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            self.services.history._record_snapshot_command(
                ctx,
                "Delete Plan tracer selection",
                before,
                assume_changed=True,
            )
        parts = []
        if point_ids:
            parts.append(f"{len(point_ids)} point(s)")
        if line_ids:
            parts.append(f"{len(line_ids)} edge(s)")
        if face_ids:
            parts.append(f"{len(face_ids)} face(s)")
        if circle_ids:
            parts.append(f"{len(circle_ids)} circle(s)")
        if arc_ids:
            parts.append(f"{len(arc_ids)} arc(s)")
        if bezier_ids:
            parts.append(f"{len(bezier_ids)} Bezier curve(s)")
        if dimension_ids:
            parts.append(f"{len(dimension_ids)} dimension(s)")
        ctx.status.info("Deleted Plan tracer " + " and ".join(parts) + ".")
        return True

    def _restore_generated_faces(self, ctx: Any) -> bool:
        """Restore user-deleted generated face fills from existing closed loops.

        Deleting a face records its geometric signature so the compiler does not
        recreate it immediately.  Users need the inverse operation too: when a
        hole was created by deleting an inner region, Rebuild faces clears those
        suppressions and compiles the current boundaries into selectable regions
        again.
        """

        if not getattr(self._state.sketch, "suppressed_face_signatures", set()):
            try:
                ctx.status.info("Plan tracer: no deleted face to rebuild.")
            except Exception:
                pass
            return False
        before = self.services.history._snapshot_state()
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            pass
        self._state.sketch.restore_generated_faces(compile_after=False)
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self.services.history._record_snapshot_command(ctx, "Rebuild Plan tracer faces", before)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            ctx.status.info("Plan tracer faces rebuilt from closed boundaries.")
        except Exception:
            pass
        return True


__all__ = ["PlanTrace2DSelectionService"]
