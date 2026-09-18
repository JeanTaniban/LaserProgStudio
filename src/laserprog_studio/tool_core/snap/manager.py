"""Shared snap manager with Smart snap and Grid snap switches."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any, Iterable

from .providers import GridSnapProvider, snap_targets_to_results
from .types import Point2, Point3, SnapProvider, SnapResult, SnapSource, SnapTarget

SMART_SOURCES = {
    SnapSource.SKETCH_POINT,
    SnapSource.SKETCH_EDGE,
    SnapSource.MESH_VERTEX,
    SnapSource.MESH_EDGE,
    SnapSource.SCENE_POINT,
    SnapSource.SCENE_EDGE,
    SnapSource.TOOL_ACTOR_POINT,
    SnapSource.TOOL_ACTOR_EDGE,
    SnapSource.TOOL_TEMP_POINT,
    SnapSource.TOOL_TEMP_EDGE,
    SnapSource.UI_POINT,
    SnapSource.UI_EDGE,
    SnapSource.CUSTOM_POINT,
    SnapSource.CUSTOM_EDGE,
    SnapSource.SKETCH_CURVE,
    SnapSource.SCENE_CURVE,
    SnapSource.TOOL_ACTOR_CURVE,
    SnapSource.TOOL_TEMP_CURVE,
    SnapSource.CUSTOM_CURVE,
    SnapSource.CENTER,
    SnapSource.INTERSECTION,
}


@dataclass(slots=True)
class SnapManager:
    smart_enabled: bool = True
    grid_enabled: bool = False
    providers: list[SnapProvider] = field(default_factory=list)
    grid_provider: GridSnapProvider = field(default_factory=GridSnapProvider)
    cache_rebuilds: int = 0

    def add_provider(self, provider: SnapProvider) -> None:
        self.providers.append(provider)

    def set_smart_snap(self, enabled: bool) -> None:
        self.smart_enabled = bool(enabled)

    def set_grid_snap(self, enabled: bool) -> None:
        self.grid_enabled = bool(enabled)

    def rebuild_cache(self, ctx: Any) -> None:
        self.cache_rebuilds += 1
        scene_cache = getattr(ctx, "scene_cache", None)
        rebuild = getattr(scene_cache, "rebuild", None)
        if callable(rebuild):
            rebuild(ctx, scope="snap")
        for provider in self.providers:
            provider.build_cache(ctx)
        self.grid_provider.build_cache(ctx)

    def smart(
        self,
        world_pos: Point3,
        screen_pos: Point2,
        ctx: Any | None = None,
        *,
        extra_targets: Iterable[SnapTarget] = (),
        extra_points: Iterable[tuple[str, Point3]] = (),
        extra_segments: Iterable[tuple[str, Point3, Point3]] = (),
        exclude_ids: Iterable[str] = (),
        exclude_sources: Iterable[SnapSource | str] = (),
        allowed_sources: Iterable[SnapSource | str] = (),
        allowed_kinds: Iterable[str] = (),
        allowed_object_ids: Iterable[str] = (),
        allowed_object_indices: Iterable[int] = (),
        max_distance_px: float | None = None,
        rebuild_cache: bool | None = None,
    ) -> SnapResult:
        """Creator-facing smart snap helper.

        It queries providers, the optional ``ctx.scene_cache`` and per-call
        extra targets. ``exclude_ids`` is applied as a query-time filter: it no
        longer forces a scene cache rebuild, so tools can exclude currently
        dragged actors on every mouse move without rebuilding the cache.

        ``rebuild_cache`` controls scene-cache freshness:

        - ``None``: rebuild only when the cache is invalid;
        - ``True``: force a rebuild;
        - ``False``: use the current cache exactly as-is.
        """

        context = ctx if ctx is not None else _NullSnapContext()
        scene_cache = getattr(context, "scene_cache", None)
        should_rebuild = bool(rebuild_cache)
        if rebuild_cache is None:
            should_rebuild = not bool(getattr(scene_cache, "valid", False))
        rebuild = getattr(scene_cache, "rebuild", None)
        if callable(rebuild) and should_rebuild:
            rebuild(context, scope="snap")

        targets = list(extra_targets)
        targets.extend(SnapTarget.point(point_id, point) for point_id, point in extra_points)
        targets.extend(SnapTarget.segment(segment_id, start, end) for segment_id, start, end in extra_segments)
        return self.query(
            world_pos,
            screen_pos,
            context,
            extra_targets=targets,
            exclude_ids=exclude_ids,
            exclude_sources=exclude_sources,
            allowed_sources=allowed_sources,
            allowed_kinds=allowed_kinds,
            allowed_object_ids=allowed_object_ids,
            allowed_object_indices=allowed_object_indices,
            max_distance_px=max_distance_px,
        )

    def query(
        self,
        world_pos: Point3,
        screen_pos: Point2,
        ctx: Any | None,
        *,
        extra_targets: Iterable[SnapTarget] = (),
        exclude_ids: Iterable[str] = (),
        exclude_sources: Iterable[SnapSource | str] = (),
        allowed_sources: Iterable[SnapSource | str] = (),
        allowed_kinds: Iterable[str] = (),
        allowed_object_ids: Iterable[str] = (),
        allowed_object_indices: Iterable[int] = (),
        max_distance_px: float | None = None,
    ) -> SnapResult:
        context = ctx if ctx is not None else _NullSnapContext()
        _increment_perf(context, "snap.manager.queries")
        excluded = tuple(str(value) for value in exclude_ids)
        excluded_sources = {_source_value(value) for value in exclude_sources}
        allowed_source_values = {_source_value(value) for value in allowed_sources}
        allowed_kind_values = {str(getattr(value, "value", value)).strip().lower().replace("-", "_") for value in allowed_kinds}
        allowed_object_id_values = {str(value) for value in allowed_object_ids if str(value)}
        allowed_object_index_values: set[int] = set()
        for value in allowed_object_indices:
            try:
                allowed_object_index_values.add(int(value))
            except Exception:
                continue
        object_scope_active = bool(allowed_object_id_values or allowed_object_index_values)
        candidates: list[SnapResult] = []
        if self.smart_enabled:
            with _measure_perf(context, "snap.manager.providers"):
                for provider in self.providers:
                    candidates.extend(provider.query(world_pos, screen_pos, context))
            scene_cache = getattr(context, "scene_cache", None)
            snap_targets_near = getattr(scene_cache, "snap_targets_near", None)
            snap_targets = getattr(scene_cache, "snap_targets", None)
            target_pool: list[SnapTarget] = []
            scene_targets: tuple[SnapTarget, ...] = ()
            if callable(snap_targets_near):
                scene_targets = tuple(snap_targets_near(screen_pos, context))
            elif callable(snap_targets):
                scene_targets = tuple(snap_targets())
            if object_scope_active:
                before_scene_targets = len(scene_targets)
                scene_targets = _filter_targets_by_object_scope(scene_targets, allowed_object_id_values, allowed_object_index_values)
                _increment_perf(context, "snap.manager.object_scope.filtered_scene_targets", before_scene_targets - len(scene_targets))
                _set_perf_value(context, "snap.manager.object_scope.scene_targets", len(scene_targets))
            target_pool.extend(scene_targets)
            target_pool.extend(tuple(extra_targets))
            _increment_perf(context, "snap.manager.target_pool", len(target_pool))
            # Convert all target-backed geometry in one pass.  This lets API-owned
            # semantic snaps such as INTERSECTION work between scene/cache targets
            # and live tool targets without pushing that complexity into tools.
            with _measure_perf(context, "snap.manager.targets_to_results"):
                candidates.extend(snap_targets_to_results(tuple(target_pool), world_pos, screen_pos, context))
        _increment_perf(context, "snap.manager.raw_candidates", len(candidates))
        candidates = [
            candidate
            for candidate in candidates
            if not _excluded(candidate, excluded, excluded_sources)
            and _allowed(candidate, allowed_source_values, allowed_kind_values)
            and _within_distance(candidate, max_distance_px)
        ]
        _increment_perf(context, "snap.manager.filtered_candidates", len(candidates))
        smart_candidates = [candidate for candidate in candidates if candidate.source in SMART_SOURCES]
        if smart_candidates:
            return min(smart_candidates, key=lambda c: (c.priority, c.distance_px))
        if self.grid_enabled:
            grid = [
                candidate
                for candidate in self.grid_provider.query(world_pos, screen_pos, context)
                if not _excluded(candidate, excluded, excluded_sources)
                and _allowed(candidate, allowed_source_values, allowed_kind_values)
                and _within_distance(candidate, max_distance_px)
            ]
            if grid:
                return grid[0]
        if candidates:
            return min(candidates, key=lambda c: (c.priority, c.distance_px))
        return SnapResult.none(world_pos)


_OBJECT_SCENE_SOURCE_VALUES = {
    SnapSource.MESH_VERTEX.value,
    SnapSource.MESH_EDGE.value,
    SnapSource.SCENE_POINT.value,
    SnapSource.SCENE_EDGE.value,
    SnapSource.CENTER.value,
}


def _filter_targets_by_object_scope(
    targets: Iterable[SnapTarget],
    allowed_object_ids: set[str],
    allowed_object_indices: set[int],
) -> tuple[SnapTarget, ...]:
    if not allowed_object_ids and not allowed_object_indices:
        return tuple(targets)
    return tuple(
        target
        for target in targets
        if _target_allowed_by_object_scope(target, allowed_object_ids, allowed_object_indices)
    )


def _target_allowed_by_object_scope(
    target: SnapTarget,
    allowed_object_ids: set[str],
    allowed_object_indices: set[int],
) -> bool:
    metadata = dict(getattr(target, "metadata", {}) or {})
    aliases = {
        str(value)
        for key in ("object_id", "mesh_id", "object_name", "source_object_id", "scene_object_id")
        if (value := metadata.get(key)) is not None and str(value)
    }
    for key in ("object_index", "mesh_index", "scene_object_index"):
        value = metadata.get(key)
        if value is None:
            continue
        try:
            if int(value) in allowed_object_indices:
                return True
        except Exception:
            pass
        aliases.add(str(value))
    if aliases:
        return bool(aliases.intersection(allowed_object_ids))
    source_value = _source_value(getattr(target, "source", ""))
    # If a target is clearly scene/object-backed but carries no object metadata,
    # it cannot be trusted in active-part-only mode. Tool/live sketch targets are
    # appended separately by the caller and are not rejected here unless they look
    # like scene geometry.
    if source_value in _OBJECT_SCENE_SOURCE_VALUES:
        return False
    return True


def _source_value(source: SnapSource | str) -> str:
    return source.value if isinstance(source, SnapSource) else str(source)


def _excluded(candidate: SnapResult, excluded_ids: tuple[str, ...], excluded_sources: set[str]) -> bool:
    if excluded_sources and candidate.source.value in excluded_sources:
        return True
    if not excluded_ids or candidate.source_id is None:
        return False
    source_id = str(candidate.source_id)
    return any(source_id == item or source_id.startswith(f"{item}:") for item in excluded_ids)


def _allowed(candidate: SnapResult, allowed_sources: set[str], allowed_kinds: set[str]) -> bool:
    if allowed_sources and candidate.source.value not in allowed_sources:
        return False
    kind = str(getattr(getattr(candidate, "kind", None), "value", getattr(candidate, "kind", ""))).strip().lower().replace("-", "_")
    if allowed_kinds and kind not in allowed_kinds:
        return False
    return True


def _within_distance(candidate: SnapResult, max_distance_px: float | None) -> bool:
    if max_distance_px is None:
        return True
    try:
        limit = float(max_distance_px)
    except Exception:
        return True
    if limit < 0.0:
        return True
    try:
        return float(candidate.distance_px) <= limit
    except Exception:
        return True


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
    set_value = getattr(profiler, "set_value", None)
    if not callable(set_value):
        return
    try:
        set_value(str(name), value)
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


class _NullViewport:
    @staticmethod
    def world_to_screen(pos: Point3) -> Point2:
        return (float(pos[0]), float(pos[1]))


class _NullSnapContext:
    viewport = _NullViewport()
