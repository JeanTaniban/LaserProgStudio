"""Shared scene cache used by smart snap and creator tools.

The cache is split into explicit layers so a creator tool can reason about what
will survive a rebuild:

* scene/sketch/actor layers are rebuilt from the current context;
* tool-temp points/segments are persistent construction targets owned by tools;
* extra snap targets are persistent UI/custom targets supplied by tools.

This avoids the Pass123 ambiguity where a point added with ``add_point`` could be
silently removed by the next smart-snap cache rebuild.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Literal

from .selection import Point3
from .snap.types import Point2, SnapSource, SnapTarget

SceneCacheScope = Literal["all", "snap", "selection", "geometry"]

# Hard caps keep smart-snap cache rebuilds predictable on dense imported parts.
# The cache still adds bounding-box corners/edges for every mesh, so coarse scene
# snapping remains available even when vertex/triangle sampling is throttled.
MAX_MESH_SNAP_POINTS = 1200
MAX_MESH_SNAP_EDGES = 3000
SNAP_SCREEN_INDEX_CELL_SIZE_PX = 64.0
SNAP_SCREEN_INDEX_MAX_CELLS_PER_TARGET = 2048
SNAP_SCREEN_INDEX_QUERY_MARGIN_PX = 96.0
SNAP_CURVE_BBOX_SAMPLE_COUNT = 24


@dataclass(frozen=True, slots=True)
class ScenePoint:
    id: str
    position: Point3
    source: str = "scene"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SceneSegment:
    id: str
    start: Point3
    end: Point3
    source: str = "scene"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SceneCacheSummary:
    version: int
    valid: bool
    scope: SceneCacheScope
    points: int
    segments: int
    bounds: int
    extra_targets: int
    tool_points: int = 0
    tool_segments: int = 0
    ui_targets: int = 0


@dataclass(frozen=True, slots=True)
class SceneBounds:
    minimum: Point3
    maximum: Point3

    @property
    def center(self) -> Point3:
        return (
            (self.minimum[0] + self.maximum[0]) * 0.5,
            (self.minimum[1] + self.maximum[1]) * 0.5,
            (self.minimum[2] + self.maximum[2]) * 0.5,
        )


class SceneCache:
    """Versioned cache of scene data useful to tools.

    ``rebuild`` accepts any context-like object. It discovers data through stable
    methods/attributes when present:

    - ``ctx.sketch.sketch_points_for_snap()`` and ``sketch_segments_for_snap()``;
    - ``ctx.selection.actors()`` for registered tool actors;
    - optional scene methods such as ``snap_points()`` or ``snap_segments()``.

    Tool-provided temporary points/segments and UI targets are never cleared by a
    rebuild. Use ``clear_tool_targets`` explicitly when a tool closes or resets.
    """

    def __init__(self) -> None:
        self.version = 0
        self.valid = False
        self.scope: SceneCacheScope = "all"
        self._points: list[ScenePoint] = []
        self._segments: list[SceneSegment] = []
        self._bounds: list[SceneBounds] = []
        self._tool_points: list[ScenePoint] = []
        self._tool_segments: list[SceneSegment] = []
        self._extra_targets: list[SnapTarget] = []
        self._snap_screen_index_key: tuple[Any, ...] | None = None
        self._snap_screen_index_targets: tuple[SnapTarget, ...] = ()
        self._snap_screen_index_cells: dict[tuple[int, int], list[int]] = {}
        self._snap_screen_index_fallback_indices: tuple[int, ...] = ()
        # Structural snap data changes much less often than the global cache
        # version.  Transient UI actors such as the Plan Tracer cursor invalidate
        # the broad scene cache on every mouse move, but they do not change the
        # mesh/sketch snap target pool.  Keep a separate stamp for screen-space
        # snap indices and Plan2D guide caches so hover does not rebuild them.
        self._snap_structure_version = 0

    def invalidate(self) -> None:
        self.valid = False
        self.version += 1

    def _touch(self) -> None:
        self.version += 1

    def _touch_snap_structure(self) -> None:
        self._snap_structure_version += 1
        self._touch()

    def snap_structure_signature(self) -> tuple[Any, ...]:
        """Return a stable stamp for the actual snap-target pool.

        ``version`` also changes for unrelated UI/selection invalidations.  The
        snap structure stamp changes only when the lists that feed
        ``snap_targets()`` are rebuilt or edited.
        """

        return (
            int(self._snap_structure_version),
            len(self._points),
            len(self._segments),
            len(self._bounds),
            len(self._tool_points),
            len(self._tool_segments),
            len(self._extra_targets),
        )

    def clear(self) -> None:
        self._points.clear()
        self._segments.clear()
        self._bounds.clear()
        self._tool_points.clear()
        self._tool_segments.clear()
        self._extra_targets.clear()
        self.valid = False
        self.version += 1
        self._snap_structure_version += 1

    def rebuild(
        self,
        ctx: Any,
        *,
        scope: SceneCacheScope = "all",
        include_selection: bool = True,
        include_sketch: bool = True,
        include_scene: bool = True,
        exclude_ids: Iterable[str] = (),
    ) -> "SceneCache":
        """Rebuild context-derived layers without touching tool-temp targets."""

        with _measure_perf(ctx, "scene_cache.rebuild.total"):
            excluded = {str(value) for value in exclude_ids}
            self.scope = scope
            self._points = []
            self._segments = []
            self._bounds = []

            if include_sketch:
                with _measure_perf(ctx, "scene_cache.rebuild.collect_sketch"):
                    self._collect_sketch(ctx, excluded)
            if include_selection:
                with _measure_perf(ctx, "scene_cache.rebuild.collect_selection"):
                    self._collect_selection(ctx, excluded)
            if include_scene:
                with _measure_perf(ctx, "scene_cache.rebuild.collect_scene"):
                    self._collect_scene(ctx, excluded)
                with _measure_perf(ctx, "scene_cache.rebuild.collect_document_meshes"):
                    self._collect_document_meshes(ctx, excluded)

            self.valid = True
            self.version += 1
            self._snap_structure_version += 1
            _increment_perf(ctx, "scene_cache.rebuild.calls")
            _set_perf_value(ctx, "scene_cache.points", len(self._points) + len(self._tool_points))
            _set_perf_value(ctx, "scene_cache.segments", len(self._segments) + len(self._tool_segments))
            _set_perf_value(ctx, "scene_cache.bounds", len(self._bounds))
            _set_perf_value(ctx, "scene_cache.extra_targets", len(self._extra_targets))
            _set_perf_value(ctx, "scene_cache.version", self.version)
            return self

    def add_point(
        self,
        point_id: str,
        position: Iterable[float],
        *,
        source: str = SnapSource.TOOL_TEMP_POINT.value,
        owner_tool: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ScenePoint:
        """Add a persistent tool-temp point that survives ``rebuild``.

        This is intended for construction guides and custom smart-snap targets.
        For one-shot targets during a single query, prefer ``ctx.snap.smart(...,
        extra_targets=[...])``.
        """

        data = dict(metadata or {})
        if owner_tool is not None:
            data.setdefault("owner_tool", str(owner_tool))
        point = ScenePoint(str(point_id), _point3(position), str(source), data)
        self._tool_points = [existing for existing in self._tool_points if existing.id != point.id]
        self._tool_points.append(point)
        self._touch_snap_structure()
        return point

    def add_segment(
        self,
        segment_id: str,
        start: Iterable[float],
        end: Iterable[float],
        *,
        source: str = SnapSource.TOOL_TEMP_EDGE.value,
        owner_tool: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SceneSegment:
        """Add a persistent tool-temp segment that survives ``rebuild``."""

        data = dict(metadata or {})
        if owner_tool is not None:
            data.setdefault("owner_tool", str(owner_tool))
        segment = SceneSegment(str(segment_id), _point3(start), _point3(end), str(source), data)
        self._tool_segments = [existing for existing in self._tool_segments if existing.id != segment.id]
        self._tool_segments.append(segment)
        self._touch_snap_structure()
        return segment

    def add_snap_target(self, target: SnapTarget, *, owner_tool: str | None = None) -> SnapTarget:
        if owner_tool is not None:
            metadata = {**target.metadata, "owner_tool": str(owner_tool)}
            target = SnapTarget(
                id=target.id,
                source=target.source,
                world_pos=target.world_pos,
                screen_pos=target.screen_pos,
                start=target.start,
                end=target.end,
                radius_px=target.radius_px,
                priority=target.priority,
                metadata=metadata,
            )
        self._extra_targets = [existing for existing in self._extra_targets if existing.id != target.id]
        self._extra_targets.append(target)
        self._touch_snap_structure()
        return target

    def set_snap_targets(self, targets: Iterable[SnapTarget], *, owner_tool: str | None = None) -> None:
        incoming = list(targets)
        if owner_tool is None:
            self._extra_targets = incoming
        else:
            owner = str(owner_tool)
            self._extra_targets = [target for target in self._extra_targets if target.metadata.get("owner_tool") != owner]
            self._extra_targets.extend(self._with_owner(target, owner) for target in incoming)
        self._touch_snap_structure()

    def clear_snap_targets(self) -> None:
        if self._extra_targets:
            self._extra_targets.clear()
            self._touch_snap_structure()

    def clear_tool_targets(self, owner_tool: str | None = None) -> None:
        """Clear persistent tool-temp and UI/custom targets.

        When ``owner_tool`` is provided, only targets tagged with that owner are
        removed. Untagged targets are considered global tool-cache targets.
        """

        if owner_tool is None:
            changed = bool(self._tool_points or self._tool_segments or self._extra_targets)
            self._tool_points.clear()
            self._tool_segments.clear()
            self._extra_targets.clear()
            if changed:
                self._touch_snap_structure()
            return
        owner = str(owner_tool)
        before = (len(self._tool_points), len(self._tool_segments), len(self._extra_targets))
        self._tool_points = [point for point in self._tool_points if point.metadata.get("owner_tool") != owner]
        self._tool_segments = [segment for segment in self._tool_segments if segment.metadata.get("owner_tool") != owner]
        self._extra_targets = [target for target in self._extra_targets if target.metadata.get("owner_tool") != owner]
        after = (len(self._tool_points), len(self._tool_segments), len(self._extra_targets))
        if before != after:
            self._touch_snap_structure()

    def add_ui_point(
        self,
        target_id: str,
        screen_pos: Point2,
        *,
        world_pos: Iterable[float] | None = None,
        radius_px: float = 14.0,
        priority: int = 15,
        owner_tool: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SnapTarget:
        data = dict(metadata or {})
        if owner_tool is not None:
            data.setdefault("owner_tool", str(owner_tool))
        target = SnapTarget.ui_point(
            str(target_id),
            (float(screen_pos[0]), float(screen_pos[1])),
            world_pos=_point3(world_pos) if world_pos is not None else None,
            radius_px=radius_px,
            priority=priority,
            metadata=data,
        )
        return self.add_snap_target(target)

    def summary(self) -> SceneCacheSummary:
        ui_targets = sum(1 for target in self._extra_targets if target.source in {SnapSource.UI_POINT, SnapSource.UI_EDGE})
        return SceneCacheSummary(
            version=self.version,
            valid=self.valid,
            scope=self.scope,
            points=len(self.points()),
            segments=len(self.segments()),
            bounds=len(self._bounds),
            extra_targets=len(self._extra_targets),
            tool_points=len(self._tool_points),
            tool_segments=len(self._tool_segments),
            ui_targets=ui_targets,
        )

    def points(self) -> tuple[ScenePoint, ...]:
        return (*self._points, *self._tool_points)

    def segments(self) -> tuple[SceneSegment, ...]:
        return (*self._segments, *self._tool_segments)

    def bounds(self) -> tuple[SceneBounds, ...]:
        return tuple(self._bounds)

    def centers(self) -> tuple[ScenePoint, ...]:
        return tuple(ScenePoint(f"bounds:{index}:center", bounds.center, "bounds") for index, bounds in enumerate(self._bounds))

    def snap_targets(self) -> tuple[SnapTarget, ...]:
        targets: list[SnapTarget] = []
        for point in self.points():
            source = _snap_source_from_text(point.source, point=True)
            targets.append(SnapTarget.point(point.id, point.position, source=source, metadata=point.metadata))
        for segment in self.segments():
            source = _snap_source_from_text(segment.source, point=False)
            targets.append(SnapTarget.segment(segment.id, segment.start, segment.end, source=source, metadata=segment.metadata))
        for center in self.centers():
            targets.append(SnapTarget.point(center.id, center.position, source=SnapSource.CENTER, metadata=center.metadata))
        targets.extend(self._extra_targets)
        return tuple(targets)

    def snap_targets_near(
        self,
        screen_pos: Point2,
        ctx: Any,
        *,
        query_margin_px: float = SNAP_SCREEN_INDEX_QUERY_MARGIN_PX,
    ) -> tuple[SnapTarget, ...]:
        """Return snap targets whose screen footprint can affect this query.

        Dense scenes can contain thousands of mesh/bounds targets.  Smart snap only
        accepts hits inside a small pixel radius, so rescanning every target on every
        mouse move wastes most of the drag budget.  This lazy screen-space grid keeps
        the full-quality target set, but only evaluates targets whose projected
        point/segment bounding box overlaps the cursor neighbourhood.  Curves or
        unknown targets fall back to the always-checked set so correctness wins over
        pruning when a cheap bound is unavailable.
        """

        with _measure_perf(ctx, "scene_cache.snap.near_query.total"):
            key = (self.snap_structure_signature(), self._snap_projection_signature(ctx), float(SNAP_SCREEN_INDEX_CELL_SIZE_PX))
            if key != self._snap_screen_index_key:
                self._record_snap_index_miss(ctx, key)
                self._rebuild_snap_screen_index(ctx, key=key)
            else:
                _increment_perf(ctx, "scene_cache.snap.screen_index_hits")
                _set_perf_value(ctx, "scene_cache.snap.rebuild_reason.last", "hit")
            if not self._snap_screen_index_targets:
                return ()
            sx, sy = _point2(screen_pos)
            cell = float(SNAP_SCREEN_INDEX_CELL_SIZE_PX)
            margin = max(float(query_margin_px), 0.0)
            min_cx = math.floor((sx - margin) / cell)
            max_cx = math.floor((sx + margin) / cell)
            min_cy = math.floor((sy - margin) / cell)
            max_cy = math.floor((sy + margin) / cell)
            indices: set[int] = set(self._snap_screen_index_fallback_indices)
            cells = self._snap_screen_index_cells
            with _measure_perf(ctx, "scene_cache.snap.near_query.cells"):
                for cx in range(int(min_cx), int(max_cx) + 1):
                    for cy in range(int(min_cy), int(max_cy) + 1):
                        for index in cells.get((cx, cy), ()):  # usually tiny
                            indices.add(int(index))
            targets = self._snap_screen_index_targets
            with _measure_perf(ctx, "scene_cache.snap.near_query.materialize"):
                result = tuple(targets[index] for index in sorted(indices) if 0 <= index < len(targets))
            _increment_perf(ctx, "scene_cache.snap.near_queries")
            _increment_perf(ctx, "scene_cache.snap.near_targets", len(result))
            _increment_perf(ctx, "scene_cache.snap.near_candidates", len(indices))
            _increment_perf(ctx, "scene_cache.snap.near_fallback", len(self._snap_screen_index_fallback_indices))
            _set_perf_value(ctx, "scene_cache.snap.last_near_targets", len(result))
            _set_perf_value(ctx, "scene_cache.snap.last_near_candidates", len(indices))
            return result


    def _record_snap_index_miss(self, ctx: Any, key: tuple[Any, ...]) -> None:
        previous = self._snap_screen_index_key
        _increment_perf(ctx, "scene_cache.snap.screen_index_misses")
        reason = "initial"
        if previous is None:
            _increment_perf(ctx, "scene_cache.snap.rebuild_reason.initial")
        else:
            try:
                if previous[0] != key[0]:
                    reason = "structure"
                    _increment_perf(ctx, "scene_cache.snap.rebuild_reason.structure")
                elif previous[1] != key[1]:
                    reason = "projection"
                    _increment_perf(ctx, "scene_cache.snap.rebuild_reason.projection")
                elif previous[2] != key[2]:
                    reason = "cell_size"
                    _increment_perf(ctx, "scene_cache.snap.rebuild_reason.cell_size")
                else:
                    reason = "unknown"
                    _increment_perf(ctx, "scene_cache.snap.rebuild_reason.unknown")
            except Exception:
                reason = "error"
                _increment_perf(ctx, "scene_cache.snap.rebuild_reason.error")
        _set_perf_value(ctx, "scene_cache.snap.rebuild_reason.last", reason)
        try:
            _set_perf_value(ctx, "scene_cache.snap.projection_signature_changed", int(previous is not None and previous[1] != key[1]))
            _set_perf_value(ctx, "scene_cache.snap.structure_signature_changed", int(previous is not None and previous[0] != key[0]))
        except Exception:
            pass

    def _rebuild_snap_screen_index(self, ctx: Any, *, key: tuple[Any, ...]) -> None:
        with _measure_perf(ctx, "scene_cache.snap.rebuild_screen_index"):
            targets = self.snap_targets()
            cell = float(SNAP_SCREEN_INDEX_CELL_SIZE_PX)
            cells: dict[tuple[int, int], list[int]] = {}
            fallback: list[int] = []
            for index, target in enumerate(targets):
                bbox = self._snap_target_screen_bbox(target, ctx)
                if bbox is None:
                    fallback.append(index)
                    continue
                min_x, min_y, max_x, max_y = bbox
                if not all(math.isfinite(value) for value in bbox):
                    fallback.append(index)
                    continue
                min_cx = math.floor(min_x / cell)
                max_cx = math.floor(max_x / cell)
                min_cy = math.floor(min_y / cell)
                max_cy = math.floor(max_y / cell)
                cell_count = (int(max_cx) - int(min_cx) + 1) * (int(max_cy) - int(min_cy) + 1)
                if cell_count <= 0 or cell_count > int(SNAP_SCREEN_INDEX_MAX_CELLS_PER_TARGET):
                    # Very large or unbounded projected targets are rare but important.
                    # Keep them correct by checking them every query rather than trying
                    # to put them in thousands of cells.
                    fallback.append(index)
                    continue
                for cx in range(int(min_cx), int(max_cx) + 1):
                    for cy in range(int(min_cy), int(max_cy) + 1):
                        cells.setdefault((cx, cy), []).append(index)
        self._snap_screen_index_key = key
        self._snap_screen_index_targets = targets
        self._snap_screen_index_cells = cells
        self._snap_screen_index_fallback_indices = tuple(fallback)
        _increment_perf(ctx, "scene_cache.snap.index_targets", len(targets))
        _increment_perf(ctx, "scene_cache.snap.index_cells", len(cells))
        _increment_perf(ctx, "scene_cache.snap.index_fallback", len(fallback))
        _set_perf_value(ctx, "scene_cache.snap.index_targets", len(targets))
        _set_perf_value(ctx, "scene_cache.snap.index_cells", len(cells))
        _set_perf_value(ctx, "scene_cache.snap.index_fallback", len(fallback))

    def _snap_projection_signature(self, ctx: Any) -> tuple[Any, ...]:
        return projection_cache_signature(ctx)

    def _snap_target_screen_bbox(self, target: SnapTarget, ctx: Any) -> tuple[float, float, float, float] | None:
        padding = _snap_target_screen_padding(target)
        if target.is_circle:
            return _circle_screen_bbox(target, ctx, padding)
        if target.is_arc:
            return _arc_screen_bbox(target, ctx, padding)
        if target.is_segment and target.start is not None and target.end is not None:
            a = _world_to_screen(ctx, target.start)
            b = _world_to_screen(ctx, target.end)
            try:
                target.metadata.setdefault("snap_start_screen", a)
                target.metadata.setdefault("snap_end_screen", b)
                target.metadata.setdefault("snap_midpoint_screen", ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5))
            except Exception:
                pass
            return (
                min(a[0], b[0]) - padding,
                min(a[1], b[1]) - padding,
                max(a[0], b[0]) + padding,
                max(a[1], b[1]) + padding,
            )
        if target.screen_pos is not None:
            point = _point2(target.screen_pos)
        elif target.world_pos is not None:
            point = _world_to_screen(ctx, target.world_pos)
            try:
                target.metadata.setdefault("snap_screen_pos", point)
            except Exception:
                pass
        else:
            return None
        return (point[0] - padding, point[1] - padding, point[0] + padding, point[1] + padding)

    def _collect_sketch(self, ctx: Any, excluded: set[str]) -> None:
        sketch = getattr(ctx, "sketch", None)
        if sketch is None:
            return
        point_getter = getattr(sketch, "sketch_points_for_snap", None)
        if callable(point_getter):
            for point_id, position in point_getter():
                if str(point_id) not in excluded:
                    self._points.append(ScenePoint(str(point_id), _point3(position), SnapSource.SKETCH_POINT.value))
        segment_getter = getattr(sketch, "sketch_segments_for_snap", None)
        if callable(segment_getter):
            for segment_id, start, end in segment_getter():
                if str(segment_id) not in excluded:
                    self._segments.append(SceneSegment(str(segment_id), _point3(start), _point3(end), SnapSource.SKETCH_EDGE.value))

    def _collect_selection(self, ctx: Any, excluded: set[str]) -> None:
        selection = getattr(ctx, "selection", None)
        actors_getter = getattr(selection, "actors", None)
        if not callable(actors_getter):
            return
        for actor in actors_getter():
            if actor.id in excluded:
                continue
            metadata = {**actor.metadata, "owner_tool": actor.owner_tool} if actor.owner_tool is not None else dict(actor.metadata)
            points = tuple(_point3(point) for point in actor.points)
            kind = str(getattr(actor.kind, "value", actor.kind))
            if kind == "point" and points:
                self._points.append(ScenePoint(actor.id, points[0], SnapSource.TOOL_ACTOR_POINT.value, metadata))
            elif len(points) >= 2:
                for index, (start, end) in enumerate(zip(points, points[1:])):
                    self._segments.append(SceneSegment(f"{actor.id}:{index}", start, end, SnapSource.TOOL_ACTOR_EDGE.value, metadata))
                for index, position in enumerate(points):
                    self._points.append(ScenePoint(f"{actor.id}:point:{index}", position, SnapSource.TOOL_ACTOR_POINT.value, metadata))

    def _collect_document_meshes(self, ctx: Any, excluded: set[str]) -> None:
        """Collect snap vertices/edges from real scene/document meshes.

        Some application hosts do not expose ``ctx.scene.snap_points`` or
        ``ctx.scene.snap_segments`` even though the document contains visible
        WorkMesh parts.  Plan-tracing tools then snapped only to their own
        ToolActor points after the first cursor update.  This fallback turns the
        stable document facade (or owner mesh getters) into normal scene
        snap targets.
        """

        with _measure_perf(ctx, "scene_cache.mesh.collect_objects"):
            objects = list(self._document_objects_for_snap(ctx))
        _set_perf_value(ctx, "scene_cache.mesh.objects", len(objects))
        if not objects:
            return

        point_budget = max(0, int(MAX_MESH_SNAP_POINTS) - len(self._points))
        edge_budget = max(0, int(MAX_MESH_SNAP_EDGES) - len(self._segments))
        seen_points: set[tuple[int, int, int]] = set()
        seen_edges: set[tuple[tuple[int, int, int], tuple[int, int, int]]] = set()

        for obj_index, obj in enumerate(objects):
            mesh = getattr(obj, "mesh", obj)
            vertices = tuple(getattr(mesh, "vertices", ()) or ())
            triangles = tuple(getattr(mesh, "triangles", ()) or ())
            if not vertices:
                continue
            object_index = int(getattr(obj, "index", obj_index))
            object_id = str(getattr(obj, "id", "") or getattr(mesh, "mesh_id", "") or f"mesh:{object_index}")
            object_name = str(getattr(obj, "name", "") or getattr(mesh, "name", "") or object_id)
            if object_id in excluded or object_name in excluded:
                continue
            mesh_id = str(getattr(mesh, "mesh_id", object_id) or object_id)
            base_meta = {"object_id": object_id, "object_index": object_index, "mesh_id": mesh_id, "object_name": object_name}

            def point_key(position: Point3) -> tuple[int, int, int]:
                return (round(position[0] * 100000), round(position[1] * 100000), round(position[2] * 100000))

            def add_point(local_id: str, position: Iterable[float], *, force: bool = False) -> None:
                nonlocal point_budget
                if point_budget <= 0 and not force:
                    return
                try:
                    point = _point3(position)
                except Exception:
                    return
                key = point_key(point)
                if key in seen_points:
                    return
                seen_points.add(key)
                self._points.append(ScenePoint(local_id, point, SnapSource.MESH_VERTEX.value, dict(base_meta)))
                if not force:
                    point_budget -= 1

            def add_edge(local_id: str, start: Iterable[float], end: Iterable[float], *, force: bool = False) -> None:
                nonlocal edge_budget
                if edge_budget <= 0 and not force:
                    return
                try:
                    a = _point3(start)
                    b = _point3(end)
                except Exception:
                    return
                ka, kb = point_key(a), point_key(b)
                if ka == kb:
                    return
                edge_key = tuple(sorted((ka, kb)))  # type: ignore[assignment]
                if edge_key in seen_edges:
                    return
                seen_edges.add(edge_key)
                self._segments.append(SceneSegment(local_id, a, b, SnapSource.MESH_EDGE.value, dict(base_meta)))
                if not force:
                    edge_budget -= 1

            vertex_stride = max(1, int(len(vertices) / max(1, max(1, point_budget) // max(1, len(objects))))) if point_budget else max(1, len(vertices))
            for vertex_index, vertex in enumerate(vertices[::vertex_stride]):
                add_point(f"mesh:{object_index}:vertex:{vertex_index * vertex_stride}", vertex)

            tri_stride = max(1, int(len(triangles) / max(1, max(1, edge_budget) // max(1, len(objects) * 3)))) if edge_budget else max(1, len(triangles))
            for tri_index, tri in enumerate(triangles[::tri_stride]):
                try:
                    ia, ib, ic = int(tri[0]), int(tri[1]), int(tri[2])
                    if min(ia, ib, ic) < 0 or max(ia, ib, ic) >= len(vertices):
                        continue
                    prefix = f"mesh:{object_index}:tri:{tri_index * tri_stride}"
                    add_edge(f"{prefix}:ab", vertices[ia], vertices[ib])
                    add_edge(f"{prefix}:bc", vertices[ib], vertices[ic])
                    add_edge(f"{prefix}:ca", vertices[ic], vertices[ia])
                except Exception:
                    continue

            self._collect_mesh_bounds_for_snap(object_index, vertices, base_meta, add_point, add_edge)

        _set_perf_value(ctx, "scene_cache.mesh.remaining_point_budget", point_budget)
        _set_perf_value(ctx, "scene_cache.mesh.remaining_edge_budget", edge_budget)
        _set_perf_value(ctx, "scene_cache.mesh.sampled_unique_points", len(seen_points))
        _set_perf_value(ctx, "scene_cache.mesh.sampled_unique_edges", len(seen_edges))

    @staticmethod
    def _document_objects_for_snap(ctx: Any) -> tuple[Any, ...]:
        document = getattr(ctx, "document", None)
        objects_getter = getattr(document, "objects", None)
        if callable(objects_getter):
            try:
                ensure = getattr(document, "ensure", None)
                if callable(ensure):
                    ensure()
            except Exception:
                pass
            for kwargs in ({"include_preview": True}, {}):
                try:
                    objects = tuple(objects_getter(**kwargs))
                    if objects:
                        return objects
                except Exception:
                    continue

        owner = getattr(ctx, "owner", None)
        for getter_name in ("current_meshes", "committed_meshes"):
            getter = getattr(owner, getter_name, None)
            if callable(getter):
                try:
                    meshes = tuple(getter() or ())
                    if meshes:
                        return meshes
                except Exception:
                    continue
        project = getattr(owner, "project_store", None)
        scene = getattr(project, "active_scene", None) if project is not None else None
        for target in (scene, project, owner):
            if target is None:
                continue
            meshes = getattr(target, "meshes", None)
            if meshes:
                try:
                    return tuple(meshes)
                except Exception:
                    pass
            committed = getattr(target, "committed_meshes", None)
            if committed:
                try:
                    return tuple(committed)
                except Exception:
                    pass
        return ()

    def _collect_mesh_bounds_for_snap(self, object_index: int, vertices: tuple[Any, ...], base_meta: dict[str, Any], add_point: Any, add_edge: Any) -> None:
        try:
            points = [_point3(vertex) for vertex in vertices]
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            zs = [point[2] for point in points]
        except Exception:
            return
        minimum = (min(xs), min(ys), min(zs))
        maximum = (max(xs), max(ys), max(zs))
        self._bounds.append(SceneBounds(minimum, maximum))
        corners = [(x, y, z) for x in (minimum[0], maximum[0]) for y in (minimum[1], maximum[1]) for z in (minimum[2], maximum[2])]
        for corner_index, corner in enumerate(corners):
            add_point(f"mesh:{object_index}:bounds:{corner_index}", corner, force=True)
        for edge_index, (i, j) in enumerate(((0, 1), (0, 2), (0, 4), (3, 1), (3, 2), (3, 7), (5, 1), (5, 4), (5, 7), (6, 2), (6, 4), (6, 7))):
            add_edge(f"mesh:{object_index}:bounds_edge:{edge_index}", corners[i], corners[j], force=True)

    def _collect_scene(self, ctx: Any, excluded: set[str]) -> None:
        scene = getattr(ctx, "scene", None)
        if scene is None:
            return
        for name in ("snap_points", "points_for_snap"):
            getter = getattr(scene, name, None)
            if callable(getter):
                for point_id, position in getter():
                    if str(point_id) not in excluded:
                        self._points.append(ScenePoint(str(point_id), _point3(position), SnapSource.SCENE_POINT.value))
                break
        for name in ("snap_segments", "segments_for_snap"):
            getter = getattr(scene, name, None)
            if callable(getter):
                for segment_id, start, end in getter():
                    if str(segment_id) not in excluded:
                        self._segments.append(SceneSegment(str(segment_id), _point3(start), _point3(end), SnapSource.SCENE_EDGE.value))
                break
        bounds_getter = getattr(scene, "bounds_for_snap", None)
        if callable(bounds_getter):
            for minimum, maximum in bounds_getter():
                self._bounds.append(SceneBounds(_point3(minimum), _point3(maximum)))

    @staticmethod
    def _with_owner(target: SnapTarget, owner_tool: str) -> SnapTarget:
        return SnapTarget(
            id=target.id,
            source=target.source,
            world_pos=target.world_pos,
            screen_pos=target.screen_pos,
            start=target.start,
            end=target.end,
            control=target.control,
            center=target.center,
            radius=target.radius,
            basis_u=target.basis_u,
            basis_v=target.basis_v,
            radius_px=target.radius_px,
            priority=target.priority,
            metadata={**target.metadata, "owner_tool": owner_tool},
            kind=target.kind,
        )


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


def _point2(value: Iterable[float]) -> Point2:
    x, y = tuple(value)
    return (float(x), float(y))


def _world_to_screen_func(ctx: Any):
    viewport = getattr(ctx, "viewport", None)
    return getattr(viewport, "world_to_screen", None)




def _callable_cache_signature(callable_obj: Any) -> tuple[Any, ...]:
    """Return a stable identity for a projection callable.

    Bound method objects and some Qt/PyVista adapters may allocate a fresh Python
    wrapper every time the attribute is read.  Using ``id(callable_obj)`` in the
    projection cache key therefore turns every cursor move into a cache miss.
    Keep only semantic identity: receiver identity when available, otherwise the
    callable type/module/name.  Camera and viewport-size data below still decide
    when the screen projection really changed.
    """

    if callable_obj is None:
        return ("none",)
    receiver = getattr(callable_obj, "__self__", None)
    func = getattr(callable_obj, "__func__", None)
    if receiver is not None and func is not None:
        return (
            "bound-method",
            id(receiver),
            type(receiver).__module__,
            type(receiver).__qualname__,
            getattr(func, "__module__", None),
            getattr(func, "__qualname__", getattr(func, "__name__", None)),
        )
    if receiver is not None:
        return ("callable-receiver", id(receiver), type(receiver).__module__, type(receiver).__qualname__)
    return (
        "callable",
        type(callable_obj).__module__,
        type(callable_obj).__qualname__,
        getattr(callable_obj, "__module__", None),
        getattr(callable_obj, "__qualname__", getattr(callable_obj, "__name__", None)),
    )

def projection_cache_signature(ctx: Any) -> tuple[Any, ...]:
    """Return a stable stamp for screen-space snap indices.

    Earlier builds projected arbitrary sentinel points and used those projected
    coordinates as the cache key. In the live PyVista/VTK viewport those values
    can jitter after actor updates even when the user did not pan/zoom, which
    made dense scene snap rebuild its screen grid on nearly every mouse move.

    This stamp tracks the real camera/window state instead. It changes when the
    camera, projection or viewport size changes, but stays stable while the Plan
    Tracer cursor and previews are merely moved.
    """

    viewport = getattr(ctx, "viewport", None)
    world_to_screen = getattr(viewport, "world_to_screen", None)
    signature: list[Any] = ["world_to_screen", _callable_cache_signature(world_to_screen)]

    owner = getattr(ctx, "owner", None)
    owner_plotter = getattr(owner, "plotter", None)
    viewport_plotter = getattr(viewport, "plotter", None)
    plotter = owner_plotter or viewport_plotter
    renderer = getattr(plotter, "renderer", None)
    camera = getattr(plotter, "camera", None) or getattr(renderer, "camera", None)
    _set_perf_value(ctx, "scene_cache.snap.projection.has_owner_plotter", int(owner_plotter is not None))
    _set_perf_value(ctx, "scene_cache.snap.projection.has_viewport_plotter", int(viewport_plotter is not None))
    _set_perf_value(ctx, "scene_cache.snap.projection.has_camera", int(camera is not None))

    def add_float(value: Any, digits: int = 6) -> None:
        try:
            signature.append(round(float(value), int(digits)))
        except Exception:
            signature.append(None)

    def add_vec(values: Any, digits: int = 6) -> None:
        try:
            for value in tuple(values):
                add_float(value, digits)
        except Exception:
            signature.append(None)

    if camera is not None:
        signature.append("camera")
        for name in ("GetPosition", "GetFocalPoint", "GetViewUp", "GetClippingRange"):
            getter = getattr(camera, name, None)
            add_vec(getter() if callable(getter) else (), 6)
        for name in ("GetParallelScale", "GetViewAngle", "GetParallelProjection"):
            getter = getattr(camera, name, None)
            if callable(getter):
                add_float(getter(), 6)
            else:
                signature.append(None)
    else:
        signature.append("no-camera")

    size = None
    try:
        size = tuple(getattr(plotter, "window_size"))
    except Exception:
        size = None
    if not size:
        render_window = getattr(plotter, "ren_win", None) or getattr(plotter, "render_window", None)
        get_size = getattr(render_window, "GetSize", None)
        if callable(get_size):
            try:
                size = tuple(get_size())
            except Exception:
                size = None
    if not size:
        try:
            size = (float(plotter.width()), float(plotter.height()))
        except Exception:
            try:
                size = (float(getattr(plotter, "width")), float(getattr(plotter, "height")))
            except Exception:
                size = None
    signature.append("size")
    add_vec(size or (), 3)

    # Some lightweight test adapters expose an explicit stamp; real viewports can
    # add this later without changing the cache API.
    for attr in ("camera_revision", "projection_revision", "view_revision"):
        value = getattr(viewport, attr, None)
        if value is not None:
            signature.append((attr, value))
    return tuple(signature)

def _world_to_screen(ctx: Any, point: Point3) -> Point2:
    world_to_screen = _world_to_screen_func(ctx)
    if callable(world_to_screen):
        try:
            projected = world_to_screen(point)
            return (float(projected[0]), float(projected[1]))
        except Exception:
            pass
    return (float(point[0]), float(point[1]))


def _snap_target_screen_padding(target: SnapTarget) -> float:
    metadata = dict(getattr(target, "metadata", {}) or {})
    values = [float(getattr(target, "radius_px", 14.0) or 14.0)]
    for key in ("midpoint_radius_px", "intersection_radius_px", "center_radius_px", "quadrant_radius_px", "angle_radius_px", "curve_radius_px"):
        try:
            values.append(float(metadata[key]))
        except Exception:
            pass
    return max(max(values), 1.0) + 2.0



def _bbox_from_screen_points(points: Iterable[Point2], padding: float) -> tuple[float, float, float, float] | None:
    pts = tuple((float(point[0]), float(point[1])) for point in points)
    if not pts:
        return None
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    pad = max(float(padding), 0.0)
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _circle_screen_bbox(target: SnapTarget, ctx: Any, padding: float) -> tuple[float, float, float, float] | None:
    if target.center is None or target.radius is None:
        return None
    try:
        center = _point3(target.center)
        radius = float(target.radius)
        if radius <= 0.0 or not math.isfinite(radius):
            return None
        basis_u = _normalize_vec3(target.basis_u or (1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        basis_v = _normalize_vec3(target.basis_v or (0.0, 1.0, 0.0), (0.0, 1.0, 0.0))
        sample_count = max(8, int(SNAP_CURVE_BBOX_SAMPLE_COUNT))
        projected: list[Point2] = []
        for index in range(sample_count):
            angle = 2.0 * math.pi * float(index) / float(sample_count)
            ca = math.cos(angle)
            sa = math.sin(angle)
            point = (
                center[0] + radius * (ca * basis_u[0] + sa * basis_v[0]),
                center[1] + radius * (ca * basis_u[1] + sa * basis_v[1]),
                center[2] + radius * (ca * basis_u[2] + sa * basis_v[2]),
            )
            projected.append(_world_to_screen(ctx, point))
        projected.append(_world_to_screen(ctx, center))
        return _bbox_from_screen_points(projected, padding)
    except Exception:
        return None


def _arc_screen_bbox(target: SnapTarget, ctx: Any, padding: float) -> tuple[float, float, float, float] | None:
    if target.start is None or target.end is None or target.control is None:
        return None
    try:
        from laserprog_studio.tool_core.geometry import arc_from_three_points, point3_to_xy

        start = _point3(target.start)
        end = _point3(target.end)
        control = _point3(target.control)
        arc = arc_from_three_points(point3_to_xy(start), point3_to_xy(end), point3_to_xy(control))
        sample_count = max(8, int(SNAP_CURVE_BBOX_SAMPLE_COUNT))
        projected: list[Point2] = []
        if arc is None:
            samples = (start, control, end)
        else:
            samples = tuple(
                (
                    arc.point_at(float(index) / float(sample_count - 1))[0],
                    arc.point_at(float(index) / float(sample_count - 1))[1],
                    start[2] + (end[2] - start[2]) * float(index) / float(sample_count - 1),
                )
                for index in range(sample_count)
            ) + (control,)
        for point in samples:
            projected.append(_world_to_screen(ctx, point))
        return _bbox_from_screen_points(projected, padding)
    except Exception:
        return None


def _normalize_vec3(value: Iterable[float], fallback: Point3) -> Point3:
    try:
        vec = _point3(value)
        length = math.sqrt(vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2])
        if length <= 1.0e-12 or not math.isfinite(length):
            return fallback
        return (vec[0] / length, vec[1] / length, vec[2] / length)
    except Exception:
        return fallback

def _snap_source_from_text(value: str, *, point: bool) -> SnapSource:
    normalized = value.lower()
    if normalized in {item.value for item in SnapSource}:
        source = SnapSource(normalized)
        if point and source in {SnapSource.SKETCH_EDGE, SnapSource.SCENE_EDGE, SnapSource.TOOL_ACTOR_EDGE, SnapSource.TOOL_TEMP_EDGE, SnapSource.UI_EDGE, SnapSource.CUSTOM_EDGE}:
            return {
                SnapSource.SKETCH_EDGE: SnapSource.SKETCH_POINT,
                SnapSource.SCENE_EDGE: SnapSource.SCENE_POINT,
                SnapSource.TOOL_ACTOR_EDGE: SnapSource.TOOL_ACTOR_POINT,
                SnapSource.TOOL_TEMP_EDGE: SnapSource.TOOL_TEMP_POINT,
                SnapSource.UI_EDGE: SnapSource.UI_POINT,
                SnapSource.CUSTOM_EDGE: SnapSource.CUSTOM_POINT,
            }[source]
        if not point and source in {SnapSource.SKETCH_POINT, SnapSource.SCENE_POINT, SnapSource.TOOL_ACTOR_POINT, SnapSource.TOOL_TEMP_POINT, SnapSource.UI_POINT, SnapSource.CUSTOM_POINT}:
            return {
                SnapSource.SKETCH_POINT: SnapSource.SKETCH_EDGE,
                SnapSource.SCENE_POINT: SnapSource.SCENE_EDGE,
                SnapSource.TOOL_ACTOR_POINT: SnapSource.TOOL_ACTOR_EDGE,
                SnapSource.TOOL_TEMP_POINT: SnapSource.TOOL_TEMP_EDGE,
                SnapSource.UI_POINT: SnapSource.UI_EDGE,
                SnapSource.CUSTOM_POINT: SnapSource.CUSTOM_EDGE,
            }[source]
        return source
    if normalized.startswith("sketch"):
        return SnapSource.SKETCH_POINT if point else SnapSource.SKETCH_EDGE
    if normalized.startswith("scene"):
        return SnapSource.SCENE_POINT if point else SnapSource.SCENE_EDGE
    if normalized.startswith("actor") or normalized.startswith("tool_actor"):
        return SnapSource.TOOL_ACTOR_POINT if point else SnapSource.TOOL_ACTOR_EDGE
    if normalized.startswith("tool") or normalized.startswith("temp"):
        return SnapSource.TOOL_TEMP_POINT if point else SnapSource.TOOL_TEMP_EDGE
    if normalized.startswith("ui"):
        return SnapSource.UI_POINT if point else SnapSource.UI_EDGE
    return SnapSource.CUSTOM_POINT if point else SnapSource.CUSTOM_EDGE



def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if not callable(increment):
        return
    try:
        increment(str(name), int(value))
    except Exception:
        pass


def _set_perf_value(ctx: Any, name: str, value: Any) -> None:
    profiler = getattr(ctx, "profiler", None)
    setter = getattr(profiler, "set_value", None)
    if not callable(setter):
        return
    try:
        setter(str(name), value)
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

__all__ = ["MAX_MESH_SNAP_EDGES", "MAX_MESH_SNAP_POINTS", "SceneBounds", "SceneCache", "SceneCacheScope", "SceneCacheSummary", "ScenePoint", "SceneSegment"]
