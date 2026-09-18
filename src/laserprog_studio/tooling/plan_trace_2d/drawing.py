# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .curve_intent import ArcIntent, HalfCircleIntent, curve_intent_metadata, half_circle_control_point
from .services import _PlanTrace2DService
from .state import _PlanTrace2DSnapshot

class PlanTrace2DDrawingService(_PlanTrace2DService):

    def _handle_polyline_press(self, ctx: Any, world: tuple[float, float, float], *, base_snapshot: _PlanTrace2DSnapshot | None = None) -> None:
        """Place one segment of a chained polyline.

        Polyline is intentionally represented as normal sketch lines.  The sketch
        compiler already rebuilds polylines/faces from the line graph, so storing
        a separate mutable polyline entity here would duplicate topology state and
        make holes/regions harder to compile.
        """

        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_polyline_last_id is None:
            self._state.pending_polyline_last_id = point.id
            # Just an anchor: no new edge yet, no topology change, no face
            # solver run needed. The first compile would otherwise re-resolve
            # every existing face in the sketch on top of placing a single
            # point.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Polyline started. Click the next point, or press Esc / double-click to finish.")
            return

        start_id = self._state.pending_polyline_last_id
        if start_id in self._state.sketch.points and point.id in self._state.sketch.points and start_id != point.id:
            line = self._state.sketch.add_line(start_id, point.id)
            line.metadata.update({"generated_by": "polyline"})
            self._state.pending_polyline_last_id = point.id
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            ctx.status.info("Polyline segment added. Continue clicking, or press Esc / double-click to finish.")
            return

        # Re-clicking the current endpoint does not mutate geometry.  Avoid a
        # full signature walk/compile request for this no-op gesture.
        ctx.status.info("Polyline point ignored: choose a distinct next point.")

    def _finish_polyline(self, ctx: Any | None, *, render: bool = True) -> bool:
        """End the current polyline chain without leaving Polyline mode."""

        if self._state.pending_polyline_last_id is None:
            return False
        self._state.pending_polyline_last_id = None
        if ctx is not None:
            try:
                self.services.snap._clear_pending_geometry_preview(ctx)
            except Exception:
                pass
            try:
                # Ending a chain only clears transient placement state.  The
                # final segment was already compiled when it was added.
                self.services.overlay._sync_reports(ctx)
                if render:
                    self.services.rendering._render(ctx, sync_overlays=True, render=True)
                ctx.status.info("Polyline finished. Polyline mode stays active for a new chain.")
            except Exception:
                pass
        return True

    def _handle_line_press(self, ctx: Any, world: tuple[float, float, float], *, base_snapshot: _PlanTrace2DSnapshot | None = None) -> None:
        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_line_start_id is None:
            self._state.pending_line_start_id = point.id
            # See ``_handle_rectangle_press``: a standalone anchor point does
            # not change topology, so skip the heavy face solver compile.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Line start placed. Click the end point.")
            return
        start_id = self._state.pending_line_start_id
        self._state.pending_line_start_id = None
        if start_id in self._state.sketch.points and point.id in self._state.sketch.points and start_id != point.id:
            line = self._state.sketch.add_line(start_id, point.id)
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            if base_snapshot is not None:
                start_xy = self._state.sketch.points.get(start_id).position if start_id in self._state.sketch.points else None
                end_xy = self._state.sketch.points.get(point.id).position if point.id in self._state.sketch.points else None
                if start_xy is not None and end_xy is not None:
                    self.services.metrics._begin_line_metric_edit(ctx, base_snapshot, start_xy, end_xy, entity_ids=(line.id, start_id, point.id))
                    ctx.status.info("Line placed. Adjust length/angle in the metric overlay, then validate.")
                    return
            ctx.status.info(f"Line added. Sketch now has {len(self._state.sketch.lines)} edge(s) and {len(self._state.sketch.polylines)} polyline(s).")
            return
        # Invalid/reused endpoint: no topology changed, so do not compile.
        ctx.status.info("Line ignored: choose a distinct end point.")

    def _handle_rectangle_press(self, ctx: Any, world: tuple[float, float, float], *, base_snapshot: _PlanTrace2DSnapshot | None = None) -> None:
        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_rectangle_corner_id is None:
            self._state.pending_rectangle_corner_id = point.id
            # A standalone point cannot change face topology; the heavy face
            # solver compile that runs on every rectangle/line/etc. click is
            # only worth it once edges actually exist. Use a lightweight
            # point-only refresh so the corner marker appears immediately.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Rectangle first corner placed. Click the opposite corner.")
            return
        first_id = self._state.pending_rectangle_corner_id
        self._state.pending_rectangle_corner_id = None
        if first_id in self._state.sketch.points and point.id in self._state.sketch.points and first_id != point.id:
            first = self._state.sketch.points[first_id].position
            opposite = point.position
            created_edges = self._add_axis_aligned_rectangle(first_id, point.id, first, opposite)
            if created_edges:
                self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
                if base_snapshot is not None:
                    self.services.metrics._begin_rectangle_metric_edit(ctx, base_snapshot, first, opposite, entity_ids=created_edges)
                    ctx.status.info("Rectangle placed. Adjust width/height in the metric overlay, then validate.")
                    return
                ctx.status.info(f"Rectangle added. Sketch now has {len(self._state.sketch.lines)} edge(s) and {len(self._state.sketch.faces)} face(s).")
            else:
                ctx.status.info("Rectangle ignored: corners are too close or degenerate.")
            return
        ctx.status.info("Rectangle ignored: choose a distinct opposite corner.")

    def _add_axis_aligned_rectangle(
        self,
        first_id: str,
        opposite_id: str,
        first: tuple[float, float],
        opposite: tuple[float, float],
    ) -> tuple[str, ...]:
        x1, y1 = float(first[0]), float(first[1])
        x2, y2 = float(opposite[0]), float(opposite[1])
        if abs(x2 - x1) <= 1.0e-8 or abs(y2 - y1) <= 1.0e-8:
            return ()
        corner_b = self.services.sketch_sync._add_or_reuse_sketch_point((x2, y1))
        corner_d = self.services.sketch_sync._add_or_reuse_sketch_point((x1, y2))
        order = (first_id, corner_b.id, opposite_id, corner_d.id)
        created: list[str] = []
        for start_id, end_id in zip(order, (*order[1:], order[0])):
            if start_id == end_id:
                continue
            line = self._state.sketch.add_line(start_id, end_id)
            line.metadata.update({"generated_by": "rectangle"})
            created.append(line.id)
        return tuple(created)

    def _handle_arc_press(self, ctx: Any, world: tuple[float, float, float], *, base_snapshot: _PlanTrace2DSnapshot | None = None) -> None:
        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_arc_start_id is None:
            self._state.pending_arc_start_id = point.id
            self._state.pending_arc_end_id = None
            # Anchor only: no topology change, skip the heavy face solver.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Arc start placed. Click the arc end point.")
            return
        if self._state.pending_arc_end_id is None:
            if point.id != self._state.pending_arc_start_id:
                self._state.pending_arc_end_id = point.id
            # Still just anchor points until the third click creates the arc.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Arc end placed. Click a point on the arc.")
            return
        start_id = self._state.pending_arc_start_id
        end_id = self._state.pending_arc_end_id
        self._state.pending_arc_start_id = None
        self._state.pending_arc_end_id = None
        if (
            start_id in self._state.sketch.points
            and end_id in self._state.sketch.points
            and point.id in self._state.sketch.points
            and len({start_id, end_id, point.id}) == 3
        ):
            arc_intent = ArcIntent.from_points(
                self._state.sketch.points[start_id].position,
                self._state.sketch.points[end_id].position,
                self._state.sketch.points[point.id].position,
            )
            arc = self._state.sketch.add_arc(start_id, end_id, point.id)
            arc.metadata.update(curve_intent_metadata(side=arc_intent.side, major=arc_intent.major, kind="arc"))
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            if base_snapshot is not None:
                start_xy = self._state.sketch.points.get(start_id).position if start_id in self._state.sketch.points else None
                end_xy = self._state.sketch.points.get(end_id).position if end_id in self._state.sketch.points else None
                control_xy = self._state.sketch.points.get(point.id).position if point.id in self._state.sketch.points else None
                if start_xy is not None and end_xy is not None and control_xy is not None:
                    self.services.metrics._begin_arc_metric_edit(ctx, base_snapshot, start_xy, end_xy, control_xy, entity_ids=(arc.id, start_id, end_id, point.id), arc_intent=arc_intent)
                    ctx.status.info("Arc placed. Adjust radius/angle in the metric overlay, then validate.")
                    return
            ctx.status.info(f"Arc added. Sketch now has {len(self._state.sketch.arcs)} arc(s) and {len(self._state.sketch.polylines)} polyline(s).")
            return
        ctx.status.info("Arc ignored: use three distinct, non-collinear points.")

    def _handle_bezier_press(
        self,
        ctx: Any,
        world: tuple[float, float, float],
        *,
        base_snapshot: _PlanTrace2DSnapshot | None = None,
    ) -> None:
        """Create one cubic Bézier curve from four staged points.

        The click order is start, end, start-handle and end-handle.  This keeps
        both endpoints available from the second click so the live preview can
        show the final chord while the two handles shape complex S-curves.
        """

        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_bezier_start_id is None:
            self._state.pending_bezier_start_id = point.id
            self._state.pending_bezier_end_id = None
            self._state.pending_bezier_control_1_id = None
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Bezier start placed. Click the end point.")
            return
        if self._state.pending_bezier_end_id is None:
            if point.id != self._state.pending_bezier_start_id:
                self._state.pending_bezier_end_id = point.id
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Bezier end placed. Click the first curvature handle.")
            return
        if self._state.pending_bezier_control_1_id is None:
            self._state.pending_bezier_control_1_id = point.id
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("First handle placed. Click the second curvature handle.")
            return

        start_id = self._state.pending_bezier_start_id
        end_id = self._state.pending_bezier_end_id
        control_1_id = self._state.pending_bezier_control_1_id
        control_2_id = point.id
        self._state.pending_bezier_start_id = None
        self._state.pending_bezier_end_id = None
        self._state.pending_bezier_control_1_id = None
        if (
            start_id in self._state.sketch.points
            and end_id in self._state.sketch.points
            and control_1_id in self._state.sketch.points
            and control_2_id in self._state.sketch.points
            and start_id != end_id
        ):
            curve = self._state.sketch.add_bezier(start_id, end_id, control_1_id, control_2_id)
            curve.metadata.update({"curve_type": "bezier", "generated_by": "bezier_tool"})
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            ctx.status.info(
                f"Bezier curve added. Sketch now has {len(self._state.sketch.beziers)} complex curve(s) "
                f"and {len(self._state.sketch.faces)} face(s)."
            )
            return
        ctx.status.info("Bezier ignored: choose two distinct endpoints.")

    def _handle_circle_press(self, ctx: Any, world: tuple[float, float, float], *, base_snapshot: _PlanTrace2DSnapshot | None = None) -> None:
        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_circle_center_id is None:
            self._state.pending_circle_center_id = point.id
            # Center anchor only: no topology change yet.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Circle center placed. Click a radius point.")
            return
        center_id = self._state.pending_circle_center_id
        self._state.pending_circle_center_id = None
        if center_id in self._state.sketch.points and point.id in self._state.sketch.points and center_id != point.id:
            circle = self._state.sketch.add_circle(center_id, point.id)
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            if base_snapshot is not None:
                center_xy = self._state.sketch.points.get(center_id).position if center_id in self._state.sketch.points else None
                radius_xy = self._state.sketch.points.get(point.id).position if point.id in self._state.sketch.points else None
                if center_xy is not None and radius_xy is not None:
                    self.services.metrics._begin_circle_metric_edit(ctx, base_snapshot, center_xy, radius_xy, entity_ids=(circle.id, center_id, point.id))
                    ctx.status.info("Circle placed. Adjust radius/diameter in the metric overlay, then validate.")
                    return
            ctx.status.info(f"Circle added. Sketch now has {len(self._state.sketch.circles)} circle(s) and {len(self._state.sketch.faces)} generated face(s).")
            return
        ctx.status.info("Circle ignored: choose a radius point away from the center.")

    def _handle_half_circle_press(self, ctx: Any, world: tuple[float, float, float], *, base_snapshot: _PlanTrace2DSnapshot | None = None) -> None:
        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        if self._state.pending_half_circle_start_id is None:
            self._state.pending_half_circle_start_id = point.id
            # Start anchor only: no topology change yet.
            self.services.sketch_sync._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
            ctx.status.info("Half-circle start placed. Click the diameter end point.")
            return
        start_id = self._state.pending_half_circle_start_id
        self._state.pending_half_circle_start_id = None
        if start_id in self._state.sketch.points and point.id in self._state.sketch.points and start_id != point.id:
            start = self._state.sketch.points[start_id].position
            end = point.position
            half_intent = HalfCircleIntent.from_points(start, end)
            control_xy = half_intent.control_xy()
            control = self.services.sketch_sync._add_or_reuse_sketch_point(control_xy)
            if control.id not in {start_id, point.id}:
                arc = self._state.sketch.add_arc(start_id, point.id, control.id)
                diameter = self._state.sketch.add_line(start_id, point.id)
                diameter.metadata.update({"generated_by": "half_circle_diameter", "half_circle_arc_id": arc.id})
                arc.metadata.update({"curve_type": "half_circle", "diameter_line_id": diameter.id, **curve_intent_metadata(side=half_intent.side, kind="half_circle")})
                self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
                if base_snapshot is not None:
                    self.services.metrics._begin_half_circle_metric_edit(ctx, base_snapshot, start, end, entity_ids=(arc.id, diameter.id, start_id, point.id, control.id), half_circle_intent=half_intent)
                    ctx.status.info("Half-circle placed. Adjust radius/diameter in the metric overlay, then validate.")
                    return
                ctx.status.info(f"Half-circle added. Sketch now has {len(self._state.sketch.arcs)} arc(s) and {len(self._state.sketch.faces)} generated face(s).")
                return
        ctx.status.info("Half-circle ignored: choose a valid diameter.")

    @staticmethod
    def _half_circle_control_point(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
        return half_circle_control_point(start, end)


__all__ = ["PlanTrace2DDrawingService"]
