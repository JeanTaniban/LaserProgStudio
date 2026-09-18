"""Public Plan 2D snap and constraint helpers."""
from __future__ import annotations

from bisect import bisect_left
from contextlib import nullcontext
from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, radians, sin
from typing import Any, Iterable

from laserprog_studio.planar_tools import LockedPlaneSpec, clamp_world_point_to_plane, plane_to_world, world_to_plane
from laserprog_studio.tool_core.snap.types import SnapKind, SnapTarget, snap_label_for_kind
from laserprog_studio.tool_api.styles import InteractionVisualState, LineStyleId, PointStyleId

Point3 = tuple[float, float, float]
Point2 = tuple[float, float]


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))

@dataclass(frozen=True, slots=True)
class Plan2DSnapCursorStyle:
    """API-owned cursor style for one semantic snap kind."""

    point_style: str
    line_style: str = LineStyleId.PREVIEW.value
    visual_state: str = InteractionVisualState.AUTO.value
    base_radius_px: int = 12
    label: str = ""
    show_label: bool = False


PLAN_2D_SNAP_CURSOR_STYLES: dict[str, Plan2DSnapCursorStyle] = {
    SnapKind.FREE.value: Plan2DSnapCursorStyle(PointStyleId.DIAMOND.value, LineStyleId.PREVIEW.value, InteractionVisualState.FIXED.value, 9, "Free", False),
    SnapKind.VERTEX.value: Plan2DSnapCursorStyle(PointStyleId.TARGET.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 14, "Vertex", True),
    SnapKind.EDGE.value: Plan2DSnapCursorStyle(PointStyleId.SQUARE.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 12, "Edge", True),
    SnapKind.MIDPOINT.value: Plan2DSnapCursorStyle(PointStyleId.RING.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 13, "Midpoint", True),
    SnapKind.INTERSECTION.value: Plan2DSnapCursorStyle(PointStyleId.TRIAD.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 15, "Intersection", True),
    SnapKind.CENTER.value: Plan2DSnapCursorStyle(PointStyleId.TARGET.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 14, "Center", True),
    SnapKind.QUADRANT.value: Plan2DSnapCursorStyle(PointStyleId.AXIS.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 12, "Quadrant", True),
    SnapKind.ANGLE.value: Plan2DSnapCursorStyle(PointStyleId.CHEVRON.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 12, "Angle", True),
    SnapKind.GRID.value: Plan2DSnapCursorStyle(PointStyleId.AXIS.value, LineStyleId.CONSTRUCTION.value, InteractionVisualState.FIXED.value, 10, "Grid", True),
    SnapKind.PERPENDICULAR.value: Plan2DSnapCursorStyle(PointStyleId.CHEVRON.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 14, "Perpendicular", True),
    SnapKind.TANGENT.value: Plan2DSnapCursorStyle(PointStyleId.ARROW.value, LineStyleId.GUIDE.value, InteractionVisualState.HOVER.value, 14, "Tangent", True),
}


def snap_cursor_style_for_kind(kind: SnapKind | str | None) -> Plan2DSnapCursorStyle:
    raw = str(kind.value if isinstance(kind, SnapKind) else kind or SnapKind.FREE.value).strip().lower().replace("-", "_")
    return PLAN_2D_SNAP_CURSOR_STYLES.get(raw, PLAN_2D_SNAP_CURSOR_STYLES[SnapKind.FREE.value])

@dataclass(frozen=True, slots=True)
class Plan2DSnapResult:
    """Result of an API-owned smart-snap query on a locked 2D plane.

    ``source`` remains the low-level origin for saved event traces
    (``tool_temp_point``, ``mesh_edge``, ...). ``kind`` is the semantic snap type
    used by the API to choose cursor/overlay styles.  ``FREE`` is a valid result:
    it means the pointer was projected to the locked plane without a snap target.
    """

    world_pos: Point3
    snapped: bool
    source: str = "none"
    source_id: str | None = None
    kind: str = SnapKind.FREE.value
    label: str = "Free"


@dataclass(frozen=True, slots=True)
class Plan2DConstraintResult:
    """Result of an API-owned drawing constraint on a locked 2D plane.

    Constraints are intentionally separate from snap results.  A snap says what
    geometric target the pointer is attracted to; a constraint says how the tool
    restricted the free/snap candidate once an anchor exists, for example an
    angle step or a square rectangle.  Tool code consumes only ``world_pos`` and
    may show ``label`` in status/inspector UI.
    """

    world_pos: Point3
    applied: bool = False
    kind: str = "none"
    label: str = ""



