# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from laserprog_studio.tool_api.sketch import SketchCompileOptions

from ..ids import TOOL_PLAN_TRACE
from .services import _PlanTrace2DService

class PlanTrace2DSketchSyncService(_PlanTrace2DService):
    def _compile_signature(self) -> tuple[Any, ...]:
        """Return a cheap semantic signature for the sketch topology.

        Dense motif sketches can make ``SketchDocument.compile`` take seconds.
        Several UI paths ask for ``can_apply`` or emit a mouse-release after a
        pure selection click without changing any geometry.  Recompiling in
        those cases is pure waste, so the live tool caches a geometry signature
        and skips the compiler when it is unchanged.
        """

        sketch = self._state.sketch

        def r2(value: Any) -> tuple[int, int]:
            try:
                return (round(float(value[0]) * 100000), round(float(value[1]) * 100000))
            except Exception:
                return (0, 0)

        points = tuple(sorted((str(pid), r2(point.position)) for pid, point in sketch.points.items()))
        lines = tuple(sorted((str(lid), str(line.start_point_id), str(line.end_point_id)) for lid, line in sketch.lines.items()))
        circles = tuple(sorted((str(cid), str(circle.center_point_id), str(circle.radius_point_id)) for cid, circle in sketch.circles.items()))
        arcs = tuple(sorted((str(aid), str(arc.start_point_id), str(arc.end_point_id), str(arc.control_point_id)) for aid, arc in sketch.arcs.items()))
        beziers = tuple(sorted((
            str(bid),
            str(bezier.start_point_id),
            str(bezier.end_point_id),
            str(bezier.control_1_point_id),
            str(bezier.control_2_point_id),
        ) for bid, bezier in getattr(sketch, "beziers", {}).items()))
        dimensions = tuple(sorted((str(did), repr(dimension)) for did, dimension in getattr(sketch, "dimensions", {}).items()))
        holes = tuple(sorted(
            (str(key), tuple(tuple(r2(point) for point in polygon) for polygon in value))
            for key, value in getattr(self._state, "motif_face_holes_by_outer_signature", {}).items()
        ))
        motif_assignments = tuple(sorted(
            (str(key), repr(sorted(dict(value).items())))
            for key, value in getattr(self._state, "motif_assignments_by_outer_signature", {}).items()
        ))
        # Deleting a generated face does not alter its boundary geometry; it only
        # adds the stable face signature to the suppression set.  Include that set
        # in the cache key or the compile fast path leaves the projected face and
        # its selection actor alive after Delete.
        suppressed_faces = tuple(sorted(str(value) for value in getattr(sketch, "suppressed_face_signatures", set()) or set()))
        return (points, lines, circles, arcs, beziers, dimensions, holes, motif_assignments, suppressed_faces)

    def _compile_and_sync_sketch(self, ctx: Any, *, render: bool, sync_apply_state: bool = True) -> None:
        """Compile and mirror one sketch revision with one projected sync."""

        with ctx.projected_drawing.for_tool(self.id).batch():
            self._compile_and_sync_sketch_batched(ctx, render=render, sync_apply_state=sync_apply_state)

    def _compile_and_sync_sketch_batched(self, ctx: Any, *, render: bool, sync_apply_state: bool = True) -> None:
        """Normalize topology and mirror the sketch document to selectable actors.

        This is the first Plan tracer pass where visible actors are generated from
        the sketch graph instead of being the source of truth.  It is what makes
        point-on-line split and future face/edge deletion deterministic.
        """

        from laserprog_studio.tool_api import plan2d

        current_signature = self._compile_signature()
        if current_signature == getattr(self._state, "plan_trace_last_compile_signature", None):
            _increment_perf(ctx, "plan_trace.sketch.compile_cache_hits")
            if sync_apply_state:
                self._sync_apply_button_state(ctx)
            return
        _increment_perf(ctx, "plan_trace.sketch.compile_cache_misses")

        # Faces are generated topology.  Their sketch ids are not stable across
        # compiles because the solver clears/recreates generated regions from the
        # current boundaries.  A normal click on a face therefore used to select
        # ``plan_trace:face:f8`` on mouse-press, then mouse-release compiled the
        # sketch into ``plan_trace:face:f10`` and stale-actor cleanup removed the
        # selection.  Persist face selection by the stable geometric signature
        # instead of the transient generated id.
        selected_face_signatures = self._selected_face_signatures(ctx)

        with _measure_perf(ctx, "plan_trace.sketch.compile_kernel"):
            self._state.sketch.compile(
                SketchCompileOptions(
                    merge_tolerance=1.0e-5,
                    split_tolerance=1.0e-5,
                    solve_faces=True,
                    # Keep user-authored circles/arcs/half-circles stable while the
                    # user edits the sketch.  The kernel can still split curves for
                    # offline topology tests, but live Plan Tracer must not turn a
                    # circle intersection drag into a destructive circle -> arc ->
                    # arc cascade.
                    split_curve_intersections=False,
                    split_curves_at_vertices=False,
                )
            )
            try:
                self.services.patterns.restore_persistent_face_holes_after_compile()
            except Exception:
                pass
        self._state.plan_trace_last_compile_signature = self._compile_signature()
        registry = ctx.projected_drawing.for_tool(self.id)
        desired_point_ids = set(self._state.sketch.points)
        desired_line_actor_ids = {self._line_actor_id(line_id) for line_id in self._state.sketch.lines}
        desired_face_actor_ids = {self._face_actor_id(face_id) for face_id in self._state.sketch.faces}
        desired_circle_actor_ids = {self._circle_actor_id(circle_id) for circle_id in self._state.sketch.circles}
        desired_arc_actor_ids = {self._arc_actor_id(arc_id) for arc_id in self._state.sketch.arcs}
        desired_bezier_actor_ids = {self._bezier_actor_id(bezier_id) for bezier_id in getattr(self._state.sketch, "beziers", {})}
        desired_dimension_actor_ids = {self._dimension_actor_id(dimension_id) for dimension_id in self._state.sketch.dimensions}
        visual_signatures = self._state.plan_trace_actor_visual_signatures
        for actor in tuple(ctx.selection.actors(owner_tool=self.id)):
            role = actor.metadata.get("plan_trace_role")
            stale = False
            if role == "point" and actor.id not in desired_point_ids:
                stale = True
            elif role == "edge" and actor.id not in desired_line_actor_ids:
                stale = True
            elif role == "face" and actor.id not in desired_face_actor_ids:
                stale = True
            elif role == "circle" and actor.id not in desired_circle_actor_ids:
                stale = True
            elif role == "arc" and actor.id not in desired_arc_actor_ids and actor.id not in desired_bezier_actor_ids:
                stale = True
            elif role == "dimension" and actor.id not in desired_dimension_actor_ids:
                stale = True
            if stale:
                registry.remove(actor.id, render=False)
                self._remove_stale_visual(ctx, str(actor.id))
                visual_signatures.pop(str(actor.id), None)
        desired_visual_actor_ids = {
            *(str(point_id) for point_id, point in self._state.sketch.points.items() if not bool(point.metadata.get("hidden_control"))),
            *desired_line_actor_ids,
            *desired_face_actor_ids,
            *desired_circle_actor_ids,
            *desired_arc_actor_ids,
            *desired_bezier_actor_ids,
            *desired_dimension_actor_ids,
        }
        for cached_actor_id in tuple(visual_signatures):
            if str(cached_actor_id) not in desired_visual_actor_ids:
                visual_signatures.pop(str(cached_actor_id), None)
        changed: list[str] = []
        for point_id, point in self._state.sketch.points.items():
            if bool(point.metadata.get("hidden_control")):
                continue
            semantic_world = self.services.coordinates.sketch_xy_to_semantic_world(point.position)
            display_world = self.services.coordinates.sketch_xy_to_display_world(point.position)
            signature = ("point", self._point_signature(display_world), self._point_signature(semantic_world))
            if self._actor_visual_is_current(ctx, registry, point_id, signature):
                continue
            plan2d.register_plan_point(ctx, owner_tool=self.id, point_id=point_id, world_pos=display_world, grabbable=True, semantic_world_pos=semantic_world)
            visual_signatures[str(point_id)] = signature
            changed.append(point_id)
        for face_id, face in self._state.sketch.faces.items():
            polygon = tuple(self.services.coordinates.sketch_xy_to_display_world(point) for point in face.polygon_points)
            if len(polygon) < 3:
                continue
            hole_polygons = tuple(
                tuple(self.services.coordinates.sketch_xy_to_display_world(point) for point in hole)
                for hole in getattr(face, "hole_polygons", ())
                if len(hole) >= 3
            )
            actor_id = self._face_actor_id(face_id)
            signature = (
                "face",
                tuple(self._point_signature(value) for value in polygon),
                tuple(tuple(self._point_signature(value) for value in hole) for hole in hole_polygons),
            )
            if not self._actor_visual_is_current(ctx, registry, actor_id, signature):
                plan2d.register_plan_face(
                    ctx,
                    owner_tool=self.id,
                    face_id=actor_id,
                    polygon_world_points=polygon,
                    hole_world_polygons=hole_polygons,
                    selectable=True,
                    sketch_face_id=face_id,
                )
                visual_signatures[str(actor_id)] = signature
                changed.append(actor_id)
            if self._face_signature(face) in selected_face_signatures:
                try:
                    ctx.selection.select(actor_id, replace=False)
                except Exception:
                    pass
        for circle_id, circle in self._state.sketch.circles.items():
            center = self._state.sketch.points.get(circle.center_point_id)
            radius_point = self._state.sketch.points.get(circle.radius_point_id)
            if center is None or radius_point is None:
                continue
            actor_id = self._circle_actor_id(circle_id)
            display_plane_for_circle = self._state.display_plane or self._state.plane
            center_world = self.services.coordinates.sketch_xy_to_display_world(center.position)
            radius_world = self.services.coordinates.sketch_xy_to_display_world(radius_point.position)
            signature = (
                "circle",
                self._point_signature(center_world),
                self._point_signature(radius_world),
                self._point_signature(display_plane_for_circle.u_axis) if display_plane_for_circle is not None else None,
                self._point_signature(display_plane_for_circle.v_axis) if display_plane_for_circle is not None else None,
            )
            if self._actor_visual_is_current(ctx, registry, actor_id, signature):
                continue
            plan2d.register_plan_circle(
                ctx,
                owner_tool=self.id,
                circle_id=actor_id,
                center_world_pos=center_world,
                radius_world_pos=radius_world,
                selectable=True,
                sketch_circle_id=circle_id,
                basis_u=display_plane_for_circle.u_axis if display_plane_for_circle is not None else None,
                basis_v=display_plane_for_circle.v_axis if display_plane_for_circle is not None else None,
            )
            visual_signatures[str(actor_id)] = signature
            changed.append(actor_id)
        for arc_id, arc in self._state.sketch.arcs.items():
            start = self._state.sketch.points.get(arc.start_point_id)
            end = self._state.sketch.points.get(arc.end_point_id)
            control = self._state.sketch.points.get(arc.control_point_id)
            if start is None or end is None or control is None:
                continue
            actor_id = self._arc_actor_id(arc_id)
            start_world = self.services.coordinates.sketch_xy_to_display_world(start.position)
            end_world = self.services.coordinates.sketch_xy_to_display_world(end.position)
            control_world = self.services.coordinates.sketch_xy_to_display_world(control.position)
            signature = (
                "arc",
                self._point_signature(start_world),
                self._point_signature(end_world),
                self._point_signature(control_world),
            )
            if self._actor_visual_is_current(ctx, registry, actor_id, signature):
                continue
            plan2d.register_plan_arc(
                ctx,
                owner_tool=self.id,
                arc_id=actor_id,
                start_world_pos=start_world,
                end_world_pos=end_world,
                control_world_pos=control_world,
                selectable=True,
                sketch_arc_id=arc_id,
            )
            visual_signatures[str(actor_id)] = signature
            changed.append(actor_id)
        for bezier_id, bezier in getattr(self._state.sketch, "beziers", {}).items():
            start = self._state.sketch.points.get(bezier.start_point_id)
            end = self._state.sketch.points.get(bezier.end_point_id)
            control_1 = self._state.sketch.points.get(bezier.control_1_point_id)
            control_2 = self._state.sketch.points.get(bezier.control_2_point_id)
            if start is None or end is None or control_1 is None or control_2 is None:
                continue
            actor_id = self._bezier_actor_id(bezier_id)
            start_world = self.services.coordinates.sketch_xy_to_display_world(start.position)
            end_world = self.services.coordinates.sketch_xy_to_display_world(end.position)
            control_1_world = self.services.coordinates.sketch_xy_to_display_world(control_1.position)
            control_2_world = self.services.coordinates.sketch_xy_to_display_world(control_2.position)
            signature = (
                "bezier",
                self._point_signature(start_world),
                self._point_signature(end_world),
                self._point_signature(control_1_world),
                self._point_signature(control_2_world),
            )
            if self._actor_visual_is_current(ctx, registry, actor_id, signature):
                continue
            plan2d.register_plan_bezier(
                ctx,
                owner_tool=self.id,
                bezier_id=actor_id,
                start_world_pos=start_world,
                end_world_pos=end_world,
                control_1_world_pos=control_1_world,
                control_2_world_pos=control_2_world,
                selectable=True,
                sketch_bezier_id=bezier_id,
            )
            visual_signatures[str(actor_id)] = signature
            changed.append(actor_id)
        for line_id, line in self._state.sketch.lines.items():
            start = self._state.sketch.points.get(line.start_point_id)
            end = self._state.sketch.points.get(line.end_point_id)
            if start is None or end is None:
                continue
            actor_id = self._line_actor_id(line_id)
            start_world = self.services.coordinates.sketch_xy_to_display_world(start.position)
            end_world = self.services.coordinates.sketch_xy_to_display_world(end.position)
            signature = ("line", self._point_signature(start_world), self._point_signature(end_world))
            if self._actor_visual_is_current(ctx, registry, actor_id, signature):
                continue
            plan2d.register_plan_line(
                ctx,
                owner_tool=self.id,
                line_id=actor_id,
                start_world_pos=start_world,
                end_world_pos=end_world,
                selectable=True,
                sketch_line_id=line_id,
            )
            visual_signatures[str(actor_id)] = signature
            changed.append(actor_id)
        try:
            from laserprog_studio.tool_api.plan2d import dimensions as dimension_api

            for dimension_id, dimension in self._state.sketch.dimensions.items():
                layout = dimension_api.layout_dimension(self._state.sketch, dimension)
                if not layout.valid:
                    continue
                actor_id = self._dimension_actor_id(dimension_id)
                dimension_world_line = (
                    self.services.coordinates.sketch_xy_to_display_world(layout.dimension_line[0]),
                    self.services.coordinates.sketch_xy_to_display_world(layout.dimension_line[1]),
                )
                witness_world_lines = tuple(
                    (self.services.coordinates.sketch_xy_to_display_world(a), self.services.coordinates.sketch_xy_to_display_world(b))
                    for a, b in layout.witness_lines
                )
                label_world_pos = self.services.coordinates.sketch_xy_to_display_world(layout.label_position)
                signature = (
                    "dimension",
                    tuple(self._point_signature(value) for value in dimension_world_line),
                    tuple(tuple(self._point_signature(value) for value in line) for line in witness_world_lines),
                    self._point_signature(label_world_pos),
                    str(layout.label),
                )
                required_ids = tuple(
                    [f"{actor_id}:witness:{index}" for index in range(len(witness_world_lines))]
                    + [f"{actor_id}:label"]
                )
                if self._actor_visual_is_current(ctx, registry, actor_id, signature, required_primitive_ids=required_ids):
                    continue
                plan2d.register_plan_dimension(
                    ctx,
                    owner_tool=self.id,
                    dimension_id=actor_id,
                    dimension_world_line=dimension_world_line,
                    witness_world_lines=witness_world_lines,
                    label_world_pos=label_world_pos,
                    label=layout.label,
                    selectable=True,
                    sketch_dimension_id=dimension_id,
                )
                visual_signatures[str(actor_id)] = signature
                changed.append(actor_id)
        except Exception:
            pass
        self._state.points = [(point_id, self.services.coordinates.sketch_xy_to_semantic_world(point.position)) for point_id, point in self._state.sketch.points.items() if not bool(point.metadata.get("hidden_control"))]
        self._state.lines = [(self._line_actor_id(line_id), line_id) for line_id in self._state.sketch.lines]
        # Geometry/topology has just been normalized. Invalidate both the full
        # snap target tuple and its screen-space neighbourhood index so exact
        # vertex/edge snaps cannot lag behind the visible sketch.
        try:
            self.services.snap_targets.invalidate_geometry_cache()
        except Exception:
            pass
        _increment_perf(ctx, "plan_trace.sketch.changed_actors", len(changed))
        with _measure_perf(ctx, "plan_trace.sketch.actor_visual_sync"):
            plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=tuple(changed), position_only=False, render=render)
        self.services.overlay._sync_reports(ctx)
        if sync_apply_state:
            self._sync_apply_button_state(ctx)


    def _sync_points_only(
        self,
        ctx: Any,
        *,
        render: bool = False,
        changed_point_ids: tuple[str, ...] | None = None,
    ) -> None:
        with ctx.projected_drawing.for_tool(self.id).batch():
            self._sync_points_only_batched(ctx, render=render, changed_point_ids=changed_point_ids)

    def _sync_points_only_batched(
        self,
        ctx: Any,
        *,
        render: bool = False,
        changed_point_ids: tuple[str, ...] | None = None,
    ) -> None:
        """Register sketch points without running the topology compiler.

        Used when a draw mode places a transient anchor that cannot change
        faces or edge topology — e.g. the first corner of a rectangle, the
        center of a circle, or the start of a line. The face solver is the
        most expensive part of ``_compile_and_sync_sketch`` (it scales with
        the number of existing closed regions); skipping it for these
        no-topology-change anchors makes drawing the second/third/Nth shape
        in a dense sketch significantly more responsive.
        """

        from laserprog_studio.tool_api import plan2d

        requested = {str(value) for value in changed_point_ids or ()}
        point_items = (
            ((point_id, self._state.sketch.points[point_id]) for point_id in requested if point_id in self._state.sketch.points)
            if requested
            else self._state.sketch.points.items()
        )
        changed: list[str] = []
        registry = ctx.projected_drawing.for_tool(self.id)
        visual_signatures = self._state.plan_trace_actor_visual_signatures
        for point_id, point in point_items:
            if bool(point.metadata.get("hidden_control")):
                continue
            semantic_world = self.services.coordinates.sketch_xy_to_semantic_world(point.position)
            display_world = self.services.coordinates.sketch_xy_to_display_world(point.position)
            signature = ("point", self._point_signature(display_world), self._point_signature(semantic_world))
            if self._actor_visual_is_current(ctx, registry, point_id, signature):
                continue
            plan2d.register_plan_point(ctx, owner_tool=self.id, point_id=point_id, world_pos=display_world, grabbable=True, semantic_world_pos=semantic_world)
            visual_signatures[str(point_id)] = signature
            changed.append(point_id)
        self._state.points = [
            (point_id, self.services.coordinates.sketch_xy_to_semantic_world(point.position))
            for point_id, point in self._state.sketch.points.items()
            if not bool(point.metadata.get("hidden_control"))
        ]
        try:
            self.services.snap_targets.invalidate_geometry_cache()
        except Exception:
            pass
        if changed:
            plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=tuple(changed), position_only=False, render=render)
        self.services.overlay._sync_reports(ctx)

    def _sync_drag_moved_points(self, ctx: Any, moved_point_ids: tuple[str, ...], *, render: bool = False) -> None:
        with ctx.projected_drawing.for_tool(self.id).batch():
            self._sync_drag_moved_points_batched(ctx, moved_point_ids, render=render)

    def _sync_drag_moved_points_batched(self, ctx: Any, moved_point_ids: tuple[str, ...], *, render: bool = False) -> None:
        """Lightweight visual sync used during point drags.

        The full sketch compiler/face solver is intentionally release-time work.
        During mouse moves we only refresh moved point handles and directly
        connected edge/curve actors so the drag remains fluid in dense sketches.
        """

        from laserprog_studio.tool_api import plan2d

        moved = {str(value) for value in moved_point_ids}
        if not moved:
            return
        changed: list[str] = []
        visual_signatures = self._state.plan_trace_actor_visual_signatures

        # Do not move the selected point handles here. The native Creator API
        # drag path receives the resolved actor positions and moves selected
        # handles itself; pre-moving them in the resolver makes the API think
        # nothing changed.  This lightweight sync only refreshes dependent
        # geometry while the point actors are left to ``move_actors_to``.

        for line_id, line in self._state.sketch.lines.items():
            if line.start_point_id not in moved and line.end_point_id not in moved:
                continue
            start = self._state.sketch.points.get(line.start_point_id)
            end = self._state.sketch.points.get(line.end_point_id)
            if start is None or end is None:
                continue
            actor_id = self._line_actor_id(line_id)
            start_world = self.services.coordinates.sketch_xy_to_display_world(start.position)
            end_world = self.services.coordinates.sketch_xy_to_display_world(end.position)
            plan2d.register_plan_line(
                ctx,
                owner_tool=self.id,
                line_id=actor_id,
                start_world_pos=start_world,
                end_world_pos=end_world,
                selectable=True,
                sketch_line_id=line_id,
            )
            visual_signatures[str(actor_id)] = ("line", self._point_signature(start_world), self._point_signature(end_world))
            changed.append(actor_id)

        display_plane_for_curve = self._state.display_plane or self._state.plane
        for circle_id, circle in self._state.sketch.circles.items():
            if circle.center_point_id not in moved and circle.radius_point_id not in moved:
                continue
            center = self._state.sketch.points.get(circle.center_point_id)
            radius_point = self._state.sketch.points.get(circle.radius_point_id)
            if center is None or radius_point is None:
                continue
            actor_id = self._circle_actor_id(circle_id)
            center_world = self.services.coordinates.sketch_xy_to_display_world(center.position)
            radius_world = self.services.coordinates.sketch_xy_to_display_world(radius_point.position)
            plan2d.register_plan_circle(
                ctx,
                owner_tool=self.id,
                circle_id=actor_id,
                center_world_pos=center_world,
                radius_world_pos=radius_world,
                selectable=True,
                sketch_circle_id=circle_id,
                basis_u=display_plane_for_curve.u_axis if display_plane_for_curve is not None else None,
                basis_v=display_plane_for_curve.v_axis if display_plane_for_curve is not None else None,
            )
            visual_signatures[str(actor_id)] = (
                "circle",
                self._point_signature(center_world),
                self._point_signature(radius_world),
                self._point_signature(display_plane_for_curve.u_axis) if display_plane_for_curve is not None else None,
                self._point_signature(display_plane_for_curve.v_axis) if display_plane_for_curve is not None else None,
            )
            changed.append(actor_id)

        for arc_id, arc in self._state.sketch.arcs.items():
            if arc.start_point_id not in moved and arc.end_point_id not in moved and arc.control_point_id not in moved:
                continue
            start = self._state.sketch.points.get(arc.start_point_id)
            end = self._state.sketch.points.get(arc.end_point_id)
            control = self._state.sketch.points.get(arc.control_point_id)
            if start is None or end is None or control is None:
                continue
            actor_id = self._arc_actor_id(arc_id)
            start_world = self.services.coordinates.sketch_xy_to_display_world(start.position)
            end_world = self.services.coordinates.sketch_xy_to_display_world(end.position)
            control_world = self.services.coordinates.sketch_xy_to_display_world(control.position)
            plan2d.register_plan_arc(
                ctx,
                owner_tool=self.id,
                arc_id=actor_id,
                start_world_pos=start_world,
                end_world_pos=end_world,
                control_world_pos=control_world,
                selectable=True,
                sketch_arc_id=arc_id,
            )
            visual_signatures[str(actor_id)] = (
                "arc",
                self._point_signature(start_world),
                self._point_signature(end_world),
                self._point_signature(control_world),
            )
            changed.append(actor_id)

        for bezier_id, bezier in getattr(self._state.sketch, "beziers", {}).items():
            referenced = {
                bezier.start_point_id,
                bezier.end_point_id,
                bezier.control_1_point_id,
                bezier.control_2_point_id,
            }
            if referenced.isdisjoint(moved):
                continue
            start = self._state.sketch.points.get(bezier.start_point_id)
            end = self._state.sketch.points.get(bezier.end_point_id)
            control_1 = self._state.sketch.points.get(bezier.control_1_point_id)
            control_2 = self._state.sketch.points.get(bezier.control_2_point_id)
            if start is None or end is None or control_1 is None or control_2 is None:
                continue
            actor_id = self._bezier_actor_id(bezier_id)
            start_world = self.services.coordinates.sketch_xy_to_display_world(start.position)
            end_world = self.services.coordinates.sketch_xy_to_display_world(end.position)
            control_1_world = self.services.coordinates.sketch_xy_to_display_world(control_1.position)
            control_2_world = self.services.coordinates.sketch_xy_to_display_world(control_2.position)
            plan2d.register_plan_bezier(
                ctx,
                owner_tool=self.id,
                bezier_id=actor_id,
                start_world_pos=start_world,
                end_world_pos=end_world,
                control_1_world_pos=control_1_world,
                control_2_world_pos=control_2_world,
                selectable=True,
                sketch_bezier_id=bezier_id,
            )
            visual_signatures[str(actor_id)] = (
                "bezier",
                self._point_signature(start_world),
                self._point_signature(end_world),
                self._point_signature(control_1_world),
                self._point_signature(control_2_world),
            )
            changed.append(actor_id)

        self._state.points = [
            (point_id, self.services.coordinates.sketch_xy_to_semantic_world(point.position))
            for point_id, point in self._state.sketch.points.items()
            if not bool(point.metadata.get("hidden_control"))
        ]
        try:
            self.services.snap_targets.invalidate_geometry_cache()
        except Exception:
            pass
        if changed:
            plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=tuple(dict.fromkeys(changed)), position_only=True, render=render)

    def _actor_visual_is_current(
        self,
        ctx: Any,
        registry: Any,
        actor_id: str,
        signature: tuple[Any, ...],
        *,
        required_primitive_ids: tuple[str, ...] = (),
    ) -> bool:
        """Return True when an unchanged actor is still fully registered.

        Topology compilation may legitimately run after every completed edge,
        because the new edge can split an existing region.  Re-registering all
        unchanged actors after that compile is unnecessary and was the main
        source of projected-overlay churn.  The cache is only trusted when both
        the selection actor and every required projected primitive still exist.
        """

        actor_key = str(actor_id)
        cached = self._state.plan_trace_actor_visual_signatures.get(actor_key)
        if cached != signature:
            return False
        try:
            if ctx.selection.actor(actor_key) is None or registry.get(actor_key) is None:
                return False
            if any(registry.get(str(primitive_id)) is None for primitive_id in required_primitive_ids):
                return False
        except Exception:
            return False
        return True

    @staticmethod
    def _point_signature(value: Any) -> tuple[int, int, int]:
        """Return a stable sub-micron signature for one display/semantic point."""

        try:
            values = tuple(float(component) for component in value)
        except Exception:
            values = ()
        padded = (*values[:3], 0.0, 0.0, 0.0)
        return tuple(round(float(component) * 1_000_000.0) for component in padded[:3])

    def _remove_stale_visual(self, ctx: Any, actor_id: str) -> None:
        """Remove viewport leftovers for topology actors that disappeared.

        Points are handle-backed rather than preview-backed, so unregistering the
        ToolActor alone can leave a dead selected-looking dot in the viewport
        until the whole tool is rebuilt.  Deleting through this local visual
        cleanup keeps point deletion deterministic without broadening the public
        ActorRegistry contract.
        """

        registry = ctx.projected_drawing.for_tool(self.id)
        targets = tuple(
            primitive.id
            for primitive in registry.items()
            if str(primitive.id) == str(actor_id)
            or str(primitive.id).startswith(f"{actor_id}:witness:")
            or str(primitive.id) == f"{actor_id}:label"
        )
        if targets:
            registry.remove_many(targets, render=False)

    def _sync_apply_button_state(self, ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        if bool(getattr(owner, "_plan_trace_2d_apply_state_syncing", False)):
            return
        update_preview_state = getattr(owner, "update_preview_state", None)
        if not callable(update_preview_state):
            return
        try:
            setattr(owner, "_plan_trace_2d_apply_state_syncing", True)
            update_preview_state()
        except Exception:
            pass
        finally:
            try:
                setattr(owner, "_plan_trace_2d_apply_state_syncing", False)
            except Exception:
                pass

    def _selected_face_signatures(self, ctx: Any) -> set[str]:
        """Return stable signatures for currently-selected generated faces."""

        signatures: set[str] = set()
        try:
            selected_ids = tuple(str(value) for value in ctx.selection.ids())
        except Exception:
            selected_ids = ()
        for actor_id in selected_ids:
            try:
                actor = ctx.selection.actor(actor_id)
            except Exception:
                actor = None
            if actor is None or actor.owner_tool != self.id:
                continue
            if actor.metadata.get("plan_trace_role") != "face":
                continue
            face_id = actor.metadata.get("plan_trace_sketch_face_id")
            face = self._state.sketch.faces.get(str(face_id)) if face_id is not None else None
            signature = self._face_signature(face)
            if signature:
                signatures.add(signature)
        return signatures

    @staticmethod
    def _face_signature(face: Any) -> str:
        if face is None:
            return ""
        try:
            return str(face.metadata.get("signature") or "")
        except Exception:
            return ""

    @staticmethod
    def _line_actor_id(line_id: str) -> str:
        return f"{TOOL_PLAN_TRACE}:line:{line_id}"

    @staticmethod
    def _face_actor_id(face_id: str) -> str:
        return f"{TOOL_PLAN_TRACE}:face:{face_id}"

    @staticmethod
    def _circle_actor_id(circle_id: str) -> str:
        return f"{TOOL_PLAN_TRACE}:circle:{circle_id}"

    @staticmethod
    def _arc_actor_id(arc_id: str) -> str:
        return f"{TOOL_PLAN_TRACE}:arc:{arc_id}"

    @staticmethod
    def _bezier_actor_id(bezier_id: str) -> str:
        return f"{TOOL_PLAN_TRACE}:bezier:{bezier_id}"

    @staticmethod
    def _dimension_actor_id(dimension_id: str) -> str:
        return f"{TOOL_PLAN_TRACE}:dimension:{dimension_id}"

    def _add_or_reuse_sketch_point(self, xy: tuple[float, float]):
        """Return an existing sketch vertex at xy or create a new one.

        The compiler still performs global duplicate merging, but interactive
        tools need this immediate canonicalization so a snapped line endpoint can
        continue from the existing vertex instead of keeping a pending id that a
        later compile removes.
        """

        for point in self._state.sketch.points.values():
            if abs(float(point.position[0]) - float(xy[0])) <= 1.0e-5 and abs(float(point.position[1]) - float(xy[1])) <= 1.0e-5:
                return point
        point_id = f"{self.id}:point:{self._state.next_point_index:04d}"
        self._state.next_point_index += 1
        return self._state.sketch.add_point(xy, point_id=point_id)

    def _place_point(self, ctx: Any, world: tuple[float, float, float]):
        from laserprog_studio.tool_api import plan2d

        plane = self._state.plane
        display_plane = self._state.display_plane or plane
        semantic_world = world
        if plane is not None and display_plane is not None:
            semantic_world = plan2d.semantic_point_for_display_world(plane, display_plane, world)
        point = self._add_or_reuse_sketch_point(self.services.coordinates.semantic_world_to_sketch_xy(semantic_world))
        # Most standalone points cannot change topology, so avoid invoking the
        # complete face solver.  A point placed on the interior of an existing
        # line is the important exception: SketchCompiler must split that line
        # immediately so the new vertex becomes a real selectable endpoint.
        if self._point_splits_existing_line(point.id):
            self._compile_and_sync_sketch(ctx, render=True)
        else:
            self._sync_points_only(ctx, render=True, changed_point_ids=(point.id,))
        actor = ctx.selection.actor(point.id)
        ctx.status.info(f"Point {len(self._state.points)} placed.")
        return actor

    def _point_splits_existing_line(self, point_id: str, *, tolerance: float = 1.0e-5) -> bool:
        """Return True when a point lies on a line interior and must node it."""

        point = self._state.sketch.points.get(str(point_id))
        if point is None:
            return False
        px, py = float(point.position[0]), float(point.position[1])
        tol2 = max(float(tolerance), 0.0) ** 2
        for line in self._state.sketch.lines.values():
            if str(point_id) in {str(line.start_point_id), str(line.end_point_id)}:
                continue
            start = self._state.sketch.points.get(line.start_point_id)
            end = self._state.sketch.points.get(line.end_point_id)
            if start is None or end is None:
                continue
            ax, ay = float(start.position[0]), float(start.position[1])
            bx, by = float(end.position[0]), float(end.position[1])
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            if length2 <= 1.0e-20:
                continue
            t = ((px - ax) * dx + (py - ay) * dy) / length2
            if t <= 1.0e-8 or t >= 1.0 - 1.0e-8:
                continue
            qx, qy = ax + t * dx, ay + t * dy
            if (px - qx) ** 2 + (py - qy) ** 2 <= tol2:
                return True
        return False



def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if not callable(increment):
        return
    try:
        increment(str(name), int(value))
    except Exception:
        pass


def _measure_perf(ctx: Any, name: str) -> Any:
    profiler = getattr(ctx, "profiler", None)
    measure = getattr(profiler, "measure", None)
    if callable(measure):
        try:
            return measure(str(name))
        except Exception:
            pass
    return nullcontext()


__all__ = ["PlanTrace2DSketchSyncService"]
