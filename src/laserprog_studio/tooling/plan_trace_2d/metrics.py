# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .constants import (
    _METRIC_CANCEL_BUTTON_ID,
    _METRIC_OVERLAY_ID,
    _METRIC_VALIDATE_BUTTON_ID,
    _MODE_ARC,
    _MODE_CIRCLE,
    _MODE_HALF_CIRCLE,
    _MODE_LINE,
    _MODE_RECTANGLE,
)
from .curve_intent import ArcIntent, HalfCircleIntent
from .metric_field_policy import apply_metric_field_update
from .metric_rebuilders import distance_xy, line_metrics_from_xy
from .services import _PlanTrace2DService
from .state import _PlacementMetricDraft, _PlanTrace2DSnapshot

class PlanTrace2DMetricsService(_PlanTrace2DService):
    def _begin_line_metric_edit(
        self,
        ctx: Any,
        base_snapshot: _PlanTrace2DSnapshot,
        start_xy: tuple[float, float],
        end_xy: tuple[float, float],
        *,
        entity_ids: tuple[str, ...] = (),
    ) -> None:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        length, angle = line_metrics_from_xy(start_xy, end_xy)
        session = metric_api.line_metric_session(_METRIC_OVERLAY_ID, length=length, angle_degrees=angle)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_LINE,
            base_snapshot=self.services.history._clone_snapshot(base_snapshot),
            session_id=session.id,
            session=session,
            start_xy=tuple(float(v) for v in start_xy),
            end_xy=tuple(float(v) for v in end_xy),
            entity_ids=tuple(str(value) for value in entity_ids),
        )
        self._show_metric_overlay(ctx, session)

    def _begin_circle_metric_edit(
        self,
        ctx: Any,
        base_snapshot: _PlanTrace2DSnapshot,
        center_xy: tuple[float, float],
        radius_xy: tuple[float, float],
        *,
        entity_ids: tuple[str, ...] = (),
    ) -> None:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        radius = distance_xy(center_xy, radius_xy)
        session = metric_api.circle_metric_session(_METRIC_OVERLAY_ID, radius=radius)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_CIRCLE,
            base_snapshot=self.services.history._clone_snapshot(base_snapshot),
            session_id=session.id,
            session=session,
            center_xy=tuple(float(v) for v in center_xy),
            radius_xy=tuple(float(v) for v in radius_xy),
            entity_ids=tuple(str(value) for value in entity_ids),
        )
        self._show_metric_overlay(ctx, session)

    def _begin_rectangle_metric_edit(
        self,
        ctx: Any,
        base_snapshot: _PlanTrace2DSnapshot,
        first_xy: tuple[float, float],
        opposite_xy: tuple[float, float],
        *,
        entity_ids: tuple[str, ...] = (),
    ) -> None:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api
        dims = metric_api.rectangle_metrics(first_xy, opposite_xy)
        session = metric_api.rectangle_metric_session(_METRIC_OVERLAY_ID, width=dims.width, height=dims.height)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_RECTANGLE,
            base_snapshot=self.services.history._clone_snapshot(base_snapshot),
            session_id=session.id,
            session=session,
            first_xy=tuple(float(v) for v in first_xy),
            opposite_xy=tuple(float(v) for v in opposite_xy),
            entity_ids=tuple(str(value) for value in entity_ids),
        )
        self._show_metric_overlay(ctx, session)

    def _begin_half_circle_metric_edit(
        self,
        ctx: Any,
        base_snapshot: _PlanTrace2DSnapshot,
        start_xy: tuple[float, float],
        end_xy: tuple[float, float],
        *,
        entity_ids: tuple[str, ...] = (),
        half_circle_intent: HalfCircleIntent | None = None,
    ) -> None:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api
        if half_circle_intent is None:
            half_circle_intent = HalfCircleIntent.from_points(start_xy, end_xy)
        circle, angle = metric_api.half_circle_metrics(start_xy, end_xy)
        session = metric_api.half_circle_metric_session(_METRIC_OVERLAY_ID, radius=circle.radius, angle_degrees=angle)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_HALF_CIRCLE,
            base_snapshot=self.services.history._clone_snapshot(base_snapshot),
            session_id=session.id,
            session=session,
            start_xy=tuple(float(v) for v in start_xy),
            end_xy=tuple(float(v) for v in end_xy),
            entity_ids=tuple(str(value) for value in entity_ids),
            half_circle_intent=half_circle_intent,
        )
        self._show_metric_overlay(ctx, session)

    def _begin_arc_metric_edit(
        self,
        ctx: Any,
        base_snapshot: _PlanTrace2DSnapshot,
        start_xy: tuple[float, float],
        end_xy: tuple[float, float],
        control_xy: tuple[float, float],
        *,
        entity_ids: tuple[str, ...] = (),
        arc_intent: ArcIntent | None = None,
    ) -> None:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api
        if arc_intent is None:
            arc_intent = ArcIntent.from_points(start_xy, end_xy, control_xy)
        arc = metric_api.arc_metrics(start_xy, end_xy, control_xy)
        angle_degrees = arc_intent.sweep_degrees if arc_intent.sweep_degrees > 0.0 else arc.angle_degrees
        session = metric_api.arc_metric_session(_METRIC_OVERLAY_ID, radius=arc.radius, angle_degrees=angle_degrees)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_ARC,
            base_snapshot=self.services.history._clone_snapshot(base_snapshot),
            session_id=session.id,
            session=session,
            start_xy=tuple(float(v) for v in start_xy),
            end_xy=tuple(float(v) for v in end_xy),
            control_xy=tuple(float(v) for v in control_xy),
            entity_ids=tuple(str(value) for value in entity_ids),
            arc_intent=arc_intent,
        )
        self._show_metric_overlay(ctx, session)

    def open_metric_edit_for_actor(self, ctx: Any, actor_id: str) -> bool:
        """Reopen the numeric validation bar for an existing sketch entity.

        Initial placement already shows the metric overlay.  When a saved/editable
        Plan Tracer sketch is reopened, users must be able to click an existing
        line/circle/rectangle/arc and get the same validation bar back instead of
        deleting and recreating the entity.  The implementation builds a clean
        base snapshot with the edited primitive removed, then reuses the existing
        placement rebuilders so validation/cancel/undo keep the same semantics.
        """

        if self._state.plane is None:
            return False
        if self._state.metric_draft is not None:
            try:
                self._validate_metric_draft(ctx)
            except Exception:
                self._state.metric_draft = None
        try:
            actor = ctx.selection.actor(str(actor_id))
        except Exception:
            actor = None
        if actor is None or getattr(actor, "owner_tool", None) != self.id:
            return False
        metadata = dict(getattr(actor, "metadata", {}) or {})
        role = str(metadata.get("plan_trace_role", "") or "")
        if role == "edge":
            return self._begin_existing_line_metric_edit(ctx, str(metadata.get("plan_trace_sketch_line_id") or ""))
        if role == "circle":
            return self._begin_existing_circle_metric_edit(ctx, str(metadata.get("plan_trace_sketch_circle_id") or ""))
        if role == "arc":
            return self._begin_existing_arc_metric_edit(ctx, str(metadata.get("plan_trace_sketch_arc_id") or ""))
        if role == "face":
            return self._begin_existing_rectangle_metric_edit(ctx, str(metadata.get("plan_trace_sketch_face_id") or ""))
        return False

    def _begin_existing_line_metric_edit(self, ctx: Any, line_id: str) -> bool:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        line = self._state.sketch.lines.get(str(line_id))
        if line is None:
            return False
        start = self._state.sketch.points.get(line.start_point_id)
        end = self._state.sketch.points.get(line.end_point_id)
        if start is None or end is None:
            return False
        start_xy = tuple(float(v) for v in start.position)
        end_xy = tuple(float(v) for v in end.position)
        length, angle = line_metrics_from_xy(start_xy, end_xy)
        if length <= 1.0e-8:
            return False
        session = metric_api.line_metric_session(_METRIC_OVERLAY_ID, length=length, angle_degrees=angle)
        base = self._metric_reedit_base_snapshot(remove_line_ids=(line.id,), cleanup_point_ids=(line.end_point_id,))
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_LINE,
            base_snapshot=base,
            session_id=session.id,
            session=session,
            start_xy=start_xy,
            end_xy=end_xy,
            entity_ids=(line.id, line.start_point_id, line.end_point_id),
        )
        self._show_metric_overlay(ctx, session)
        try:
            ctx.status.info("Editing existing line metrics. Adjust length/angle, then validate.")
        except Exception:
            pass
        return True

    def _begin_existing_circle_metric_edit(self, ctx: Any, circle_id: str) -> bool:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        circle = self._state.sketch.circles.get(str(circle_id))
        if circle is None:
            return False
        center = self._state.sketch.points.get(circle.center_point_id)
        radius_point = self._state.sketch.points.get(circle.radius_point_id)
        if center is None or radius_point is None:
            return False
        center_xy = tuple(float(v) for v in center.position)
        radius_xy = tuple(float(v) for v in radius_point.position)
        radius = distance_xy(center_xy, radius_xy)
        if radius <= 1.0e-8:
            return False
        session = metric_api.circle_metric_session(_METRIC_OVERLAY_ID, radius=radius)
        base = self._metric_reedit_base_snapshot(remove_circle_ids=(circle.id,), cleanup_point_ids=(circle.radius_point_id,))
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_CIRCLE,
            base_snapshot=base,
            session_id=session.id,
            session=session,
            center_xy=center_xy,
            radius_xy=radius_xy,
            entity_ids=(circle.id, circle.center_point_id, circle.radius_point_id),
        )
        self._show_metric_overlay(ctx, session)
        try:
            ctx.status.info("Editing existing circle metrics. Adjust radius/diameter, then validate.")
        except Exception:
            pass
        return True

    def _begin_existing_rectangle_metric_edit(self, ctx: Any, face_id: str) -> bool:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        rect = self._rectangle_edit_data_from_face(str(face_id))
        if rect is None:
            return False
        first, opposite, line_ids, cleanup_points = rect
        dims = metric_api.rectangle_metrics(first, opposite)
        if dims.width <= 1.0e-8 or dims.height <= 1.0e-8:
            return False
        session = metric_api.rectangle_metric_session(_METRIC_OVERLAY_ID, width=dims.width, height=dims.height)
        base = self._metric_reedit_base_snapshot(remove_line_ids=line_ids, cleanup_point_ids=cleanup_points)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_RECTANGLE,
            base_snapshot=base,
            session_id=session.id,
            session=session,
            first_xy=first,
            opposite_xy=opposite,
            entity_ids=tuple(line_ids),
        )
        self._show_metric_overlay(ctx, session)
        try:
            ctx.status.info("Editing existing rectangle metrics. Adjust width/height, then validate.")
        except Exception:
            pass
        return True

    def _begin_existing_arc_metric_edit(self, ctx: Any, arc_id: str) -> bool:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        arc = self._state.sketch.arcs.get(str(arc_id))
        if arc is None:
            return False
        start = self._state.sketch.points.get(arc.start_point_id)
        end = self._state.sketch.points.get(arc.end_point_id)
        control = self._state.sketch.points.get(arc.control_point_id)
        if start is None or end is None or control is None:
            return False
        start_xy = tuple(float(v) for v in start.position)
        end_xy = tuple(float(v) for v in end.position)
        control_xy = tuple(float(v) for v in control.position)
        metadata = dict(getattr(arc, "metadata", {}) or {})
        if metadata.get("curve_type") == "half_circle":
            side_label = str(metadata.get("curve_side") or "left").lower()
            half_intent = HalfCircleIntent.from_points(start_xy, end_xy, side=-1.0 if side_label == "right" else 1.0)
            circle, angle = metric_api.half_circle_metrics(start_xy, end_xy)
            session = metric_api.half_circle_metric_session(_METRIC_OVERLAY_ID, radius=circle.radius, angle_degrees=angle)
            diameter_line_id = str(metadata.get("diameter_line_id") or "")
            remove_lines = (diameter_line_id,) if diameter_line_id in self._state.sketch.lines else ()
            base = self._metric_reedit_base_snapshot(remove_arc_ids=(arc.id,), remove_line_ids=remove_lines, cleanup_point_ids=(arc.control_point_id,))
            self._state.metric_draft = _PlacementMetricDraft(
                mode=_MODE_HALF_CIRCLE,
                base_snapshot=base,
                session_id=session.id,
                session=session,
                start_xy=start_xy,
                end_xy=end_xy,
                entity_ids=(arc.id, *remove_lines, arc.start_point_id, arc.end_point_id, arc.control_point_id),
                half_circle_intent=half_intent,
            )
            self._show_metric_overlay(ctx, session)
            try:
                ctx.status.info("Editing existing half-circle metrics. Adjust radius/diameter, then validate.")
            except Exception:
                pass
            return True
        arc_intent = ArcIntent.from_points(start_xy, end_xy, control_xy)
        arc_metrics = metric_api.arc_metrics(start_xy, end_xy, control_xy)
        angle_degrees = arc_intent.sweep_degrees if arc_intent.sweep_degrees > 0.0 else arc_metrics.angle_degrees
        session = metric_api.arc_metric_session(_METRIC_OVERLAY_ID, radius=arc_metrics.radius, angle_degrees=angle_degrees)
        base = self._metric_reedit_base_snapshot(remove_arc_ids=(arc.id,), cleanup_point_ids=(arc.control_point_id,))
        self._state.metric_draft = _PlacementMetricDraft(
            mode=_MODE_ARC,
            base_snapshot=base,
            session_id=session.id,
            session=session,
            start_xy=start_xy,
            end_xy=end_xy,
            control_xy=control_xy,
            entity_ids=(arc.id, arc.start_point_id, arc.end_point_id, arc.control_point_id),
            arc_intent=arc_intent,
        )
        self._show_metric_overlay(ctx, session)
        try:
            ctx.status.info("Editing existing arc metrics. Adjust radius/angle, then validate.")
        except Exception:
            pass
        return True

    def _metric_reedit_base_snapshot(
        self,
        *,
        remove_line_ids: tuple[str, ...] = (),
        remove_circle_ids: tuple[str, ...] = (),
        remove_arc_ids: tuple[str, ...] = (),
        cleanup_point_ids: tuple[str, ...] = (),
    ) -> _PlanTrace2DSnapshot:
        base = self.services.history._snapshot_state()
        sketch = base.sketch
        removed_entity_ids = {str(value) for value in (*remove_line_ids, *remove_circle_ids, *remove_arc_ids) if value}
        cleanup = {str(value) for value in cleanup_point_ids if value}
        for line_id in tuple(removed_entity_ids):
            line = sketch.lines.pop(line_id, None)
            if line is not None:
                cleanup.update((line.start_point_id, line.end_point_id))
        for circle_id in tuple(remove_circle_ids):
            circle = sketch.circles.pop(str(circle_id), None)
            if circle is not None:
                cleanup.update((circle.radius_point_id,))
        for arc_id in tuple(remove_arc_ids):
            arc = sketch.arcs.pop(str(arc_id), None)
            if arc is not None:
                cleanup.update((arc.control_point_id,))
        try:
            sketch.remove_dimensions_referencing(removed_entity_ids)
        except Exception:
            pass
        for point_id in tuple(cleanup):
            if point_id in sketch.points and not self._point_is_referenced(sketch, point_id):
                sketch.points.pop(point_id, None)
        # Faces/polylines are generated topology.  Removing a primitive makes the
        # old generated regions stale; the metric rebuilder recompiles them from
        # the edited geometry on validation.
        sketch.faces.clear()
        sketch.polylines.clear()
        return base

    @staticmethod
    def _point_is_referenced(sketch: Any, point_id: str) -> bool:
        point_id = str(point_id)
        for line in getattr(sketch, "lines", {}).values():
            if point_id in {line.start_point_id, line.end_point_id}:
                return True
        for arc in getattr(sketch, "arcs", {}).values():
            if point_id in {arc.start_point_id, arc.end_point_id, arc.control_point_id}:
                return True
        for circle in getattr(sketch, "circles", {}).values():
            if point_id in {circle.center_point_id, circle.radius_point_id}:
                return True
        return False

    def _rectangle_edit_data_from_face(self, face_id: str) -> tuple[tuple[float, float], tuple[float, float], tuple[str, ...], tuple[str, ...]] | None:
        face = self._state.sketch.faces.get(str(face_id))
        if face is None:
            return None
        if tuple(getattr(face, "hole_polygons", ()) or ()):  # not a simple rectangle edit target
            return None
        points = tuple((float(p[0]), float(p[1])) for p in tuple(getattr(face, "polygon_points", ()) or ()))
        if len(points) < 4:
            return None
        # Remove closing duplicate if present and reject non-rectangular regions.
        if len(points) > 1 and distance_xy(points[0], points[-1]) <= 1.0e-8:
            points = points[:-1]
        unique: list[tuple[float, float]] = []
        for pt in points:
            if not any(distance_xy(pt, other) <= 1.0e-6 for other in unique):
                unique.append(pt)
        if len(unique) != 4:
            return None
        xs = [p[0] for p in unique]
        ys = [p[1] for p in unique]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if max_x - min_x <= 1.0e-8 or max_y - min_y <= 1.0e-8:
            return None
        expected = {(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)}
        if any(not any(distance_xy(pt, ex) <= 1.0e-5 for ex in expected) for pt in unique):
            return None
        line_ids = tuple(str(eid) for eid in tuple(getattr(face, "boundary_entity_ids", ()) or ()) if str(eid) in self._state.sketch.lines)
        if len(line_ids) < 4:
            return None
        cleanup: list[str] = []
        for line_id in line_ids:
            line = self._state.sketch.lines.get(line_id)
            if line is not None:
                cleanup.extend((line.start_point_id, line.end_point_id))
        return (min_x, min_y), (max_x, max_y), tuple(dict.fromkeys(line_ids)), tuple(dict.fromkeys(cleanup))

    def _show_metric_overlay(self, ctx: Any, session: Any) -> None:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        ctx.overlay.show_window(
            metric_api.build_metric_edit_window(
                window_id=_METRIC_OVERLAY_ID,
                owner_tool=self.id,
                session=session,
                validate_button_id=_METRIC_VALIDATE_BUTTON_ID,
                cancel_button_id=_METRIC_CANCEL_BUTTON_ID,
                anchor="viewport_bottom_center",
                width_px=0,
                overlay_kind="metric_bar",
            )
        )
        self.services.rendering._render(ctx, sync_overlays=True, render=True)

    def _validate_metric_draft(self, ctx: Any) -> bool:
        draft = self._state.metric_draft
        if draft is None:
            ctx.overlay.hide_window(_METRIC_OVERLAY_ID)
            return False
        # ``_commit_metric_overlay_values`` reports back whether any geometry
        # was actually rebuilt. When the implicit-validate path fires (the user
        # clicks elsewhere to start a new shape) and the field values are
        # unchanged, we can skip the heavy snapshot + sketch compile that
        # would otherwise rerun the face solver on every Plan tracer click.
        had_pending = bool(getattr(draft, "pending_field_values", None))
        geometry_dirty = had_pending or not self._values_match_session(
            draft.session,
            self._collect_metric_overlay_values(ctx, draft),
        )
        if not self._commit_metric_overlay_values(ctx):
            return False
        draft = self._state.metric_draft
        if draft is None:
            ctx.overlay.hide_window(_METRIC_OVERLAY_ID)
            return False
        before = self.services.history._clone_snapshot(draft.base_snapshot) if geometry_dirty else None
        self._state.metric_draft = None
        ctx.overlay.hide_window(_METRIC_OVERLAY_ID)
        if geometry_dirty and before is not None:
            self.services.history._record_snapshot_command(ctx, f"Validate Plan tracer {self.services.overlay._label_for_tool(draft.mode)} metrics", before)
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            self.services.rendering._render(ctx, sync_overlays=True, render=True)
        else:
            # Geometry unchanged: just refresh the overlay and report. Skip the
            # face-solver compile/full re-render, which dominate chained-draw
            # workflows in dense sketches.
            self.services.rendering._render(ctx, sync_overlays=True, render=False)
        try:
            ctx.status.info(f"Validated {self.services.overlay._label_for_tool(draft.mode)} metrics.")
        except Exception:
            pass
        return True

    def _cancel_metric_draft(self, ctx: Any) -> bool:
        draft = self._state.metric_draft
        if draft is None:
            ctx.overlay.hide_window(_METRIC_OVERLAY_ID)
            return False
        self._state.metric_draft = None
        ctx.overlay.hide_window(_METRIC_OVERLAY_ID)
        self.services.history._restore_snapshot_state(ctx, draft.base_snapshot, render=True)
        try:
            ctx.status.info(f"Cancelled {self.services.overlay._label_for_tool(draft.mode)} metric edit.")
        except Exception:
            pass
        return True


    def remember_metric_value(self, field_id: str, value_text: str) -> bool:
        """Store an edited metric field without rebuilding the overlay immediately.

        Qt emits ``editingFinished`` before the Validate button receives its click.
        Rebuilding geometry from that focus-out event can rematerialise the overlay
        and eat the click.  Plan Tracer therefore treats text edits as pending and
        commits all visible field values atomically from Validate.
        """

        draft = self._state.metric_draft
        if draft is None:
            return False
        field_id = str(field_id)
        if field_id not in draft.session.fields:
            return False
        draft.pending_field_values[field_id] = str(value_text)
        return True

    def _collect_metric_overlay_values(self, ctx: Any, draft: _PlacementMetricDraft) -> dict[str, str]:
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        values: dict[str, str] = {}
        prefix = metric_api.metric_field_overlay_id(_METRIC_OVERLAY_ID, "")
        try:
            window = ctx.overlay.window(_METRIC_OVERLAY_ID)
        except Exception:
            window = None
        if window is not None:
            for field in tuple(getattr(window, "fields", ()) or ()):
                field_id = str(getattr(field, "id", "") or "")
                metric_field_id = field_id[len(prefix):] if field_id.startswith(prefix) else field_id
                if metric_field_id in draft.session.fields:
                    values[metric_field_id] = str(getattr(field, "value", "") or "")
        # Tool-level editingFinished callbacks are the freshest source when the
        # Qt event order is field-commit -> button-click.  They must therefore
        # win over the declarative manager values.
        values.update(dict(getattr(draft, "pending_field_values", {}) or {}))
        return values

    def _commit_metric_overlay_values(self, ctx: Any) -> bool:
        draft = self._state.metric_draft
        if draft is None:
            return False
        values = self._collect_metric_overlay_values(ctx, draft)
        if not values:
            return True
        session = draft.session
        previous_values = session.as_values()
        # Fast path: when validation fires because the user clicked elsewhere
        # to start a new shape (the implicit-accept path) the field values match
        # the ones already on the session and there's nothing to rebuild. The
        # full path snapshots/restores history and re-runs the sketch compile
        # for every Plan tracer click that opened a metric draft on the
        # previous click; skipping it shaved that hidden double compile out of
        # the chained drawing workflow.
        if not getattr(draft, "pending_field_values", None) and self._values_match_session(session, values):
            draft.pending_field_values.clear() if hasattr(draft, "pending_field_values") else None
            return True
        previous_snapshot = self.services.history._snapshot_state()
        try:
            for field_id, value_text in values.items():
                if field_id in session.fields and not apply_metric_field_update(draft, field_id, value_text):
                    raise ValueError(f"Unknown metric field {field_id!r}")
        except ValueError:
            for previous_field_id, previous_value in previous_values.items():
                if previous_field_id in session.fields:
                    session.replace_field_value(previous_field_id, previous_value)
            self.services.history._load_snapshot_contents(previous_snapshot)
            self._state.metric_draft = draft
            self._show_metric_overlay(ctx, session)
            return False
        rebuilt = self._rebuild_metric_draft_geometry(ctx, draft)
        if rebuilt:
            draft.pending_field_values.clear()
            self._sync_metric_overlay_field_values(ctx, session)
            return True
        for previous_field_id, previous_value in previous_values.items():
            if previous_field_id in session.fields:
                session.replace_field_value(previous_field_id, previous_value)
        self.services.history._load_snapshot_contents(previous_snapshot)
        self._state.metric_draft = draft
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._show_metric_overlay(ctx, session)
        try:
            ctx.status.info("Metric value rejected: geometry would become degenerate.")
        except Exception:
            pass
        return False

    def apply_metric_value(self, ctx: Any, field_id: str, value_text: str) -> bool:
        """Apply one metric field from the API overlay and rebuild the draft.

        The current Qt adapter only notifies button clicks, but this method is the
        stable tool-facing hook for the next UI pass.  Tests and future text-field
        callbacks can call it without knowing Plan Tracer geometry internals.
        """

        draft = self._state.metric_draft
        if draft is None:
            return False
        field_id = str(field_id)
        session = draft.session
        field = session.fields.get(field_id)
        if field is None:
            return False
        previous_values = session.as_values()
        previous_snapshot = self.services.history._snapshot_state()
        try:
            if not apply_metric_field_update(draft, field_id, value_text):
                return False
        except ValueError:
            self._show_metric_overlay(ctx, session)
            return False
        rebuilt = self._rebuild_metric_draft_geometry(ctx, draft)
        if rebuilt:
            # Do not rebuild the metric overlay on a successful field commit.
            # In Qt, clicking Validate while a QLineEdit still has focus first
            # emits editingFinished. Rebuilding the overlay from that focus-out
            # event destroys the Validate button under the mouse, so the first
            # click only appears to close/reopen the bar and the actual validate
            # action is lost. Keep the current widget alive, update the manager's
            # declarative field values for the next normal sync, and let the
            # pending button click continue.
            self._sync_metric_overlay_field_values(ctx, session)
            return True
        # A parsed value can still be geometrically invalid (zero length,
        # impossible arc radius, duplicate points after reconstruction, ...).
        # Restore both the live sketch and the typed session so the overlay and
        # geometry never disagree while the user keeps editing the same draft.
        for previous_field_id, previous_value in previous_values.items():
            if previous_field_id in session.fields:
                session.replace_field_value(previous_field_id, previous_value)
        self.services.history._load_snapshot_contents(previous_snapshot)
        self._state.metric_draft = draft
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._show_metric_overlay(ctx, session)
        try:
            ctx.status.info("Metric value rejected: geometry would become degenerate.")
        except Exception:
            pass
        return False


    def _values_match_session(self, session: Any, values: dict[str, str]) -> bool:
        """Return True when ``values`` would not change the active metric session.

        Used by the implicit-validate path: clicking elsewhere to start a new
        shape silently validates the previous metric draft. When the user did
        not edit anything, the captured field values already equal the active
        session, so the full rebuild/snapshot/compile dance can be skipped.
        Comparison goes through ``format_metric_value`` so display rounding
        matches the strings the overlay round-trips back to us.
        """

        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        for field_id, value_text in values.items():
            field = session.fields.get(field_id)
            if field is None:
                return False
            try:
                current = metric_api.format_metric_value(field)
            except Exception:
                return False
            if str(value_text).strip() != str(current).strip():
                return False
        return True

    def _sync_metric_overlay_field_values(self, ctx: Any, session: Any) -> None:
        """Refresh stored metric field text without rematerialising the Qt bar.

        Successful edits should update geometry immediately, but they must not
        destroy/recreate the focused overlay widget.  The Qt adapter will perform
        its ordinary deferred sync after the current event, so linked fields such
        as circle radius/diameter still converge without eating the Validate
        click that caused the focus-out commit.
        """

        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        try:
            for field in metric_api.field_tuple(session.fields):
                ctx.overlay.update_field(
                    _METRIC_OVERLAY_ID,
                    metric_api.metric_field_overlay_id(_METRIC_OVERLAY_ID, field.id),
                    metric_api.format_metric_value(field),
                )
        except Exception:
            pass

    def _rebuild_metric_draft_geometry(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        return self.services.metric_rebuilders.rebuild_metric_draft_geometry(ctx, draft)


__all__ = ["PlanTrace2DMetricsService"]
