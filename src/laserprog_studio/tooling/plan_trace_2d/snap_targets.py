# -*- coding: utf-8 -*-
from __future__ import annotations

from math import cos, floor, isfinite, pi, sin, sqrt
from typing import Any

from laserprog_studio.tool_api.plan2d.plane import sample_plan_arc_xy
from laserprog_studio.tool_api.plan2d.curves import sample_cubic_bezier
from laserprog_studio.tool_api.scene import projection_cache_signature

from .constants import _ANCHOR_ID
from .services import _PlanTrace2DService

_PLAN_TRACE_SNAP_CELL_SIZE_PX = 72.0
_PLAN_TRACE_SNAP_QUERY_MARGIN_PX = 12.0
_PLAN_TRACE_SNAP_MAX_CELLS_PER_TARGET = 768
_PLAN_TRACE_CURVE_BBOX_SAMPLE_COUNT = 24


class PlanTrace2DSnapTargetsService(_PlanTrace2DService):
    """Compiled Plan Tracer snap target exporter.

    Cursor moves are extremely high-frequency.  Building every point/edge/circle
    SnapTarget and resampling arcs on each event made dense sketches feel like the
    snap loop was frozen.  This service now compiles the full target set once per
    sketch/plane signature, then serves two cheap query views:

    * a local exact-snap set from a screen-space index;
    * the full target tuple for distant U/V alignment guides.

    The exact set is local by design; the full tuple is still handed to the Plan2D
    alignment guide cache so a far vertex can continue to align the cursor.
    """

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self._targets_signature: tuple[Any, ...] | None = None
        self._targets_cache: tuple[Any, ...] = ()
        self._screen_index_key: tuple[Any, ...] | None = None
        self._screen_index_targets: tuple[Any, ...] = ()
        self._screen_index_cells: dict[tuple[int, int], tuple[int, ...]] = {}
        self._screen_index_fallback: tuple[int, ...] = ()
        self._drag_targets_cache: tuple[Any, ...] | None = None
        self._drag_screen_index_key: tuple[Any, ...] | None = None
        self._drag_screen_index_targets: tuple[Any, ...] = ()
        self._drag_screen_index_cells: dict[tuple[int, int], tuple[int, ...]] = {}
        self._drag_screen_index_fallback: tuple[int, ...] = ()
        # Frozen drag targets have their own generation. Live sketch updates
        # invalidate the post-release target pool on every drag frame, but must
        # not rebuild the unchanged frozen drag screen index.
        self._drag_targets_revision: int = 0
        # Cache of filtered target tuples, keyed by (pool_identity, exclude_ids).
        # ``smart_snap_on_plan`` uses ``id(extra_alignment_targets)`` to memoise
        # the compiled plan2d guide cache. Without this cache the filtered tuple
        # gets a fresh id on every mouse move, so the heavy
        # ``_Plan2DGuideCache.build`` (per-target ``world_to_plane`` projection)
        # was rebuilt on every hover. Returning the same filtered tuple keeps
        # the upstream alignment-guide cache hot for the lifetime of the sketch.
        self._filtered_cache: dict[tuple[int, tuple[str, ...]], tuple[Any, ...]] = {}
        self._targets_fast_signature: tuple[Any, ...] | None = None
        self._move_revision: int = 0
        # Monotonic geometry generation used by the screen-space index.  Tuple
        # object ids can be reused by Python after a rebuild; a generation stamp
        # prevents an old local index from being accepted for new snap geometry.
        self._targets_revision: int = 0

    def _live_snap_targets(self, ctx: Any, *, exclude_ids: tuple[str, ...] = ()) -> tuple[Any, ...]:
        targets = self._active_full_targets(ctx)
        if exclude_ids:
            return self._stable_filtered(targets, exclude_ids)
        return targets

    def _live_snap_targets_near(self, ctx: Any, screen_pos: tuple[float, float], *, exclude_ids: tuple[str, ...] = ()) -> tuple[Any, ...]:
        """Return only exact-snap targets close enough to affect this cursor move.

        Distant alignments do not use this filtered set.  They use
        ``_live_snap_targets`` through Plan2D's compiled guide cache, so quality is
        preserved while the expensive exact snap/intersection pass stays local.
        """

        targets = self._active_full_targets(ctx)
        if not targets:
            return ()
        near = self._near_targets_from_pool(ctx, targets, screen_pos)
        if exclude_ids:
            return self._stable_filtered(near, exclude_ids)
        return near

    def _live_snap_targets_and_near(
        self,
        ctx: Any,
        screen_pos: tuple[float, float],
        *,
        exclude_ids: tuple[str, ...] = (),
    ) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        """Return ``(alignment_targets, near_targets)`` from a single signature pass.

        The cursor update needs both views per mouse move; running the two
        public helpers back-to-back duplicates the snap-target signature walk and
        the optional ``_filter_targets`` pass.  Computing them together keeps
        the snap loop cheap on hover in dense sketches.

        The alignment tuple is intentionally cached by identity: the upstream
        plan2d guide cache memoises a heavy ``world_to_plane`` projection table
        by ``id(extra_alignment_targets)``; rebuilding it on every mouse move
        was the single largest contributor to snap latency in dense sketches.
        """

        targets = self._active_full_targets(ctx)
        if not targets:
            return (), ()
        near = self._near_targets_from_pool(ctx, targets, screen_pos)
        if exclude_ids:
            align_filtered = self._stable_filtered(targets, exclude_ids)
            # When the filter against the full pool removed nothing, the same
            # exclude set cannot remove anything from any subset either - so
            # the per-move near filter (the hottest call) can be skipped.
            # This is the common case for cursor hover: the only excluded id
            # is ``_CURSOR_ID``, which never appears in the snap target pool.
            if len(align_filtered) == len(targets):
                return align_filtered, near
            near_filtered = self._filter_targets(near, exclude_ids)
            return align_filtered, near_filtered
        return targets, near

    def _stable_filtered(self, pool: tuple[Any, ...], exclude_ids: tuple[str, ...]) -> tuple[Any, ...]:
        """Return a filtered tuple whose identity is stable across calls.

        The plan2d guide cache memoises its compiled projection table by
        ``id(extra_alignment_targets)``. Returning the same tuple object when
        the underlying pool and exclude set are unchanged is what lets that
        cache stay hot during a mouse-move loop.
        """

        if not exclude_ids:
            return pool
        cache_key = (id(pool), tuple(sorted(str(value) for value in exclude_ids)))
        cached = self._filtered_cache.get(cache_key)
        if cached is not None:
            return cached
        # Drop stale entries when the underlying pool changes: anything not
        # keyed by the current pool identity has been invalidated by topology.
        if len(self._filtered_cache) > 8:
            current_pool_id = id(pool)
            for stored_key in tuple(self._filtered_cache):
                if stored_key[0] != current_pool_id:
                    self._filtered_cache.pop(stored_key, None)
        filtered = self._filter_targets(pool, exclude_ids)
        self._filtered_cache[cache_key] = filtered
        return filtered

    def _near_targets_from_pool(
        self,
        ctx: Any,
        targets: tuple[Any, ...],
        screen_pos: tuple[float, float],
    ) -> tuple[Any, ...]:
        with self._measure_perf(ctx, "plan_trace.snap.near_query.total"):
            target_pool, cells, fallback = self._ensure_screen_index(ctx, targets)
            sx, sy = self._point2(screen_pos)
            cell = float(_PLAN_TRACE_SNAP_CELL_SIZE_PX)
            margin = float(_PLAN_TRACE_SNAP_QUERY_MARGIN_PX)
            min_cx = floor((sx - margin) / cell)
            max_cx = floor((sx + margin) / cell)
            min_cy = floor((sy - margin) / cell)
            max_cy = floor((sy + margin) / cell)
            indices: set[int] = set(int(index) for index in fallback)
            with self._measure_perf(ctx, "plan_trace.snap.near_query.cells"):
                for cx in range(int(min_cx), int(max_cx) + 1):
                    for cy in range(int(min_cy), int(max_cy) + 1):
                        indices.update(int(index) for index in cells.get((cx, cy), ()))
            with self._measure_perf(ctx, "plan_trace.snap.near_query.materialize"):
                result = tuple(target_pool[index] for index in sorted(indices) if 0 <= index < len(target_pool))
            self._increment_perf(ctx, "plan_trace.snap.near_queries")
            self._increment_perf(ctx, "plan_trace.snap.near_index_candidates", len(indices))
            self._increment_perf(ctx, "plan_trace.snap.near_targets", len(result))
            self._increment_perf(ctx, "plan_trace.snap.near_fallback_targets", len(fallback))
            self._set_perf_value(ctx, "plan_trace.snap.last_near_targets", len(result))
            self._set_perf_value(ctx, "plan_trace.snap.last_near_index_candidates", len(indices))
            return result

    def _begin_drag_snap_cache(self, ctx: Any, *, exclude_ids: tuple[str, ...] = ()) -> None:
        """Freeze snap targets at drag start.

        Point drags update the sketch every mouse event.  Rebuilding the snap target
        graph from that moving sketch is wasted work and can self-snap to the dragged
        handles.  The drag uses a frozen, excluded target set and clears it on release.
        """

        self._drag_targets_cache = self._filter_targets(self._full_live_snap_targets(ctx), exclude_ids)
        self._drag_targets_revision = (self._drag_targets_revision + 1) & 0xFFFFFFFF
        self._drag_screen_index_key = None
        self._drag_screen_index_targets = ()
        self._drag_screen_index_cells = {}
        self._drag_screen_index_fallback = ()

    def _end_drag_snap_cache(self) -> None:
        self._drag_targets_cache = None
        self._drag_screen_index_key = None
        self._drag_screen_index_targets = ()
        self._drag_screen_index_cells = {}
        self._drag_screen_index_fallback = ()
        # The live sketch may have moved while the frozen drag target tuple was
        # active. Force the first post-release hover through a clean rebuild.
        self.invalidate_geometry_cache()

    def invalidate_geometry_cache(self) -> None:
        """Invalidate compiled live targets and every derived local index.

        Geometry mutations are cheap to signal and expensive to rediscover from
        stale caches.  Centralizing the reset prevents a point/edge edit from
        leaving exact snaps unavailable while alignment axes still appear.
        """

        self._targets_signature = None
        self._targets_fast_signature = None
        self._targets_cache = ()
        self._screen_index_key = None
        self._screen_index_targets = ()
        self._screen_index_cells = {}
        self._screen_index_fallback = ()
        self._filtered_cache.clear()
        self._targets_revision = (self._targets_revision + 1) & 0xFFFFFFFF

    def _active_full_targets(self, ctx: Any) -> tuple[Any, ...]:
        if self._drag_targets_cache is not None:
            # Recover from a missed/consumed release.  A stale frozen cache often
            # excludes the grabbed point and every incident edge; the visible
            # symptom is that only U/V alignment axes continue to snap.
            selection = getattr(ctx, "selection", None)
            state = getattr(selection, "state", None)
            grab_active = getattr(state, "grab_active", None)
            if grab_active is False:
                self._end_drag_snap_cache()
            else:
                return tuple(self._drag_targets_cache)
        return self._full_live_snap_targets(ctx)

    def _full_live_snap_targets(self, ctx: Any) -> tuple[Any, ...]:
        # Two-stage cache. The cheap "fast signature" only inspects dict ids,
        # lengths and a couple of state pointers; it reliably hits on every
        # mouse move because topology mutations bump those counters. When it
        # misses we fall back to the full structural signature so position-only
        # edits (which keep the dict ids stable but move the same point) still
        # invalidate the cache correctly.
        with self._measure_perf(ctx, "plan_trace.snap_targets.fast_signature"):
            fast_sig = self._fast_snap_target_signature()
        if fast_sig is not None and fast_sig == self._targets_fast_signature:
            self._increment_perf(ctx, "plan_trace.snap_targets.fast_signature_hits")
            self._set_perf_value(ctx, "plan_trace.snap_targets.cached_total", len(self._targets_cache))
            return self._targets_cache
        self._increment_perf(ctx, "plan_trace.snap_targets.fast_signature_misses")
        with self._measure_perf(ctx, "plan_trace.snap_targets.structural_signature"):
            signature = self._snap_target_signature(ctx)
        if signature == self._targets_signature:
            self._increment_perf(ctx, "plan_trace.snap_targets.structural_signature_hits")
            self._targets_fast_signature = fast_sig
            self._set_perf_value(ctx, "plan_trace.snap_targets.cached_total", len(self._targets_cache))
            return self._targets_cache
        self._increment_perf(ctx, "plan_trace.snap_targets.structural_signature_misses")
        with self._measure_perf(ctx, "plan_trace.snap_targets.build_live_targets"):
            self._targets_cache = self._build_live_snap_targets(ctx)
        self._targets_revision = (self._targets_revision + 1) & 0xFFFFFFFF
        self._filtered_cache.clear()
        self._increment_perf(ctx, "plan_trace.snap_targets.rebuilds")
        self._set_perf_value(ctx, "plan_trace.snap_targets.total", len(self._targets_cache))
        self._targets_signature = signature
        self._targets_fast_signature = fast_sig
        self._screen_index_key = None
        self._screen_index_targets = ()
        self._screen_index_cells = {}
        self._screen_index_fallback = ()
        return self._targets_cache

    def _fast_snap_target_signature(self) -> tuple[Any, ...] | None:
        """Return a cheap identity-based signature for hover updates.

        Hovering over the viewport produces a high-frequency stream of mouse
        events. The structural signature visits every point/line/arc/circle in
        the sketch on every call; for dense sketches that walk became the next
        bottleneck once the plan2d guide cache was working. The cheap signature
        catches the common case "topology unchanged since last move" by hashing
        dict ids, lengths and a few state pointers — operations the structural
        version still does, but without the per-entity tuple builds.

        Returning ``None`` forces the caller to fall back to the structural
        signature (used when, e.g., a point was moved in place: the dict id and
        length are stable, but the cached cache must still be invalidated).
        """

        state = self._state
        sketch = state.sketch
        plane = state.display_plane or state.plane
        try:
            return (
                id(sketch.points), len(sketch.points),
                id(sketch.lines), len(sketch.lines),
                id(sketch.arcs), len(sketch.arcs),
                id(sketch.beziers), len(sketch.beziers),
                id(sketch.circles), len(sketch.circles),
                getattr(sketch, "_next_id", 0),
                id(plane),
                id(state.points), len(state.points),
                self._move_revision,
            )
        except Exception:
            return None

    def _bump_move_revision(self) -> None:
        """Invalidate the fast signature after an in-place point move.

        ``move_point`` mutates an existing dict entry without changing dict
        identity, so the fast signature alone cannot detect it. Drag and
        metric-driven edits call this to force the next snap-target query
        through the structural fallback.
        """

        self._move_revision = (self._move_revision + 1) & 0xFFFFFFFF

    def _snap_target_signature(self, ctx: Any) -> tuple[Any, ...]:  # noqa: ARG002
        plane = self._state.plane
        display_plane = self._state.display_plane or plane
        plane_sig = self._plane_signature(display_plane)
        points = tuple(
            (str(point_id), self._round3(world))
            for point_id, world in tuple(getattr(self._state, "points", ()) or ())
        )
        sketch = self._state.sketch
        line_sig = tuple(sorted((str(line_id), str(line.start_point_id), str(line.end_point_id)) for line_id, line in sketch.lines.items()))
        arc_sig = tuple(sorted((str(arc_id), str(arc.start_point_id), str(arc.end_point_id), str(arc.control_point_id)) for arc_id, arc in sketch.arcs.items()))
        bezier_sig = tuple(sorted((str(bezier_id), str(bezier.start_point_id), str(bezier.end_point_id), str(bezier.control_1_point_id), str(bezier.control_2_point_id)) for bezier_id, bezier in sketch.beziers.items()))
        circle_sig = tuple(sorted((str(circle_id), str(circle.center_point_id), str(circle.radius_point_id)) for circle_id, circle in sketch.circles.items()))
        anchor = self._round3(self._state.anchor_world) if self._state.anchor_world is not None else None
        return (plane_sig, points, line_sig, arc_sig, bezier_sig, circle_sig, anchor)

    @staticmethod
    def _plane_signature(plane: Any) -> tuple[float, ...] | None:
        if plane is None:
            return None
        try:
            values = (*plane.normal, *plane.u_axis, *plane.v_axis, float(plane.depth))
            return tuple(round(float(value), 6) for value in values)
        except Exception:
            return None

    @staticmethod
    def _round3(value: Any) -> tuple[int, int, int]:
        try:
            return (round(float(value[0]) * 100000), round(float(value[1]) * 100000), round(float(value[2]) * 100000))
        except Exception:
            return (0, 0, 0)

    def _build_live_snap_targets(self, ctx: Any) -> tuple[Any, ...]:
        """Return live Plan tracer construction targets for snap queries."""

        from laserprog_studio.tool_api import snap as snap_api
        plane = self._state.plane
        display_plane = self._state.display_plane or plane
        if plane is None or display_plane is None:
            self._set_perf_value(ctx, "plan_trace.snap_targets.total", 0)
            return ()
        targets = []
        point_count = line_count = arc_count = arc_segment_count = bezier_count = bezier_segment_count = circle_count = anchor_count = 0
        with self._measure_perf(ctx, "plan_trace.snap_targets.build.points"):
            for actor_id, semantic_world in tuple(self._state.points):
                try:
                    display_world = self.services.coordinates.semantic_world_to_display(semantic_world)
                    targets.append(
                        snap_api.tool_point(
                            actor_id,
                            display_world,
                            radius_px=16.0,
                            priority=8,
                            owner_tool=self.id,
                            metadata={"plan_trace_live_target": True, "snap_kind": "vertex"},
                            kind=snap_api.SnapKind.VERTEX,
                        )
                    )
                    point_count += 1
                except Exception:
                    continue
        with self._measure_perf(ctx, "plan_trace.snap_targets.build.lines"):
            for line_id, line in self._state.sketch.lines.items():
                actor_id = self.services.sketch_sync._line_actor_id(line_id)
                start = self._state.sketch.points.get(line.start_point_id)
                end = self._state.sketch.points.get(line.end_point_id)
                if start is None or end is None:
                    continue
                try:
                    targets.append(
                        snap_api.tool_segment(
                            actor_id,
                            self.services.coordinates.sketch_xy_to_display_world(start.position),
                            self.services.coordinates.sketch_xy_to_display_world(end.position),
                            radius_px=13.0,
                            priority=55,
                            owner_tool=self.id,
                            metadata={
                                "plan_trace_live_target": True,
                                "role": "edge",
                                "snap_kind": "edge",
                                "midpoint_radius_px": 12.0,
                                "plan_trace_point_ids": (str(line.start_point_id), str(line.end_point_id)),
                            },
                            kind=snap_api.SnapKind.EDGE,
                        )
                    )
                    line_count += 1
                except Exception:
                    continue
        with self._measure_perf(ctx, "plan_trace.snap_targets.build.arcs"):
            for arc_id, arc in self._state.sketch.arcs.items():
                actor_id = self.services.sketch_sync._arc_actor_id(arc_id)
                start_point = self._state.sketch.points.get(arc.start_point_id)
                end_point = self._state.sketch.points.get(arc.end_point_id)
                control_point = self._state.sketch.points.get(arc.control_point_id)
                point_ids = (str(arc.start_point_id), str(arc.end_point_id), str(arc.control_point_id))
                if start_point is not None and end_point is not None and control_point is not None:
                    try:
                        targets.append(
                            snap_api.tool_arc(
                                actor_id,
                                self.services.coordinates.sketch_xy_to_display_world(start_point.position),
                                self.services.coordinates.sketch_xy_to_display_world(end_point.position),
                                self.services.coordinates.sketch_xy_to_display_world(control_point.position),
                                radius_px=11.0,
                                priority=68,
                                owner_tool=self.id,
                                metadata={
                                    "plan_trace_live_target": True,
                                    "role": "curve",
                                    "snap_kind": "edge",
                                    "curve_type": "arc",
                                    "parent_arc_id": arc_id,
                                    "include_intersection_snap": True,
                                    "intersection_radius_px": 10.0,
                                    "plan_trace_point_ids": point_ids,
                                },
                                kind=snap_api.SnapKind.EDGE,
                            )
                        )
                        arc_count += 1
                    except Exception:
                        pass
                with self._measure_perf(ctx, "plan_trace.snap_targets.build.arc_samples"):
                    points = self.services.coordinates.sample_arc_display_points(arc, segments=24)
                if len(points) < 2:
                    continue
                for index, (start_world, end_world) in enumerate(zip(points, points[1:])):
                    try:
                        targets.append(
                            snap_api.tool_segment(
                                f"{actor_id}:seg:{index}",
                                start_world,
                                end_world,
                                radius_px=11.0,
                                priority=48,
                                owner_tool=self.id,
                                metadata={
                                    "plan_trace_live_target": True,
                                    "role": "curve",
                                    "snap_kind": "edge",
                                    "curve_type": "arc",
                                    "parent_arc_id": arc_id,
                                    "include_midpoint_snap": False,
                                    "intersection_radius_px": 9.0,
                                    "plan_trace_point_ids": point_ids,
                                },
                                kind=snap_api.SnapKind.EDGE,
                            )
                        )
                        arc_segment_count += 1
                    except Exception:
                        continue
        with self._measure_perf(ctx, "plan_trace.snap_targets.build.beziers"):
            for bezier_id, bezier in self._state.sketch.beziers.items():
                actor_id = self.services.sketch_sync._bezier_actor_id(bezier_id)
                start_point = self._state.sketch.points.get(bezier.start_point_id)
                end_point = self._state.sketch.points.get(bezier.end_point_id)
                control_1 = self._state.sketch.points.get(bezier.control_1_point_id)
                control_2 = self._state.sketch.points.get(bezier.control_2_point_id)
                if start_point is None or end_point is None or control_1 is None or control_2 is None:
                    continue
                point_ids = (
                    str(bezier.start_point_id),
                    str(bezier.end_point_id),
                    str(bezier.control_1_point_id),
                    str(bezier.control_2_point_id),
                )
                try:
                    samples_xy = sample_cubic_bezier(
                        start_point.position,
                        control_1.position,
                        control_2.position,
                        end_point.position,
                        segments=40,
                    )
                except Exception:
                    continue
                display_points = []
                for sample in samples_xy:
                    try:
                        display_points.append(self.services.coordinates.sketch_xy_to_display_world(sample))
                    except Exception:
                        pass
                if len(display_points) < 2:
                    continue
                bezier_count += 1
                for index, (start_world, end_world) in enumerate(zip(display_points, display_points[1:])):
                    try:
                        targets.append(
                            snap_api.tool_segment(
                                f"{actor_id}:seg:{index}",
                                start_world,
                                end_world,
                                radius_px=11.0,
                                priority=52,
                                owner_tool=self.id,
                                metadata={
                                    "plan_trace_live_target": True,
                                    "role": "curve",
                                    "snap_kind": "edge",
                                    "curve_type": "bezier",
                                    "parent_bezier_id": bezier_id,
                                    "include_midpoint_snap": False,
                                    "intersection_radius_px": 9.0,
                                    "plan_trace_point_ids": point_ids,
                                },
                                kind=snap_api.SnapKind.EDGE,
                            )
                        )
                        bezier_segment_count += 1
                    except Exception:
                        continue
        with self._measure_perf(ctx, "plan_trace.snap_targets.build.circles"):
            for circle_id, circle in self._state.sketch.circles.items():
                actor_id = self.services.sketch_sync._circle_actor_id(circle_id)
                center = self._state.sketch.points.get(circle.center_point_id)
                radius_point = self._state.sketch.points.get(circle.radius_point_id)
                if center is None or radius_point is None:
                    continue
                try:
                    center_world = self.services.coordinates.sketch_xy_to_display_world(center.position)
                    radius_world = self.services.coordinates.sketch_xy_to_display_world(radius_point.position)
                    radius = (
                        (float(radius_world[0]) - float(center_world[0])) ** 2
                        + (float(radius_world[1]) - float(center_world[1])) ** 2
                        + (float(radius_world[2]) - float(center_world[2])) ** 2
                    ) ** 0.5
                    if radius <= 1.0e-8:
                        continue
                    targets.append(
                        snap_api.tool_circle(
                            actor_id,
                            center_world,
                            radius,
                            radius_px=13.0,
                            priority=58,
                            owner_tool=self.id,
                            basis_u=display_plane.u_axis,
                            basis_v=display_plane.v_axis,
                            metadata={
                                "plan_trace_live_target": True,
                                "role": "curve",
                                "curve_type": "circle",
                                "include_center_snap": True,
                                "include_quadrant_snap": True,
                                "include_angle_snap": True,
                                "angle_step_degrees": 45.0,
                                "curve_radius_px": 12.0,
                                "plan_trace_point_ids": (str(circle.center_point_id), str(circle.radius_point_id)),
                            },
                        )
                    )
                    circle_count += 1
                except Exception:
                    continue
        with self._measure_perf(ctx, "plan_trace.snap_targets.build.anchor"):
            if self._state.anchor_world is not None:
                try:
                    display_anchor = self.services.coordinates.semantic_world_to_display(self._state.anchor_world)
                    targets.append(
                        snap_api.tool_point(
                            _ANCHOR_ID,
                            display_anchor,
                            radius_px=18.0,
                            priority=18,
                            owner_tool=self.id,
                            metadata={"plan_trace_live_target": True, "role": "height_anchor", "snap_kind": "vertex"},
                            kind=snap_api.SnapKind.VERTEX,
                        )
                    )
                    anchor_count += 1
                except Exception:
                    pass
        self._set_perf_value(ctx, "plan_trace.snap_targets.points", point_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.lines", line_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.arcs", arc_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.arc_segments", arc_segment_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.beziers", bezier_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.bezier_segments", bezier_segment_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.circles", circle_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.anchors", anchor_count)
        self._set_perf_value(ctx, "plan_trace.snap_targets.total", len(targets))
        return tuple(targets)

    def _ensure_screen_index(self, ctx: Any, targets: tuple[Any, ...]) -> tuple[tuple[Any, ...], dict[tuple[int, int], tuple[int, ...]], tuple[int, ...]]:
        projection_sig = self._projection_signature(ctx)
        is_drag_pool = targets is self._drag_targets_cache
        revision = self._drag_targets_revision if is_drag_pool else self._targets_revision
        key = (revision, id(targets), len(targets), projection_sig, float(_PLAN_TRACE_SNAP_CELL_SIZE_PX))
        if is_drag_pool:
            if key != self._drag_screen_index_key:
                self._record_screen_index_miss(ctx, self._drag_screen_index_key, key, drag=True)
                target_pool, cells, fallback = self._build_screen_index(ctx, targets)
                self._drag_screen_index_key = key
                self._drag_screen_index_targets = target_pool
                self._drag_screen_index_cells = cells
                self._drag_screen_index_fallback = fallback
            else:
                self._increment_perf(ctx, "plan_trace.snap.screen_index_hits")
            return self._drag_screen_index_targets, self._drag_screen_index_cells, self._drag_screen_index_fallback
        if key != self._screen_index_key:
            self._record_screen_index_miss(ctx, self._screen_index_key, key, drag=False)
            target_pool, cells, fallback = self._build_screen_index(ctx, targets)
            self._screen_index_key = key
            self._screen_index_targets = target_pool
            self._screen_index_cells = cells
            self._screen_index_fallback = fallback
        else:
            self._increment_perf(ctx, "plan_trace.snap.screen_index_hits")
        return self._screen_index_targets, self._screen_index_cells, self._screen_index_fallback


    def _record_screen_index_miss(self, ctx: Any, previous: tuple[Any, ...] | None, key: tuple[Any, ...], *, drag: bool) -> None:
        self._increment_perf(ctx, "plan_trace.snap.screen_index_misses")
        if drag:
            self._increment_perf(ctx, "plan_trace.snap.screen_index_misses.drag")
        if previous is None:
            self._increment_perf(ctx, "plan_trace.snap.rebuild_reason.initial")
            return
        try:
            if previous[0] != key[0] or previous[1] != key[1] or previous[2] != key[2]:
                self._increment_perf(ctx, "plan_trace.snap.rebuild_reason.targets")
            elif previous[3] != key[3]:
                self._increment_perf(ctx, "plan_trace.snap.rebuild_reason.projection")
            elif previous[4] != key[4]:
                self._increment_perf(ctx, "plan_trace.snap.rebuild_reason.cell_size")
            else:
                self._increment_perf(ctx, "plan_trace.snap.rebuild_reason.unknown")
        except Exception:
            self._increment_perf(ctx, "plan_trace.snap.rebuild_reason.error")

    def _build_screen_index(self, ctx: Any, targets: tuple[Any, ...]) -> tuple[tuple[Any, ...], dict[tuple[int, int], tuple[int, ...]], tuple[int, ...]]:
        measure = self._measure_perf(ctx, "plan_trace.snap.build_screen_index")
        with measure:
            cell = float(_PLAN_TRACE_SNAP_CELL_SIZE_PX)
            mutable_cells: dict[tuple[int, int], list[int]] = {}
            fallback: list[int] = []
            for index, target in enumerate(targets):
                bbox = self._target_screen_bbox(ctx, target)
                if bbox is None or not all(isfinite(float(value)) for value in bbox):
                    fallback.append(int(index))
                    continue
                min_x, min_y, max_x, max_y = bbox
                min_cx = floor(float(min_x) / cell)
                max_cx = floor(float(max_x) / cell)
                min_cy = floor(float(min_y) / cell)
                max_cy = floor(float(max_y) / cell)
                cell_count = (int(max_cx) - int(min_cx) + 1) * (int(max_cy) - int(min_cy) + 1)
                if cell_count <= 0 or cell_count > int(_PLAN_TRACE_SNAP_MAX_CELLS_PER_TARGET):
                    fallback.append(int(index))
                    continue
                for cx in range(int(min_cx), int(max_cx) + 1):
                    for cy in range(int(min_cy), int(max_cy) + 1):
                        mutable_cells.setdefault((cx, cy), []).append(int(index))
            cells = {key: tuple(values) for key, values in mutable_cells.items()}
            self._increment_perf(ctx, "plan_trace.snap.index_targets", len(targets))
            self._increment_perf(ctx, "plan_trace.snap.index_cells", len(cells))
            self._increment_perf(ctx, "plan_trace.snap.index_fallback_targets", len(fallback))
            return tuple(targets), cells, tuple(fallback)

    def _target_screen_bbox(self, ctx: Any, target: Any) -> tuple[float, float, float, float] | None:
        padding = max(float(getattr(target, "radius_px", 14.0) or 14.0), 0.0) + 4.0
        metadata = getattr(target, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = None
        if bool(getattr(target, "is_circle", False)):
            return self._circle_screen_bbox(ctx, target, padding)
        if bool(getattr(target, "is_arc", False)):
            return self._arc_screen_bbox(ctx, target, padding)
        if bool(getattr(target, "is_segment", False)) and getattr(target, "start", None) is not None and getattr(target, "end", None) is not None:
            a = self._world_to_screen(ctx, target.start)
            b = self._world_to_screen(ctx, target.end)
            if metadata is not None:
                metadata["snap_start_screen"] = (float(a[0]), float(a[1]))
                metadata["snap_end_screen"] = (float(b[0]), float(b[1]))
                metadata["snap_midpoint_screen"] = ((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5)
            return (min(a[0], b[0]) - padding, min(a[1], b[1]) - padding, max(a[0], b[0]) + padding, max(a[1], b[1]) + padding)
        if getattr(target, "screen_pos", None) is not None:
            x, y = self._point2(target.screen_pos)
        elif getattr(target, "world_pos", None) is not None:
            x, y = self._world_to_screen(ctx, target.world_pos)
        else:
            return None
        if metadata is not None:
            metadata["snap_screen_pos"] = (float(x), float(y))
        return (x - padding, y - padding, x + padding, y + padding)

    def _circle_screen_bbox(self, ctx: Any, target: Any, padding: float) -> tuple[float, float, float, float] | None:
        center = getattr(target, "center", None)
        radius = getattr(target, "radius", None)
        if center is None or radius is None:
            return None
        try:
            r = float(radius)
            if not isfinite(r) or r <= 0.0:
                return None
            c = (float(center[0]), float(center[1]), float(center[2]) if len(center) > 2 else 0.0)
            basis_u = self._normalize_vec3(getattr(target, "basis_u", None), fallback=(1.0, 0.0, 0.0))
            basis_v = self._normalize_vec3(getattr(target, "basis_v", None), fallback=(0.0, 1.0, 0.0))
            samples = [self._world_to_screen(ctx, c)]
            sample_count = max(8, int(_PLAN_TRACE_CURVE_BBOX_SAMPLE_COUNT))
            for index in range(sample_count):
                angle = (2.0 * pi * float(index)) / float(sample_count)
                ca = cos(angle)
                sa = sin(angle)
                world = (
                    c[0] + r * (basis_u[0] * ca + basis_v[0] * sa),
                    c[1] + r * (basis_u[1] * ca + basis_v[1] * sa),
                    c[2] + r * (basis_u[2] * ca + basis_v[2] * sa),
                )
                samples.append(self._world_to_screen(ctx, world))
            return self._bbox_from_screen_points(samples, padding)
        except Exception:
            return None

    def _arc_screen_bbox(self, ctx: Any, target: Any, padding: float) -> tuple[float, float, float, float] | None:
        start = getattr(target, "start", None)
        end = getattr(target, "end", None)
        control = getattr(target, "control", None)
        if start is None or end is None or control is None:
            return None
        try:
            s = (float(start[0]), float(start[1]), float(start[2]) if len(start) > 2 else 0.0)
            e = (float(end[0]), float(end[1]), float(end[2]) if len(end) > 2 else 0.0)
            c = (float(control[0]), float(control[1]), float(control[2]) if len(control) > 2 else 0.0)
            sample_count = max(8, int(_PLAN_TRACE_CURVE_BBOX_SAMPLE_COUNT))
            arc_points = sample_plan_arc_xy((s[0], s[1]), (e[0], e[1]), (c[0], c[1]), segments=sample_count)
            samples = [self._world_to_screen(ctx, s), self._world_to_screen(ctx, c), self._world_to_screen(ctx, e)]
            denom = max(1, len(arc_points) - 1)
            for index, (x, y) in enumerate(arc_points):
                t = float(index) / float(denom)
                z = s[2] + (e[2] - s[2]) * t
                samples.append(self._world_to_screen(ctx, (float(x), float(y), float(z))))
            return self._bbox_from_screen_points(samples, padding)
        except Exception:
            return None

    @staticmethod
    def _bbox_from_screen_points(points: Any, padding: float) -> tuple[float, float, float, float] | None:
        xs: list[float] = []
        ys: list[float] = []
        for point in points:
            try:
                x = float(point[0])
                y = float(point[1])
            except Exception:
                continue
            if isfinite(x) and isfinite(y):
                xs.append(x)
                ys.append(y)
        if not xs or not ys:
            return None
        return (min(xs) - padding, min(ys) - padding, max(xs) + padding, max(ys) + padding)

    @staticmethod
    def _normalize_vec3(value: Any, *, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
        try:
            vec = (float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.0)
            length = sqrt(vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2])
            if length > 1.0e-12 and isfinite(length):
                return (vec[0] / length, vec[1] / length, vec[2] / length)
        except Exception:
            pass
        return fallback

    @staticmethod
    def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
        profiler = getattr(ctx, "profiler", None)
        increment = getattr(profiler, "increment", None)
        if not callable(increment):
            return
        try:
            increment(str(name), int(value))
        except Exception:
            pass

    @staticmethod
    def _set_perf_value(ctx: Any, name: str, value: Any) -> None:
        profiler = getattr(ctx, "profiler", None)
        setter = getattr(profiler, "set_value", None)
        if not callable(setter):
            return
        try:
            setter(str(name), value)
        except Exception:
            pass

    @staticmethod
    def _measure_perf(ctx: Any, name: str) -> Any:
        from contextlib import nullcontext

        profiler = getattr(ctx, "profiler", None)
        measure = getattr(profiler, "measure", None)
        if callable(measure):
            try:
                return measure(str(name))
            except Exception:
                pass
        return nullcontext()

    def _projection_signature(self, ctx: Any) -> tuple[Any, ...]:
        return projection_cache_signature(ctx)

    @staticmethod
    def _world_to_screen(ctx: Any, pos: Any) -> tuple[float, float]:
        viewport = getattr(ctx, "viewport", None)
        world_to_screen = getattr(viewport, "world_to_screen", None)
        if callable(world_to_screen):
            try:
                projected = world_to_screen(pos)
                return (float(projected[0]), float(projected[1]))
            except Exception:
                pass
        return (float(pos[0]), float(pos[1]))

    @staticmethod
    def _point2(value: Any) -> tuple[float, float]:
        return (float(value[0]), float(value[1]))

    def _filter_targets(self, targets: tuple[Any, ...], exclude_ids: tuple[str, ...]) -> tuple[Any, ...]:
        excluded = {str(value) for value in exclude_ids}
        if not excluded:
            return tuple(targets)
        return tuple(target for target in targets if not self._target_excluded(target, excluded))

    @staticmethod
    def _target_excluded(target: Any, excluded: set[str]) -> bool:
        target_id = str(getattr(target, "id", "") or "")
        if any(target_id == item or target_id.startswith(f"{item}:") for item in excluded):
            return True
        try:
            point_ids = tuple(str(value) for value in dict(getattr(target, "metadata", {}) or {}).get("plan_trace_point_ids", ()) or ())
        except Exception:
            point_ids = ()
        return any(point_id in excluded for point_id in point_ids)



__all__ = ["PlanTrace2DSnapTargetsService"]
