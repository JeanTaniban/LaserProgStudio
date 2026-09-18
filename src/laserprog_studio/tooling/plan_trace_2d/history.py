# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api.core import FunctionCommand
from laserprog_studio.tool_api.core import ToolEvent, ToolEventType

from .constants import _METRIC_OVERLAY_ID
from .services import _PlanTrace2DService
from .state import _PlanTrace2DSnapshot

class PlanTrace2DHistoryService(_PlanTrace2DService):
    def _snapshot_state(self) -> _PlanTrace2DSnapshot:
        return _PlanTrace2DSnapshot(
            sketch=self._state.sketch.clone(),
            next_point_index=int(self._state.next_point_index),
            pending_line_start_id=self._state.pending_line_start_id,
            pending_polyline_last_id=self._state.pending_polyline_last_id,
            pending_rectangle_corner_id=self._state.pending_rectangle_corner_id,
            pending_circle_center_id=self._state.pending_circle_center_id,
            pending_arc_start_id=self._state.pending_arc_start_id,
            pending_arc_end_id=self._state.pending_arc_end_id,
            pending_bezier_start_id=self._state.pending_bezier_start_id,
            pending_bezier_end_id=self._state.pending_bezier_end_id,
            pending_bezier_control_1_id=self._state.pending_bezier_control_1_id,
            pending_half_circle_start_id=self._state.pending_half_circle_start_id,
            pending_dimension_start_id=self._state.pending_dimension_start_id,
            pending_dimension_line_id=self._state.pending_dimension_line_id,
            motif_face_holes_by_outer_signature=dict(self._state.motif_face_holes_by_outer_signature),
            motif_face_hole_kinds=dict(self._state.motif_face_hole_kinds),
            motif_assignments_by_outer_signature={str(k): dict(v) for k, v in self._state.motif_assignments_by_outer_signature.items()},
        )

    @staticmethod
    def _clone_snapshot(snapshot: _PlanTrace2DSnapshot) -> _PlanTrace2DSnapshot:
        return _PlanTrace2DSnapshot(
            sketch=snapshot.sketch.clone(),
            next_point_index=int(snapshot.next_point_index),
            pending_line_start_id=snapshot.pending_line_start_id,
            pending_polyline_last_id=snapshot.pending_polyline_last_id,
            pending_rectangle_corner_id=snapshot.pending_rectangle_corner_id,
            pending_circle_center_id=snapshot.pending_circle_center_id,
            pending_arc_start_id=snapshot.pending_arc_start_id,
            pending_arc_end_id=snapshot.pending_arc_end_id,
            pending_bezier_start_id=snapshot.pending_bezier_start_id,
            pending_bezier_end_id=snapshot.pending_bezier_end_id,
            pending_bezier_control_1_id=snapshot.pending_bezier_control_1_id,
            pending_half_circle_start_id=snapshot.pending_half_circle_start_id,
            pending_dimension_start_id=snapshot.pending_dimension_start_id,
            pending_dimension_line_id=snapshot.pending_dimension_line_id,
            motif_face_holes_by_outer_signature=dict(getattr(snapshot, "motif_face_holes_by_outer_signature", {}) or {}),
            motif_face_hole_kinds=dict(getattr(snapshot, "motif_face_hole_kinds", {}) or {}),
            motif_assignments_by_outer_signature={str(k): dict(v) for k, v in (getattr(snapshot, "motif_assignments_by_outer_signature", {}) or {}).items()},
        )

    def _load_snapshot_contents(self, snapshot: _PlanTrace2DSnapshot) -> None:
        self._state.sketch = snapshot.sketch.clone()
        self._state.next_point_index = int(snapshot.next_point_index)
        self._state.pending_line_start_id = snapshot.pending_line_start_id
        self._state.pending_polyline_last_id = snapshot.pending_polyline_last_id
        self._state.pending_rectangle_corner_id = snapshot.pending_rectangle_corner_id
        self._state.pending_circle_center_id = snapshot.pending_circle_center_id
        self._state.pending_arc_start_id = snapshot.pending_arc_start_id
        self._state.pending_arc_end_id = snapshot.pending_arc_end_id
        self._state.pending_bezier_start_id = snapshot.pending_bezier_start_id
        self._state.pending_bezier_end_id = snapshot.pending_bezier_end_id
        self._state.pending_bezier_control_1_id = snapshot.pending_bezier_control_1_id
        self._state.pending_half_circle_start_id = snapshot.pending_half_circle_start_id
        self._state.pending_dimension_start_id = snapshot.pending_dimension_start_id
        self._state.pending_dimension_line_id = snapshot.pending_dimension_line_id
        self._state.motif_face_holes_by_outer_signature = dict(getattr(snapshot, "motif_face_holes_by_outer_signature", {}) or {})
        self._state.motif_face_hole_kinds = dict(getattr(snapshot, "motif_face_hole_kinds", {}) or {})
        self._state.motif_assignments_by_outer_signature = {str(k): dict(v) for k, v in (getattr(snapshot, "motif_assignments_by_outer_signature", {}) or {}).items()}

    def _restore_snapshot_state(self, ctx: Any, snapshot: _PlanTrace2DSnapshot, *, render: bool = True) -> None:
        self._load_snapshot_contents(snapshot)
        self._state.active_drag_snapshot = None
        self._state.active_transform_session = None
        self._state.metric_draft = None
        try:
            ctx.overlay.hide_window(_METRIC_OVERLAY_ID)
        except Exception:
            pass
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            pass
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=render)
        self.services.rendering._render(ctx, sync_overlays=True, render=render)

    @staticmethod
    def _snapshots_equal(first: _PlanTrace2DSnapshot, second: _PlanTrace2DSnapshot) -> bool:
        return first == second

    def _record_snapshot_command(
        self,
        ctx: Any,
        label: str,
        before: _PlanTrace2DSnapshot,
        *,
        assume_changed: bool = False,
    ) -> None:
        """Record one detached before/after snapshot without cloning them again.

        ``_snapshot_state`` already returns an independent sketch clone.  The old
        history path immediately deep-cloned both snapshots a second time before
        capturing them in the command closures.  On dense Plan Tracer documents
        that turned one edit into four complete sketch copies and produced the
        visible post-Delete freeze.

        Snapshot restoration always clones into the live state, so the detached
        command snapshots themselves are safe to retain directly.
        """

        after = self._snapshot_state()
        if not assume_changed and self._snapshots_equal(before, after):
            return

        before_snapshot = before
        after_snapshot = after

        command = FunctionCommand(
            str(label),
            do_func=lambda snapshot=after_snapshot: self._restore_snapshot_state(ctx, snapshot, render=True),
            undo_func=lambda snapshot=before_snapshot: self._restore_snapshot_state(ctx, snapshot, render=True),
        )
        recorder = getattr(ctx.commands, "record_executed", None)
        if callable(recorder):
            recorder(command)
        else:  # pragma: no cover - command stacks without record_executed
            ctx.commands.execute(command)

    @staticmethod
    def _is_undo_shortcut(event: ToolEvent) -> bool:
        return event.type == ToolEventType.KEY_PRESS and event.ctrl and not event.shift and (event.key or "").lower() == "z"

    @staticmethod
    def _is_redo_shortcut(event: ToolEvent) -> bool:
        key = (event.key or "").lower()
        return event.type == ToolEventType.KEY_PRESS and event.ctrl and (key == "y" or (event.shift and key == "z"))

    def _undo_last(self, ctx: Any) -> bool:
        if not ctx.commands.undo():
            ctx.status.info("Nothing to undo in Plan tracer.")
            return True
        ctx.status.info("Plan tracer undo.")
        return True

    def _redo_last(self, ctx: Any) -> bool:
        if not ctx.commands.redo():
            ctx.status.info("Nothing to redo in Plan tracer.")
            return True
        ctx.status.info("Plan tracer redo.")
        return True


__all__ = ["PlanTrace2DHistoryService"]