@dataclass(frozen=True, slots=True)
class _Plan2DGuidePoint:
    u: float
    v: float
    world: Point3
    source: str
    source_id: str | None
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class _Plan2DGuideCache:
    points: tuple[_Plan2DGuidePoint, ...]
    by_u: tuple[tuple[float, int], ...]
    by_v: tuple[tuple[float, int], ...]

    @classmethod
    def build(cls, plane: LockedPlaneSpec, targets: Iterable[SnapTarget]) -> "_Plan2DGuideCache":
        points: list[_Plan2DGuidePoint] = []
        seen: set[tuple[int, int, str, str]] = set()

        def add(world: Point3 | None, target: SnapTarget, suffix: str = "") -> None:
            if world is None:
                return
            try:
                clamped = clamp_world_point_to_plane(plane, _point3(world))
                u, v = world_to_plane(plane, clamped)
                u = float(u)
                v = float(v)
            except Exception:
                return
            if not (isfinite(u) and isfinite(v)):
                return
            source = str(getattr(getattr(target, "source", None), "value", getattr(target, "source", "custom_point")))
            base_id = str(getattr(target, "id", ""))
            source_id = f"{base_id}{suffix}" if base_id else None
            key = (round(u * 100000), round(v * 100000), source, str(source_id))
            if key in seen:
                return
            seen.add(key)
            kind = str(getattr(getattr(target, "kind", None), "value", getattr(target, "kind", "")) or SnapKind.VERTEX.value)
            metadata = dict(getattr(target, "metadata", {}) or {})
            label = str(metadata.get("snap_label", metadata.get("label", "Align")) or "Align")
            points.append(_Plan2DGuidePoint(u=u, v=v, world=clamped, source=source, source_id=source_id, kind=kind, label=label))

        for target in targets or ():
            try:
                if getattr(target, "world_pos", None) is not None:
                    add(target.world_pos, target)
                if getattr(target, "start", None) is not None:
                    add(target.start, target, ":start")
                if getattr(target, "end", None) is not None:
                    add(target.end, target, ":end")
                if getattr(target, "control", None) is not None:
                    add(target.control, target, ":control")
                if getattr(target, "center", None) is not None:
                    add(target.center, target, ":center")
                if getattr(target, "start", None) is not None and getattr(target, "end", None) is not None:
                    a = _point3(target.start)
                    b = _point3(target.end)
                    add(((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5), target, ":midpoint")
            except Exception:
                continue
        return cls(
            points=tuple(points),
            by_u=tuple(sorted((point.u, index) for index, point in enumerate(points))),
            by_v=tuple(sorted((point.v, index) for index, point in enumerate(points))),
        )

    def nearest_u(self, value: float) -> _Plan2DGuidePoint | None:
        return self._nearest(self.by_u, float(value))

    def nearest_v(self, value: float) -> _Plan2DGuidePoint | None:
        return self._nearest(self.by_v, float(value))

    def _nearest(self, indexed: tuple[tuple[float, int], ...], value: float) -> _Plan2DGuidePoint | None:
        if not indexed:
            return None
        pos = bisect_left(indexed, (float(value), -1))
        best: tuple[float, int] | None = None
        for candidate_pos in (pos - 1, pos):
            if candidate_pos < 0 or candidate_pos >= len(indexed):
                continue
            coord, index = indexed[candidate_pos]
            distance = abs(float(coord) - float(value))
            if best is None or distance < best[0]:
                best = (distance, int(index))
        if best is None:
            return None
        try:
            return self.points[best[1]]
        except Exception:
            return None


def _plane_signature(plane: LockedPlaneSpec) -> tuple[float, ...]:
    values = (*plane.normal, *plane.u_axis, *plane.v_axis, float(plane.depth))
    return tuple(round(float(value), 6) for value in values)


_OBJECT_SCENE_SOURCE_VALUES = {"mesh_vertex", "mesh_edge", "scene_point", "scene_edge", "center"}


def _normalised_object_scope(
    allowed_object_ids: Iterable[str] = (),
    allowed_object_indices: Iterable[int] = (),
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    ids = tuple(sorted({str(value) for value in allowed_object_ids if str(value)}))
    indices: set[int] = set()
    for value in allowed_object_indices:
        try:
            indices.add(int(value))
        except Exception:
            continue
    return ids, tuple(sorted(indices))


def _source_value(target: SnapTarget) -> str:
    source = getattr(target, "source", "")
    return str(getattr(source, "value", source))


def _filter_targets_by_object_scope(
    targets: Iterable[SnapTarget],
    allowed_object_ids: tuple[str, ...],
    allowed_object_indices: tuple[int, ...],
) -> tuple[SnapTarget, ...]:
    if not allowed_object_ids and not allowed_object_indices:
        return tuple(targets)
    allowed_ids = set(allowed_object_ids)
    allowed_indices = set(int(value) for value in allowed_object_indices)
    return tuple(target for target in targets if _target_allowed_by_object_scope(target, allowed_ids, allowed_indices))


def _target_allowed_by_object_scope(target: SnapTarget, allowed_object_ids: set[str], allowed_object_indices: set[int]) -> bool:
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
    if _source_value(target) in _OBJECT_SCENE_SOURCE_VALUES:
        return False
    return True


def _scene_plan2d_guide_cache(ctx: Any, plane: LockedPlaneSpec, *, allowed_object_ids: Iterable[str] = (), allowed_object_indices: Iterable[int] = ()) -> _Plan2DGuideCache:
    scene_cache = getattr(ctx, "scene_cache", None)
    if scene_cache is None:
        _increment_perf(ctx, "plan2d.guide_cache.scene.no_scene_cache")
        return _Plan2DGuideCache.build(plane, ())
    signature_getter = getattr(scene_cache, "snap_structure_signature", None)
    structure_signature = signature_getter() if callable(signature_getter) else int(getattr(scene_cache, "version", 0) or 0)
    object_ids, object_indices = _normalised_object_scope(allowed_object_ids, allowed_object_indices)
    key = (structure_signature, _plane_signature(plane), object_ids, object_indices)
    if getattr(scene_cache, "_plan2d_guide_cache_key", None) == key:
        cache = getattr(scene_cache, "_plan2d_guide_cache", None)
        if isinstance(cache, _Plan2DGuideCache):
            _increment_perf(ctx, "plan2d.guide_cache.scene.hits")
            _set_perf_value(ctx, "plan2d.guide_cache.scene.points", len(cache.points))
            return cache
    _increment_perf(ctx, "plan2d.guide_cache.scene.misses")
    snap_targets = getattr(scene_cache, "snap_targets", None)
    with _measure_perf(ctx, "plan2d.guide_cache.scene.collect_targets"):
        targets = tuple(snap_targets()) if callable(snap_targets) else ()
        if object_ids or object_indices:
            before_targets = len(targets)
            targets = _filter_targets_by_object_scope(targets, object_ids, object_indices)
            _increment_perf(ctx, "plan2d.guide_cache.scene.object_scope.filtered", before_targets - len(targets))
    with _measure_perf(ctx, "plan2d.guide_cache.scene.build"):
        cache = _Plan2DGuideCache.build(plane, targets)
    _set_perf_value(ctx, "plan2d.guide_cache.scene.targets", len(targets))
    _set_perf_value(ctx, "plan2d.guide_cache.scene.points", len(cache.points))
    try:
        scene_cache._plan2d_guide_cache_key = key
        scene_cache._plan2d_guide_cache = cache
    except Exception:
        pass
    return cache


def _extra_plan2d_guide_cache(ctx: Any, plane: LockedPlaneSpec, targets: tuple[SnapTarget, ...]) -> _Plan2DGuideCache:
    """Return a compiled guide cache for per-tool alignment targets.

    Plan Tracer supplies a stable target tuple from its own compiled snap service.
    Rebuilding this guide cache on every mouse event would still re-project every
    sketch point/edge endpoint.  Cache by tuple identity + plane signature; when
    the sketch changes the service publishes a new tuple object and the cache is
    rebuilt once.
    """

    if not targets:
        _increment_perf(ctx, "plan2d.guide_cache.extra.empty")
        return _Plan2DGuideCache.build(plane, ())
    key = (id(targets), len(targets), _plane_signature(plane))
    store = getattr(ctx, "_plan2d_extra_guide_cache_store", None)
    if not isinstance(store, dict):
        store = {}
        try:
            setattr(ctx, "_plan2d_extra_guide_cache_store", store)
        except Exception:
            store = {}
    cached = store.get(key)
    if isinstance(cached, _Plan2DGuideCache):
        _increment_perf(ctx, "plan2d.guide_cache.extra.hits")
        _set_perf_value(ctx, "plan2d.guide_cache.extra.points", len(cached.points))
        return cached
    _increment_perf(ctx, "plan2d.guide_cache.extra.misses")
    with _measure_perf(ctx, "plan2d.guide_cache.extra.build"):
        cache = _Plan2DGuideCache.build(plane, targets)
    _set_perf_value(ctx, "plan2d.guide_cache.extra.targets", len(targets))
    _set_perf_value(ctx, "plan2d.guide_cache.extra.points", len(cache.points))
    # Keep only a few recent target tuples to avoid retaining old sketch states.
    if len(store) > 6:
        for old_key in tuple(store)[: max(0, len(store) - 3)]:
            store.pop(old_key, None)
    store[key] = cache
    return cache


def _screen_distance_for_world(ctx: Any, world: Point3, screen_pos: Point2) -> float:
    viewport = getattr(ctx, "viewport", None)
    world_to_screen = getattr(viewport, "world_to_screen", None)
    if callable(world_to_screen):
        try:
            projected = world_to_screen(world)
            return hypot(float(projected[0]) - float(screen_pos[0]), float(projected[1]) - float(screen_pos[1]))
        except Exception:
            pass
    return hypot(float(world[0]) - float(screen_pos[0]), float(world[1]) - float(screen_pos[1]))


_ALIGNMENT_RADIUS_CACHE: "dict[int, float]" = {}


def _alignment_radius_px(max_distance_px: float | None, extra_targets: Iterable[SnapTarget]) -> float:
    if max_distance_px is not None:
        try:
            return max(float(max_distance_px), 0.0)
        except Exception:
            pass
    # Hot path on mouse hover: ``extra_targets`` is the same tuple object on
    # repeated moves (Plan Tracer caches it), so memoising by tuple identity
    # keeps the per-target ``getattr/min/max`` work out of the snap loop.
    if isinstance(extra_targets, tuple):
        cache_key = id(extra_targets)
        cached = _ALIGNMENT_RADIUS_CACHE.get(cache_key)
        if cached is not None:
            return cached
        radius = 14.0
        for target in extra_targets:
            try:
                radius = max(radius, min(float(getattr(target, "radius_px", 14.0) or 14.0), 24.0))
            except Exception:
                continue
        if len(_ALIGNMENT_RADIUS_CACHE) > 16:
            _ALIGNMENT_RADIUS_CACHE.clear()
        _ALIGNMENT_RADIUS_CACHE[cache_key] = radius
        return radius
    radius = 14.0
    for target in extra_targets or ():
        try:
            radius = max(radius, min(float(getattr(target, "radius_px", 14.0) or 14.0), 24.0))
        except Exception:
            continue
    return radius


def _query_plan2d_alignment_guides(
    ctx: Any,
    *,
    plane: LockedPlaneSpec,
    candidate_world: Point3,
    screen_pos: Point2,
    extra_targets: tuple[SnapTarget, ...],
    max_distance_px: float | None,
    allowed_object_ids: Iterable[str] = (),
    allowed_object_indices: Iterable[int] = (),
) -> Plan2DSnapResult | None:
    with _measure_perf(ctx, "plan2d.smart_snap.alignment.project"):
        try:
            raw_u, raw_v = world_to_plane(plane, clamp_world_point_to_plane(plane, candidate_world))
            raw_u = float(raw_u)
            raw_v = float(raw_v)
        except Exception:
            return None
    with _measure_perf(ctx, "plan2d.smart_snap.alignment.scene_cache"):
        scene_cache = _scene_plan2d_guide_cache(ctx, plane, allowed_object_ids=allowed_object_ids, allowed_object_indices=allowed_object_indices)
    with _measure_perf(ctx, "plan2d.smart_snap.alignment.extra_cache"):
        extra_cache = _extra_plan2d_guide_cache(ctx, plane, extra_targets) if extra_targets else _Plan2DGuideCache.build(plane, ())
    with _measure_perf(ctx, "plan2d.smart_snap.alignment.radius"):
        radius_px = _alignment_radius_px(max_distance_px, extra_targets)
    candidates: list[tuple[float, Point3, str, str | None, str, str]] = []

    def add_axis(point: _Plan2DGuidePoint | None, *, axis: str) -> None:
        if point is None:
            return
        u = point.u if axis == "u" else raw_u
        v = point.v if axis == "v" else raw_v
        world = clamp_world_point_to_plane(plane, plane_to_world(plane, u, v))
        distance_px = _screen_distance_for_world(ctx, world, screen_pos)
        if distance_px <= radius_px:
            label = "Align U" if axis == "u" else "Align V"
            candidates.append((distance_px, world, point.source, point.source_id, SnapKind.PERPENDICULAR.value, label))

    with _measure_perf(ctx, "plan2d.smart_snap.alignment.nearest_axes"):
        for cache in (scene_cache, extra_cache):
            add_axis(cache.nearest_u(raw_u), axis="u")
            add_axis(cache.nearest_v(raw_v), axis="v")

    # When both axes are close, offer the intersection of the two best guides.
    with _measure_perf(ctx, "plan2d.smart_snap.alignment.intersection_candidate"):
        best_u = min((item for cache in (scene_cache, extra_cache) if (item := cache.nearest_u(raw_u)) is not None), key=lambda p: abs(p.u - raw_u), default=None)
        best_v = min((item for cache in (scene_cache, extra_cache) if (item := cache.nearest_v(raw_v)) is not None), key=lambda p: abs(p.v - raw_v), default=None)
        if best_u is not None and best_v is not None:
            world = clamp_world_point_to_plane(plane, plane_to_world(plane, best_u.u, best_v.v))
            distance_px = _screen_distance_for_world(ctx, world, screen_pos)
            if distance_px <= radius_px:
                candidates.append((max(0.0, distance_px - 0.5), world, best_u.source, best_u.source_id, SnapKind.INTERSECTION.value, "Align U+V"))

    _increment_perf(ctx, "plan2d.smart_snap.alignment_candidates", len(candidates))
    _set_perf_value(ctx, "plan2d.smart_snap.last_alignment_candidates", len(candidates))
    if not candidates:
        return None
    distance_px, world, source, source_id, kind, label = min(candidates, key=lambda item: item[0])
    return Plan2DSnapResult(world_pos=world, snapped=True, source=source, source_id=source_id, kind=kind, label=label)


def _plan_grid_snap_result(
    ctx: Any,
    *,
    plane: LockedPlaneSpec,
    candidate_world: Point3,
    screen_pos: Point2,
    max_distance_px: float | None,
) -> Plan2DSnapResult | None:
    """Snap to a construction grid expressed in the locked plane basis.

    The generic snap manager owns a world-XYZ grid.  Locked 2D tools need a
    different contract: the grid is in local U/V plane coordinates and must not
    grab a visually distant intersection.  Otherwise a persisted huge grid step
    such as 100000 mm can freeze Plan Tracer's cursor on the plane origin.
    """

    snap_manager = getattr(ctx, "snap", None)
    if not bool(getattr(snap_manager, "grid_enabled", False)):
        return None
    grid_provider = getattr(snap_manager, "grid_provider", None)
    if grid_provider is not None and not bool(getattr(grid_provider, "enabled", True)):
        return None
    try:
        grid_size = float(getattr(grid_provider, "grid_size", 1.0) if grid_provider is not None else 1.0)
    except Exception:
        return None
    if not isfinite(grid_size) or grid_size <= 0.0:
        return None
    try:
        candidate = clamp_world_point_to_plane(plane, candidate_world)
        u, v = world_to_plane(plane, candidate)
        snapped_world = clamp_world_point_to_plane(
            plane,
            plane_to_world(
                plane,
                round(float(u) / grid_size) * grid_size,
                round(float(v) / grid_size) * grid_size,
            ),
        )
    except Exception:
        return None

    # Grid snap is useful only when the nearest grid intersection is close to the
    # mouse in screen space.  A fixed radius protects the editor from polluted
    # persisted preferences while preserving normal small-grid snapping.
    radius_px = 18.0
    if max_distance_px is not None:
        try:
            radius_px = max(float(max_distance_px), 0.0)
        except Exception:
            radius_px = 18.0
    distance_px = _screen_distance_for_world(ctx, snapped_world, screen_pos)
    _set_perf_value(ctx, "plan2d.smart_snap.grid.distance_px", distance_px)
    if distance_px > radius_px:
        _increment_perf(ctx, "plan2d.smart_snap.grid.ignored_far")
        return None
    _increment_perf(ctx, "plan2d.smart_snap.grid.local_hits")
    return Plan2DSnapResult(
        world_pos=snapped_world,
        snapped=True,
        source="grid",
        source_id=None,
        kind=SnapKind.GRID.value,
        label="Grid",
    )

def constrain_angle_step_on_plan(
    plane: LockedPlaneSpec,
    anchor_world: Point3,
    candidate_world: Point3,
    *,
    angle_step_degrees: float = 45.0,
    min_distance: float = 1.0e-9,
) -> Plan2DConstraintResult:
    """Constrain ``candidate_world`` around ``anchor_world`` to an angle step.

    This is public API for sketch-like tools.  Tools should not hand-roll
    horizontal/vertical/45° math because every planar view has its own world
    basis.  The function works in the locked plane's local U/V coordinates, then
    maps the constrained point back to the same plane.
    """

    from laserprog_studio.planar_tools import world_to_plane

    step = abs(float(angle_step_degrees))
    if step <= 0.0 or step > 180.0:
        return Plan2DConstraintResult(clamp_world_point_to_plane(plane, candidate_world), applied=False)
    anchor = clamp_world_point_to_plane(plane, anchor_world)
    candidate = clamp_world_point_to_plane(plane, candidate_world)
    au, av = world_to_plane(plane, anchor)
    cu, cv = world_to_plane(plane, candidate)
    dx = float(cu) - float(au)
    dy = float(cv) - float(av)
    length = hypot(dx, dy)
    if length <= float(min_distance):
        return Plan2DConstraintResult(candidate, applied=False)
    step_rad = radians(step)
    angle = atan2(dy, dx)
    snapped_angle = round(angle / step_rad) * step_rad
    constrained = plane_to_world(plane, float(au) + cos(snapped_angle) * length, float(av) + sin(snapped_angle) * length)
    label = f"Angle {step:g}°" if step != 45.0 else "Angle 45°"
    return Plan2DConstraintResult(clamp_world_point_to_plane(plane, constrained), applied=True, kind="angle_step", label=label)


def constrain_square_from_corner_on_plan(
    plane: LockedPlaneSpec,
    anchor_world: Point3,
    candidate_world: Point3,
    *,
    min_size: float = 1.0e-9,
) -> Plan2DConstraintResult:
    """Constrain ``candidate_world`` to make an axis-aligned square from corner.

    The square is expressed in the locked plane's local U/V coordinates, so it is
    consistent across top/front/side drawing views.  The largest mouse delta is
    used as the side length; this matches common CAD/sketcher behaviour and keeps
    the pointer outside the square rather than unexpectedly shrinking it.
    """

    from laserprog_studio.planar_tools import world_to_plane

    anchor = clamp_world_point_to_plane(plane, anchor_world)
    candidate = clamp_world_point_to_plane(plane, candidate_world)
    au, av = world_to_plane(plane, anchor)
    cu, cv = world_to_plane(plane, candidate)
    dx = float(cu) - float(au)
    dy = float(cv) - float(av)
    size = max(abs(dx), abs(dy))
    if size <= float(min_size):
        return Plan2DConstraintResult(candidate, applied=False)
    sx = 1.0 if dx >= 0.0 else -1.0
    sy = 1.0 if dy >= 0.0 else -1.0
    constrained = plane_to_world(plane, float(au) + sx * size, float(av) + sy * size)
    return Plan2DConstraintResult(clamp_world_point_to_plane(plane, constrained), applied=True, kind="square", label="Square")


def smart_snap_on_plan(
    ctx: Any,
    *,
    owner_tool: str,
    plane: LockedPlaneSpec,
    candidate_world: Point3,
    screen_pos: Point2,
    exclude_ids: Iterable[str] = (),
    exclude_sources: Iterable[str] = (),
    allowed_sources: Iterable[str] = (),
    allowed_kinds: Iterable[str] = (),
    allowed_object_ids: Iterable[str] = (),
    allowed_object_indices: Iterable[int] = (),
    extra_targets: Iterable[SnapTarget] = (),
    extra_alignment_targets: Iterable[SnapTarget] = (),
    max_distance_px: float | None = None,
    rebuild_cache: bool | None = None,
) -> Plan2DSnapResult:
    """Run official smart snap and clamp the result to the locked plane.

    ``extra_targets`` lets a locked-plane tool provide its current construction
    points without forcing a full scene-cache rebuild on every cursor move.
    Scene meshes remain in the cache; live tool points are supplied per query.

    ``exclude_sources`` / ``allowed_sources`` / ``allowed_kinds`` let tools build
    safe snap profiles: for example Vent Generator allows real scene geometry
    and custom alignment guides while refusing its own route actors.
    """

    try:
        _increment_perf(ctx, "plan2d.smart_snap.calls")
        with _measure_perf(ctx, "plan2d.smart_snap.prepare_targets"):
            extra_targets_tuple = tuple(extra_targets)
            extra_alignment_targets_tuple = tuple(extra_alignment_targets) if extra_alignment_targets else extra_targets_tuple
        _increment_perf(ctx, "plan2d.smart_snap.extra_targets", len(extra_targets_tuple))
        _increment_perf(ctx, "plan2d.smart_snap.alignment_targets", len(extra_alignment_targets_tuple))
        with _measure_perf(ctx, "plan2d.smart_snap.total"):
            with _measure_perf(ctx, "plan2d.smart_snap.manager"):
                result = ctx.snap.smart(
                    clamp_world_point_to_plane(plane, candidate_world),
                    screen_pos,
                    ctx,
                    extra_targets=extra_targets_tuple,
                    exclude_ids=tuple(exclude_ids),
                    exclude_sources=tuple(exclude_sources),
                    allowed_sources=tuple(allowed_sources),
                    allowed_kinds=tuple(allowed_kinds),
                    allowed_object_ids=tuple(allowed_object_ids),
                    allowed_object_indices=tuple(allowed_object_indices),
                    max_distance_px=max_distance_px,
                    rebuild_cache=rebuild_cache,
                )
            source = str(getattr(getattr(result, "source", None), "value", getattr(result, "source", "none")))
            kind = str(getattr(getattr(result, "kind", None), "value", getattr(result, "kind", SnapKind.FREE.value)))
            manager_reported_grid = source == "grid" or kind == SnapKind.GRID.value
            world = clamp_world_point_to_plane(plane, _point3(result.position))
            snapped = bool(getattr(result, "snapped", False)) and not manager_reported_grid
            if manager_reported_grid:
                # The generic snap manager grid is a world-XYZ fallback.  For a
                # locked 2D tool this can clamp every pointer position back to
                # the face origin, especially after a bad persisted grid step.
                # Treat it as "no snap" here, then apply the official plane
                # local grid after alignment guides have had a chance to win.
                _increment_perf(ctx, "plan2d.smart_snap.grid.manager_ignored")
                world = clamp_world_point_to_plane(plane, candidate_world)
            snap_manager = getattr(ctx, "snap", None)
            if not snapped and bool(getattr(snap_manager, "smart_enabled", True)):
                with _measure_perf(ctx, "plan2d.smart_snap.alignment"):
                    alignment = _query_plan2d_alignment_guides(
                        ctx,
                        plane=plane,
                        candidate_world=candidate_world,
                        screen_pos=screen_pos,
                        extra_targets=extra_alignment_targets_tuple,
                        max_distance_px=max_distance_px,
                        allowed_object_ids=tuple(allowed_object_ids),
                        allowed_object_indices=tuple(allowed_object_indices),
                    )
                if alignment is not None:
                    _increment_perf(ctx, "plan2d.smart_snap.alignment_hits")
                    return alignment
            if not snapped:
                grid_result = _plan_grid_snap_result(
                    ctx,
                    plane=plane,
                    candidate_world=candidate_world,
                    screen_pos=screen_pos,
                    max_distance_px=max_distance_px,
                )
                if grid_result is not None:
                    return grid_result
            label = str(getattr(result, "label", "") or snap_label_for_kind(kind))
            if manager_reported_grid:
                kind = SnapKind.FREE.value
                label = snap_label_for_kind(kind)
                source = "none"
            return Plan2DSnapResult(
                world_pos=world,
                snapped=snapped,
                source=source,
                source_id=None if getattr(result, "source_id", None) is None else str(getattr(result, "source_id")),
                kind=kind,
                label=label,
            )
    except Exception:
        return Plan2DSnapResult(world_pos=clamp_world_point_to_plane(plane, candidate_world), snapped=False, kind=SnapKind.FREE.value, label="Free")


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


__all__ = [
    "PLAN_2D_SNAP_CURSOR_STYLES",
    "Plan2DConstraintResult",
    "Plan2DSnapCursorStyle",
    "Plan2DSnapResult",
    "constrain_angle_step_on_plan",
    "constrain_square_from_corner_on_plan",
    "smart_snap_on_plan",
    "snap_cursor_style_for_kind",
]
