# -*- coding: utf-8 -*-
"""Plan Tracer Mirror workflow, overlay, preview and add-only commit.

Geometry mathematics lives in :mod:`mirror_geometry`; state transitions in
:mod:`mirror_state`.  This service only adapts the pure plan to the sketch API
and the projected drawing/overlay runtimes.
"""
from __future__ import annotations

import copy
import math
from typing import Any, Iterable

from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api import visual
from laserprog_studio.tool_api.core import MouseButton, ToolEventType

from .constants import _MODE_MODIFY
from .mirror_geometry import (
    ArcPrimitive,
    BezierPrimitive,
    CirclePrimitive,
    LinePrimitive,
    MirrorAxis,
    MirrorPlan,
    MirrorPrimitive,
    PointPrimitive,
    build_mirror_plan,
    sample_primitive,
)
from .mirror_state import MirrorStage, MirrorWorkflow
from .selection_edit import PasteResult, SketchSelection
from .services import _PlanTrace2DService

Point2 = tuple[float, float]

MIRROR_WINDOW_ID = "plan_trace_2d.mirror"
MIRROR_ACTION_PREFIX = "plan_trace_2d.mirror.action."
MIRROR_VISUAL_PREFIX = "plan_trace_2d:mirror:"
_MIRROR_AXIS_ID = MIRROR_VISUAL_PREFIX + "axis"
_MIRROR_PREVIEW_SEGMENTS_ID = MIRROR_VISUAL_PREFIX + "preview:segments"
_MIRROR_PREVIEW_POINTS_ID = MIRROR_VISUAL_PREFIX + "preview:points"
_MIRROR_INFO_FIELD_ID = "plan_trace_2d.mirror.info"


class PlanTrace2DMirrorOverlay:
    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        value = str(button_id or "")
        if value.startswith(MIRROR_ACTION_PREFIX):
            return value[len(MIRROR_ACTION_PREFIX):]
        return None

    @staticmethod
    def _button(action: str, label: str, icon: str, tooltip: str, *, enabled: bool = True, style: str = "secondary") -> visual.ToolButtonSpec:
        return visual.ToolButtonSpec(
            id=MIRROR_ACTION_PREFIX + action,
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
        )

    def sync(self, ctx: Any, service: "PlanTrace2DMirrorService") -> None:
        stage = service.workflow.stage
        plan = service.plan
        if stage is MirrorStage.AXIS_START:
            instruction = "Click the first point of the symmetry axis."
        elif stage is MirrorStage.AXIS_END:
            instruction = "Click the second point. Smart Snap is active."
        elif plan is None:
            instruction = "The axis is invalid. Restart it."
        elif plan.addition_count:
            instruction = (
                f"Preview: {plan.addition_count} addition(s) · "
                f"{plan.split_source_count} crossing element(s) split."
            )
        else:
            instruction = "The chosen geometry is already symmetric about this axis."
        scope = "Selected geometry" if service.uses_selection else "Whole sketch"
        ctx.overlay.show_window(
            visual.OverlayWindowSpec(
                id=MIRROR_WINDOW_ID,
                title="Mirror",
                owner_tool=service.id,
                fields=[
                    visual.OverlayFieldSpec(_MIRROR_INFO_FIELD_ID, scope, instruction, kind="info"),
                ],
                buttons=[
                    self._button(
                        "apply",
                        "Apply",
                        "tool.apply",
                        "Add the mirrored geometry without removing the source.",
                        enabled=bool(stage is MirrorStage.PREVIEW and plan is not None and plan.addition_count),
                        style="primary",
                    ),
                    self._button("restart", "New axis", "sketch.line", "Discard this axis and pick two new points.", enabled=stage is not MirrorStage.AXIS_START),
                    self._button("cancel", "Cancel", "tool.close", "Close Mirror without changing the sketch."),
                ],
                anchor="viewport_top_right",
                overlay_kind="popover",
                width_px=310,
                movable=True,
                persistent=True,
                close_on_click_outside=False,
                cursor_offset_px=(0, 84),
            )
        )

    @staticmethod
    def hide(ctx: Any) -> None:
        try:
            ctx.overlay.hide_window(MIRROR_WINDOW_ID)
        except Exception:
            pass


