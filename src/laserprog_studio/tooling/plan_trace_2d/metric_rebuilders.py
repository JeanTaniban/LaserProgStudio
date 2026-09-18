# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any

from .constants import (
    _MODE_ARC,
    _MODE_CIRCLE,
    _MODE_HALF_CIRCLE,
    _MODE_LINE,
    _MODE_RECTANGLE,
)
from .curve_intent import ArcIntent, HalfCircleIntent, arc_control_from_intent, curve_intent_metadata, distance_xy, half_circle_control_point
from .services import _PlanTrace2DService
from .state import _PlacementMetricDraft


class PlanTrace2DMetricRebuilderService(_PlanTrace2DService):
    """Rebuild the temporary sketch geometry for editable metric drafts.

    The metric service owns user-facing sessions and overlay validation. This
    service owns the shape-specific reconstruction policy so metric editing does
    not turn into another monolith.
    """

    def rebuild_metric_draft_geometry(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        if draft.mode == _MODE_LINE:
            return self._rebuild_line_metric_draft(ctx, draft)
        if draft.mode == _MODE_CIRCLE:
            return self._rebuild_circle_metric_draft(ctx, draft)
        if draft.mode == _MODE_RECTANGLE:
            return self._rebuild_rectangle_metric_draft(ctx, draft)
        if draft.mode == _MODE_HALF_CIRCLE:
            return self._rebuild_half_circle_metric_draft(ctx, draft)
        if draft.mode == _MODE_ARC:
            return self._rebuild_arc_metric_draft(ctx, draft)
        return False

    def _rebuild_line_metric_draft(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        if draft.start_xy is None or draft.end_xy is None:
            return False
        values = draft.session.as_values()
        length = max(float(values.get("length", 0.0)), 0.0)
        angle = math.radians(float(values.get("angle", 0.0)))
        start = draft.start_xy
        end = (float(start[0]) + math.cos(angle) * length, float(start[1]) + math.sin(angle) * length)
        self.services.history._load_snapshot_contents(draft.base_snapshot)
        start_point = self.services.sketch_sync._add_or_reuse_sketch_point(start)
        end_point = self.services.sketch_sync._add_or_reuse_sketch_point(end)
        self._state.pending_line_start_id = None
        if start_point.id == end_point.id:
            return False
        line = self._state.sketch.add_line(start_point.id, end_point.id)
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=draft.mode,
            base_snapshot=self.services.history._clone_snapshot(draft.base_snapshot),
            session_id=draft.session_id,
            session=draft.session,
            start_xy=start,
            end_xy=end,
            entity_ids=(line.id, start_point.id, end_point.id),
        )
        return True

    def _rebuild_circle_metric_draft(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        if draft.center_xy is None or draft.radius_xy is None:
            return False
        values = draft.session.as_values()
        radius = max(float(values.get("radius", 0.0)), 0.0)
        if radius <= 1.0e-8:
            return False
        center = draft.center_xy
        original_radius = self._distance_xy(center, draft.radius_xy)
        if original_radius <= 1.0e-8:
            direction = (1.0, 0.0)
        else:
            direction = ((float(draft.radius_xy[0]) - float(center[0])) / original_radius, (float(draft.radius_xy[1]) - float(center[1])) / original_radius)
        radius_xy = (float(center[0]) + direction[0] * radius, float(center[1]) + direction[1] * radius)
        self.services.history._load_snapshot_contents(draft.base_snapshot)
        center_point = self.services.sketch_sync._add_or_reuse_sketch_point(center)
        radius_point = self.services.sketch_sync._add_or_reuse_sketch_point(radius_xy)
        self._state.pending_circle_center_id = None
        if center_point.id == radius_point.id:
            return False
        circle = self._state.sketch.add_circle(center_point.id, radius_point.id)
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=draft.mode,
            base_snapshot=self.services.history._clone_snapshot(draft.base_snapshot),
            session_id=draft.session_id,
            session=draft.session,
            center_xy=center,
            radius_xy=radius_xy,
            entity_ids=(circle.id, center_point.id, radius_point.id),
        )
        return True

    def _rebuild_rectangle_metric_draft(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        if draft.first_xy is None or draft.opposite_xy is None:
            return False
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        values = draft.session.as_values()
        width = max(float(values.get("width", 0.0)), 0.0)
        height = max(float(values.get("height", 0.0)), 0.0)
        if width <= 1.0e-8 or height <= 1.0e-8:
            return False
        first = draft.first_xy
        opposite = metric_api.rectangle_opposite_from_metrics(first, draft.opposite_xy, width=width, height=height)
        self.services.history._load_snapshot_contents(draft.base_snapshot)
        first_point = self.services.sketch_sync._add_or_reuse_sketch_point(first)
        opposite_point = self.services.sketch_sync._add_or_reuse_sketch_point(opposite)
        self._state.pending_rectangle_corner_id = None
        created_edges = self.services.drawing._add_axis_aligned_rectangle(first_point.id, opposite_point.id, first, opposite)
        if not created_edges:
            return False
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=draft.mode,
            base_snapshot=self.services.history._clone_snapshot(draft.base_snapshot),
            session_id=draft.session_id,
            session=draft.session,
            first_xy=first,
            opposite_xy=opposite,
            entity_ids=tuple(created_edges),
        )
        return True

    def _rebuild_half_circle_metric_draft(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        if draft.start_xy is None or draft.end_xy is None:
            return False
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        values = draft.session.as_values()
        radius = max(float(values.get("radius", 0.0)), 0.0)
        diameter = max(float(values.get("diameter", radius * 2.0)), 0.0)
        angle_degrees = float(values.get("angle", self._line_metrics_from_xy(draft.start_xy, draft.end_xy)[1]))
        if diameter <= 1.0e-8:
            return False
        start = draft.start_xy
        end = metric_api.half_circle_end_from_metrics(start, diameter=diameter, angle_degrees=angle_degrees)
        self.services.history._load_snapshot_contents(draft.base_snapshot)
        start_point = self.services.sketch_sync._add_or_reuse_sketch_point(start)
        end_point = self.services.sketch_sync._add_or_reuse_sketch_point(end)
        self._state.pending_half_circle_start_id = None
        if start_point.id == end_point.id:
            return False
        half_intent = draft.half_circle_intent or HalfCircleIntent.from_points(start, end)
        half_intent = HalfCircleIntent.from_points(start, end, side=half_intent.side)
        control_xy = half_intent.control_xy()
        control = self.services.sketch_sync._add_or_reuse_sketch_point(control_xy)
        if control.id in {start_point.id, end_point.id}:
            return False
        arc = self._state.sketch.add_arc(start_point.id, end_point.id, control.id)
        diameter_line = self._state.sketch.add_line(start_point.id, end_point.id)
        diameter_line.metadata.update({"generated_by": "half_circle_diameter", "half_circle_arc_id": arc.id})
        arc.metadata.update({"curve_type": "half_circle", "diameter_line_id": diameter_line.id, **curve_intent_metadata(side=half_intent.side, kind="half_circle")})
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=draft.mode,
            base_snapshot=self.services.history._clone_snapshot(draft.base_snapshot),
            session_id=draft.session_id,
            session=draft.session,
            start_xy=start,
            end_xy=end,
            entity_ids=(arc.id, diameter_line.id, start_point.id, end_point.id, control.id),
            half_circle_intent=half_intent,
        )
        return True

    def _rebuild_arc_metric_draft(self, ctx: Any, draft: _PlacementMetricDraft) -> bool:
        if draft.start_xy is None or draft.end_xy is None or draft.control_xy is None:
            return False
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        values = draft.session.as_values()
        radius = max(float(values.get("radius", 0.0)), 0.0)
        angle_degrees = float(values.get("angle", 0.0))
        start = draft.start_xy
        end = draft.end_xy
        if self._distance_xy(start, end) <= 1.0e-8:
            return False
        arc_intent = draft.arc_intent or ArcIntent.from_points(start, end, draft.control_xy)
        control_xy = arc_control_from_intent(
            start,
            end,
            side=arc_intent.side,
            radius=radius,
            angle_degrees=angle_degrees if angle_degrees > 0.0 else None,
            major=bool(angle_degrees > 180.0) if angle_degrees > 0.0 else arc_intent.major,
        )
        if control_xy is None:
            return False
        arc_intent = arc_intent.with_control(control_xy, sweep_degrees=angle_degrees if angle_degrees > 0.0 else None)
        self.services.history._load_snapshot_contents(draft.base_snapshot)
        start_point = self.services.sketch_sync._add_or_reuse_sketch_point(start)
        end_point = self.services.sketch_sync._add_or_reuse_sketch_point(end)
        control_point = self.services.sketch_sync._add_or_reuse_sketch_point(control_xy)
        self._state.pending_arc_start_id = None
        self._state.pending_arc_end_id = None
        if len({start_point.id, end_point.id, control_point.id}) != 3:
            return False
        arc = self._state.sketch.add_arc(start_point.id, end_point.id, control_point.id)
        arc.metadata.update(curve_intent_metadata(side=arc_intent.side, major=arc_intent.major, kind="arc"))
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._state.metric_draft = _PlacementMetricDraft(
            mode=draft.mode,
            base_snapshot=self.services.history._clone_snapshot(draft.base_snapshot),
            session_id=draft.session_id,
            session=draft.session,
            start_xy=start,
            end_xy=end,
            control_xy=control_xy,
            entity_ids=(arc.id, start_point.id, end_point.id, control_point.id),
            arc_intent=arc_intent,
        )
        return True


    @staticmethod
    def _distance_xy(first: tuple[float, float], second: tuple[float, float]) -> float:
        return distance_xy(first, second)

    @staticmethod
    def _line_metrics_from_xy(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
        return line_metrics_from_xy(start, end)


def distance_xy(first: tuple[float, float], second: tuple[float, float]) -> float:
    return ((float(second[0]) - float(first[0])) ** 2 + (float(second[1]) - float(first[1])) ** 2) ** 0.5


def line_metrics_from_xy(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    return (dx * dx + dy * dy) ** 0.5, math.degrees(math.atan2(dy, dx))


__all__ = ["PlanTrace2DMetricRebuilderService", "distance_xy", "line_metrics_from_xy"]