class PlanTrace2DMirrorService(_PlanTrace2DService):
    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.overlay = PlanTrace2DMirrorOverlay()
        self.workflow = MirrorWorkflow()
        self.scope_selection: SketchSelection | None = None
        self.uses_selection = False
        self.axis_start: Point2 | None = None
        self.axis_end: Point2 | None = None
        self.hover_xy: Point2 | None = None
        self.plan: MirrorPlan | None = None
        self._visual_ids: tuple[str, ...] = ()
        self._last_ctx: Any | None = None

    def activate(self, ctx: Any) -> None:
        self._last_ctx = ctx
        selected = self.services.selection_edit.selected_entities(ctx, expand_faces=True)
        self.uses_selection = selected.entity_count > 0
        self.scope_selection = selected if self.uses_selection else None
        self.workflow.restart()
        self.axis_start = None
        self.axis_end = None
        self.hover_xy = None
        self.plan = None
        self._clear_preview(ctx, render=False)
        self.overlay.sync(ctx, self)
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            if self.uses_selection:
                ctx.status.info("Mirror: the current Plan Tracer selection is locked as the source. Pick two axis points.")
            else:
                ctx.status.info("Mirror: no selection, so the whole sketch will be completed symmetrically. Pick two axis points.")
        except Exception:
            pass

    def deactivate(self, ctx: Any, *, render: bool = True) -> None:
        self._clear_preview(ctx, render=False)
        self.overlay.hide(ctx)
        self.workflow.restart()
        self.axis_start = None
        self.axis_end = None
        self.hover_xy = None
        self.plan = None
        self.scope_selection = None
        self.uses_selection = False
        if render:
            self.services.rendering._render(ctx, sync_overlays=True, render=True)

    def handle_escape(self, ctx: Any) -> bool:
        if self.workflow.stage is MirrorStage.AXIS_START:
            return False
        self.restart_axis(ctx)
        return True

    def handle_button(self, ctx: Any, button_id: str) -> bool:
        action = self.overlay.action_from_button(button_id)
        if action is None:
            return False
        if action == "apply":
            self.apply(ctx)
            return True
        if action == "restart":
            self.restart_axis(ctx)
            return True
        if action == "cancel":
            self.services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="mirror_cancel", render=True)
            return True
        return True

    def restart_axis(self, ctx: Any) -> None:
        self.workflow.restart()
        self.axis_start = None
        self.axis_end = None
        self.hover_xy = None
        self.plan = None
        self._clear_preview(ctx, render=False)
        self.overlay.sync(ctx, self)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            ctx.status.info("Mirror: click the first point of the new symmetry axis.")
        except Exception:
            pass

    def handle_event(self, ctx: Any, event: Any) -> bool:
        self._last_ctx = ctx
        if event.screen_pos is None:
            return False
        if event.type is ToolEventType.MOUSE_MOVE:
            self.hover_xy = self._snapped_xy(ctx, event)
            if self.workflow.stage is MirrorStage.AXIS_END:
                self._sync_preview(ctx, render=True, dynamic_axis_end=self.hover_xy)
            else:
                # Keep the normal Plan Tracer cursor/snap directives alive even
                # before the first point and after the fixed preview.
                self.services.snap._update_cursor(ctx, event, render=True)
            return True
        if event.type is ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
            xy = self._snapped_xy(ctx, event)
            if self.workflow.stage is MirrorStage.AXIS_START:
                self.axis_start = xy
                self.axis_end = None
                self.plan = None
                self.workflow.begin_axis()
                self.overlay.sync(ctx, self)
                self._sync_preview(ctx, render=True, dynamic_axis_end=xy)
                try:
                    ctx.status.info("Mirror: first axis point fixed. Click the second point.")
                except Exception:
                    pass
                return True
            if self.workflow.stage is MirrorStage.AXIS_END:
                if self.axis_start is None or math.dist(self.axis_start, xy) <= 1.0e-7:
                    try:
                        ctx.status.info("Mirror axis needs two distinct points.")
                    except Exception:
                        pass
                    return True
                self.axis_end = xy
                self._build_plan()
                self.workflow.preview_ready()
                self.overlay.sync(ctx, self)
                self._sync_preview(ctx, render=True)
                try:
                    if self.plan is not None and self.plan.addition_count:
                        ctx.status.info(f"Mirror preview ready: {self.plan.addition_count} add-only element(s). Click Apply.")
                    else:
                        ctx.status.info("Mirror: the current geometry is already symmetric for this axis.")
                except Exception:
                    pass
                return True
            return True
        return True

    def _snapped_xy(self, ctx: Any, event: Any) -> Point2:
        display_world = self.services.snap._update_cursor(ctx, event, render=False)
        semantic = self.services.coordinates.display_world_to_semantic(display_world)
        return self.services.coordinates.semantic_world_to_sketch_xy(semantic)

    def _all_selection(self) -> SketchSelection:
        sketch = self._state.sketch
        return SketchSelection(
            point_ids=frozenset(sketch.points),
            line_ids=frozenset(sketch.lines),
            arc_ids=frozenset(sketch.arcs),
            bezier_ids=frozenset(sketch.beziers),
            circle_ids=frozenset(sketch.circles),
            face_ids=frozenset(sketch.faces),
        )

    def _primitives_for_selection(self, selection: SketchSelection) -> tuple[MirrorPrimitive, ...]:
        sketch = self._state.sketch
        result: list[MirrorPrimitive] = []
        support_points: set[str] = set()
        for line_id in sorted(selection.line_ids):
            line = sketch.lines.get(line_id)
            if line is None:
                continue
            start = sketch.points.get(line.start_point_id)
            end = sketch.points.get(line.end_point_id)
            if start is None or end is None:
                continue
            support_points.update((line.start_point_id, line.end_point_id))
            result.append(LinePrimitive(line.id, start.position, end.position, copy.deepcopy(line.metadata)))
        for arc_id in sorted(selection.arc_ids):
            arc = sketch.arcs.get(arc_id)
            if arc is None:
                continue
            points = [sketch.points.get(value) for value in (arc.start_point_id, arc.end_point_id, arc.control_point_id)]
            if any(point is None for point in points):
                continue
            support_points.update((arc.start_point_id, arc.end_point_id, arc.control_point_id))
            result.append(ArcPrimitive(arc.id, points[0].position, points[1].position, points[2].position, copy.deepcopy(arc.metadata)))  # type: ignore[union-attr]
        for bezier_id in sorted(selection.bezier_ids):
            bezier = sketch.beziers.get(bezier_id)
            if bezier is None:
                continue
            ids = (bezier.start_point_id, bezier.control_1_point_id, bezier.control_2_point_id, bezier.end_point_id)
            points = [sketch.points.get(value) for value in ids]
            if any(point is None for point in points):
                continue
            support_points.update(ids)
            result.append(BezierPrimitive(
                bezier.id,
                points[0].position,  # type: ignore[union-attr]
                points[1].position,  # type: ignore[union-attr]
                points[2].position,  # type: ignore[union-attr]
                points[3].position,  # type: ignore[union-attr]
                copy.deepcopy(bezier.metadata),
            ))
        for circle_id in sorted(selection.circle_ids):
            circle = sketch.circles.get(circle_id)
            if circle is None:
                continue
            center = sketch.points.get(circle.center_point_id)
            radius = sketch.points.get(circle.radius_point_id)
            if center is None or radius is None:
                continue
            support_points.update((circle.center_point_id, circle.radius_point_id))
            result.append(CirclePrimitive(circle.id, center.position, radius.position, copy.deepcopy(circle.metadata)))
        # Only genuinely standalone selected points are copied separately.
        for point_id in sorted(set(selection.point_ids) - support_points):
            point = sketch.points.get(point_id)
            if point is not None:
                result.append(PointPrimitive(point.id, point.position, copy.deepcopy(point.metadata)))
        return tuple(result)

    def _build_plan(self) -> None:
        if self.axis_start is None or self.axis_end is None:
            self.plan = None
            return
        axis = MirrorAxis(self.axis_start, self.axis_end)
        selection = self.scope_selection if self.uses_selection and self.scope_selection is not None else self._all_selection()
        sources = self._primitives_for_selection(selection)
        existing = self._primitives_for_selection(self._all_selection())
        self.plan = build_mirror_plan(sources, axis, existing=existing, tolerance=1.0e-6)

    def _replace_preview(self, ctx: Any, primitives: list[Any], *, render: bool) -> None:
        registry = ctx.projected_drawing.for_tool(self.id)
        next_ids = tuple(str(item.id) for item in primitives)
        stale = tuple(value for value in self._visual_ids if value not in set(next_ids))
        with registry.batch():
            if stale:
                registry.remove_many(stale, render=False)
            if primitives:
                registry.add_many(primitives, replace=True, render=False)
        self._visual_ids = next_ids
        if render:
            self.services.rendering._render(ctx, sync_overlays=False, render=True)

    def _sync_preview(self, ctx: Any, *, render: bool, dynamic_axis_end: Point2 | None = None) -> None:
        start = self.axis_start
        end = dynamic_axis_end or self.axis_end
        primitives: list[Any] = []
        if start is not None and end is not None and math.dist(start, end) > 1.0e-9:
            primitives.append(draw2d.line(
                _MIRROR_AXIS_ID,
                self.services.coordinates.sketch_xy_to_display_world(start),
                self.services.coordinates.sketch_xy_to_display_world(end),
                color="#F59E0B",
                width_px=2.6,
                opacity=1.0,
                layer=98,
                metadata={"projected_no_selection_actor": True, "plan_trace_role": "mirror_axis"},
            ))
        plan = self.plan if dynamic_axis_end is None else None
        segments: list[tuple[Point2, Point2]] = []
        points: list[Point2] = []
        if plan is not None:
            budget = 18000
            for primitive in plan.additions:
                sampled = sample_primitive(primitive, segments=28)
                if isinstance(primitive, PointPrimitive):
                    points.extend(sampled)
                else:
                    segments.extend(zip(sampled, sampled[1:]))
                if len(segments) >= budget:
                    break
        if segments:
            primitives.append(draw2d.segment_batch(
                _MIRROR_PREVIEW_SEGMENTS_ID,
                tuple((
                    self.services.coordinates.sketch_xy_to_display_world(a),
                    self.services.coordinates.sketch_xy_to_display_world(b),
                ) for a, b in segments[:18000]),
                color="#10B981",
                width_px=2.6,
                opacity=0.94,
                layer=97,
            ))
        if points:
            primitives.append(draw2d.point_cloud(
                _MIRROR_PREVIEW_POINTS_ID,
                tuple(self.services.coordinates.sketch_xy_to_display_world(point) for point in points[:5000]),
                color="#6EE7B7",
                size_px=5.0,
                opacity=0.95,
                layer=97,
            ))
        self._replace_preview(ctx, primitives, render=render)

    def _clear_preview(self, ctx: Any, *, render: bool) -> None:
        if self._visual_ids:
            try:
                ctx.projected_drawing.for_tool(self.id).remove_many(self._visual_ids, render=False)
            except Exception:
                pass
        self._visual_ids = ()
        if render:
            self.services.rendering._render(ctx, sync_overlays=False, render=True)

    def apply(self, ctx: Any) -> bool:
        """Commit the add-only plan transactionally.

        Face reconstruction is intentionally delayed until every mirrored
        primitive has been inserted.  Should the shared sketch compiler reject
        the result, the exact pre-Mirror snapshot is restored before control is
        returned to the user; a failed symmetry can therefore never leave a
        half-created contour in the document.
        """

        plan = self.plan
        if self.workflow.stage is not MirrorStage.PREVIEW or plan is None or not plan.additions:
            return False
        before = self.services.history._snapshot_state()
        try:
            result = self._commit_additions(plan.additions)
            if not result.created_count:
                try:
                    ctx.status.info("Mirror: no new geometry was necessary.")
                except Exception:
                    pass
                return False
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
        except Exception as exc:
            # Restore topology and counters, then keep the Mirror preview active
            # so the user can choose another axis instead of being left with a
            # partially committed sketch.
            self.services.history._restore_snapshot_state(ctx, before, render=False)
            self.services.snap_targets.invalidate_geometry_cache()
            self.overlay.sync(ctx, self)
            self.services.rendering._render(ctx, sync_overlays=True, render=True)
            try:
                ctx.status.info(f"Mirror was not applied; the sketch was restored ({exc}).")
            except Exception:
                pass
            return False

        self.services.history._record_snapshot_command(ctx, "Mirror Plan Tracer geometry", before)
        self.services.selection_edit.select_paste_result(ctx, result)
        self.services.snap_targets.invalidate_geometry_cache()
        self._clear_preview(ctx, render=False)
        try:
            ctx.status.info(
                f"Mirror added {result.created_count} element(s); original geometry was preserved."
            )
        except Exception:
            pass
        self.services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="mirror_apply", render=True)
        return True

    def _commit_additions(self, additions: Iterable[MirrorPrimitive]) -> PasteResult:
        sketch = self._state.sketch
        tolerance = 1.0e-7
        point_index: dict[tuple[int, int], list[str]] = {}
        for point_id, point in sketch.points.items():
            key = (round(point.position[0] / tolerance), round(point.position[1] / tolerance))
            point_index.setdefault(key, []).append(point_id)

        created_points: list[str] = []
        created_lines: list[str] = []
        created_arcs: list[str] = []
        created_beziers: list[str] = []
        created_circles: list[str] = []

        def point_id_at(position: Point2, metadata: dict[str, Any] | None = None) -> str:
            key = (round(position[0] / tolerance), round(position[1] / tolerance))
            for point_id in point_index.get(key, ()):
                point = sketch.points.get(point_id)
                if point is not None and math.dist(point.position, position) <= tolerance:
                    return point_id
            point_id = f"{self.id}:point:{self._state.next_point_index:04d}"
            self._state.next_point_index += 1
            point = sketch.add_point(position, point_id=point_id)
            point.metadata.update(copy.deepcopy(dict(metadata or {})))
            point.metadata["generated_by"] = "mirror"
            point_index.setdefault(key, []).append(point.id)
            created_points.append(point.id)
            return point.id

        for primitive in additions:
            metadata = copy.deepcopy(dict(getattr(primitive, "metadata", {}) or {}))
            if isinstance(primitive, PointPrimitive):
                point_id_at(primitive.point, metadata)
            elif isinstance(primitive, LinePrimitive):
                start = point_id_at(primitive.start)
                end = point_id_at(primitive.end)
                if start == end:
                    continue
                entity = sketch.add_line(start, end)
                entity.metadata.update(metadata)
                created_lines.append(entity.id)
            elif isinstance(primitive, ArcPrimitive):
                start = point_id_at(primitive.start)
                end = point_id_at(primitive.end)
                control = point_id_at(primitive.control)
                if len({start, end, control}) < 3:
                    continue
                entity = sketch.add_arc(start, end, control)
                entity.metadata.update(metadata)
                created_arcs.append(entity.id)
            elif isinstance(primitive, BezierPrimitive):
                start = point_id_at(primitive.start)
                control_1 = point_id_at(primitive.control_1)
                control_2 = point_id_at(primitive.control_2)
                end = point_id_at(primitive.end)
                if start == end:
                    continue
                entity = sketch.add_bezier(start, end, control_1, control_2, metadata=metadata)
                created_beziers.append(entity.id)
            elif isinstance(primitive, CirclePrimitive):
                center = point_id_at(primitive.center)
                radius = point_id_at(primitive.radius_point)
                if center == radius:
                    continue
                entity = sketch.add_circle(center, radius)
                entity.metadata.update(metadata)
                created_circles.append(entity.id)

        return PasteResult(
            tuple(created_points),
            tuple(created_lines),
            tuple(created_arcs),
            tuple(created_beziers),
            tuple(created_circles),
        )


__all__ = ["MIRROR_WINDOW_ID", "PlanTrace2DMirrorService"]
