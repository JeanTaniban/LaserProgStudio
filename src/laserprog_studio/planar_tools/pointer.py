# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Iterable

from .contracts import LockedPlaneSpec, PlanarToolConfig, Vec2, Vec3
from .orientation import plane_to_world, world_to_plane


@dataclass(frozen=True, slots=True)
class PlanarRay:
    """World-space ray emitted from a screen position."""

    origin: Vec3
    direction: Vec3


@dataclass(frozen=True, slots=True)
class PlanarPointerResult:
    """Resolved pointer position on a locked drawing plane.

    ``raw_*`` is the exact ray/plane intersection. ``snapped_*`` applies the
    current planar snap contract. Future tools can use ``raw`` while dragging and
    ``snapped`` when committing, or use snapped everywhere for grid-first workflows.
    """

    screen: tuple[float, float]
    raw_world: Vec3
    raw_plane: Vec2
    snapped_world: Vec3
    snapped_plane: Vec2
    snap_label: str | None = None


def dot(a: Vec3, b: Vec3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def add(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def scale(v: Vec3, k: float) -> Vec3:
    return (float(v[0]) * float(k), float(v[1]) * float(k), float(v[2]) * float(k))


def norm(v: Vec3) -> float:
    return math.sqrt(max(dot(v, v), 0.0))


def unit(v: Vec3, fallback: Vec3 = (0.0, 0.0, -1.0)) -> Vec3:
    n = norm(v)
    if not math.isfinite(n) or n <= 1e-12:
        return fallback
    return (float(v[0]) / n, float(v[1]) / n, float(v[2]) / n)


def make_ray(origin: Vec3, target: Vec3) -> PlanarRay:
    return PlanarRay(tuple(float(v) for v in origin), unit(sub(target, origin)))


def intersect_ray_with_locked_plane(ray: PlanarRay, plane: LockedPlaneSpec, *, epsilon: float = 1e-9) -> Vec3 | None:
    """Return the intersection of a world ray with a locked plane.

    The plane equation is ``dot(point, plane.normal) == plane.depth``.  ``None``
    means the ray is parallel to the plane or the intersection is behind the ray.
    """

    denom = dot(ray.direction, plane.normal)
    if abs(denom) <= float(epsilon):
        return None
    t = (float(plane.depth) - dot(ray.origin, plane.normal)) / denom
    if not math.isfinite(t) or t < 0.0:
        return None
    return add(ray.origin, scale(ray.direction, t))



@dataclass(frozen=True, slots=True)
class _CompiledSegment2D:
    a: Vec2
    b: Vec2
    vx: float
    vy: float
    length2: float
    min_u: float
    max_u: float
    min_v: float
    max_v: float


@dataclass(frozen=True, slots=True)
class _CompiledEdgeGrid2D:
    origin_u: float
    origin_v: float
    cell_size: float
    cells: dict[tuple[int, int], tuple[int, ...]]
    fallback_indices: tuple[int, ...] = ()

    def query_indices(self, u: float, v: float, tolerance: float) -> tuple[int, ...]:
        cell = max(float(self.cell_size), 1e-9)
        tol = max(float(tolerance), 0.0)
        min_cu = math.floor((float(u) - tol - float(self.origin_u)) / cell)
        max_cu = math.floor((float(u) + tol - float(self.origin_u)) / cell)
        min_cv = math.floor((float(v) - tol - float(self.origin_v)) / cell)
        max_cv = math.floor((float(v) + tol - float(self.origin_v)) / cell)
        out: set[int] = set(int(i) for i in self.fallback_indices)
        for cu in range(int(min_cu), int(max_cu) + 1):
            for cv in range(int(min_cv), int(max_cv) + 1):
                out.update(int(i) for i in self.cells.get((cu, cv), ()))
        return tuple(sorted(out))


def _build_edge_grid(edges: tuple[_CompiledSegment2D, ...]) -> _CompiledEdgeGrid2D | None:
    if not edges:
        return None
    min_u = min(edge.min_u for edge in edges)
    max_u = max(edge.max_u for edge in edges)
    min_v = min(edge.min_v for edge in edges)
    max_v = max(edge.max_v for edge in edges)
    extent = max(float(max_u) - float(min_u), float(max_v) - float(min_v), 1.0)
    # This is a compiled plane-space acceleration cache, not a screen locality
    # snap rule.  Long edges that cross too many cells are preserved in fallback,
    # so distant U/V guide behaviour remains unchanged.
    cell_size = max(extent / 72.0, 1.0)
    mutable_cells: dict[tuple[int, int], list[int]] = {}
    fallback: list[int] = []
    max_cells_per_edge = 768
    for index, edge in enumerate(edges):
        min_cu = math.floor((edge.min_u - min_u) / cell_size)
        max_cu = math.floor((edge.max_u - min_u) / cell_size)
        min_cv = math.floor((edge.min_v - min_v) / cell_size)
        max_cv = math.floor((edge.max_v - min_v) / cell_size)
        cell_count = (int(max_cu) - int(min_cu) + 1) * (int(max_cv) - int(min_cv) + 1)
        if cell_count <= 0 or cell_count > max_cells_per_edge:
            fallback.append(int(index))
            continue
        for cu in range(int(min_cu), int(max_cu) + 1):
            for cv in range(int(min_cv), int(max_cv) + 1):
                mutable_cells.setdefault((cu, cv), []).append(int(index))
    cells = {key: tuple(values) for key, values in mutable_cells.items()}
    return _CompiledEdgeGrid2D(float(min_u), float(min_v), float(cell_size), cells, tuple(fallback))


@dataclass(frozen=True, slots=True)
class CompiledPlanarSnapCache:
    """Precomputed plane-space guide cache for high-frequency pointer moves.

    The cache deliberately keeps global U/V coordinate indexes.  A point can be
    far away on screen and still be a valid horizontal/vertical alignment guide;
    only exact point/edge-body hits are filtered locally.  That avoids the
    previous screen-neighbourhood optimisation that made distant alignments
    disappear in dense scenes.
    """

    anchors: tuple[Vec2, ...] = ()
    sorted_u: tuple[tuple[float, float, float], ...] = ()
    sorted_v: tuple[tuple[float, float, float], ...] = ()
    edges: tuple[_CompiledSegment2D, ...] = ()
    edge_grid: _CompiledEdgeGrid2D | None = None

    @classmethod
    def build(
        cls,
        anchor_points: Iterable[Vec2] = (),
        edge_segments: Iterable[tuple[Vec2, Vec2]] = (),
    ) -> "CompiledPlanarSnapCache":
        anchors: list[Vec2] = []
        seen_points: set[tuple[int, int]] = set()
        for point in anchor_points or ():
            try:
                u = float(point[0])
                v = float(point[1])
            except Exception:
                continue
            if not (math.isfinite(u) and math.isfinite(v)):
                continue
            key = (round(u * 100000), round(v * 100000))
            if key in seen_points:
                continue
            seen_points.add(key)
            anchors.append((u, v))

        edges: list[_CompiledSegment2D] = []
        seen_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        for segment in edge_segments or ():
            try:
                a, b = segment
                ax, ay = float(a[0]), float(a[1])
                bx, by = float(b[0]), float(b[1])
            except Exception:
                continue
            if not all(math.isfinite(value) for value in (ax, ay, bx, by)):
                continue
            vx = bx - ax
            vy = by - ay
            length2 = vx * vx + vy * vy
            if length2 <= 1e-12:
                continue
            ka = (round(ax * 100000), round(ay * 100000))
            kb = (round(bx * 100000), round(by * 100000))
            key = tuple(sorted((ka, kb)))  # type: ignore[assignment]
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                _CompiledSegment2D(
                    a=(ax, ay),
                    b=(bx, by),
                    vx=vx,
                    vy=vy,
                    length2=length2,
                    min_u=min(ax, bx),
                    max_u=max(ax, bx),
                    min_v=min(ay, by),
                    max_v=max(ay, by),
                )
            )
        return cls(
            anchors=tuple(anchors),
            sorted_u=tuple(sorted((u, v, u) for u, v in anchors)),
            sorted_v=tuple(sorted((v, u, v) for u, v in anchors)),
            edges=tuple(edges),
            edge_grid=_build_edge_grid(tuple(edges)),
        )

    def nearest_point(self, u: float, v: float, tolerance: float) -> tuple[float, float, float] | None:
        tol = max(float(tolerance), 0.0)
        if tol <= 0.0 or not self.anchors:
            return None
        lo = bisect_left(self.sorted_u, (float(u) - tol, -math.inf, -math.inf))
        hi = bisect_right(self.sorted_u, (float(u) + tol, math.inf, math.inf))
        best: tuple[float, float, float] | None = None
        for au, av, _ in self.sorted_u[lo:hi]:
            if abs(float(av) - float(v)) > tol:
                continue
            d = math.hypot(float(au) - float(u), float(av) - float(v))
            if d <= tol and (best is None or d < best[0]):
                best = (d, float(au), float(av))
        return best

    def nearest_u(self, u: float, tolerance: float) -> tuple[float, float] | None:
        return _nearest_axis_coordinate(self.sorted_u, float(u), float(tolerance))

    def nearest_v(self, v: float, tolerance: float) -> tuple[float, float] | None:
        return _nearest_axis_coordinate(self.sorted_v, float(v), float(tolerance))

    def nearest_edge(self, u: float, v: float, tolerance: float) -> tuple[float, float, float] | None:
        tol = max(float(tolerance), 0.0)
        if tol <= 0.0 or not self.edges:
            return None
        best: tuple[float, float, float] | None = None
        if self.edge_grid is not None:
            edge_iterable = (self.edges[index] for index in self.edge_grid.query_indices(float(u), float(v), tol) if 0 <= int(index) < len(self.edges))
        else:
            edge_iterable = iter(self.edges)
        for edge in edge_iterable:
            # Cheap precomputed AABB reject.  Long segments still stay queryable
            # along their full length through the grid fallback.
            if float(u) < edge.min_u - tol or float(u) > edge.max_u + tol or float(v) < edge.min_v - tol or float(v) > edge.max_v + tol:
                continue
            hit = _nearest_point_on_compiled_segment((float(u), float(v)), edge)
            if hit is None:
                continue
            d = math.hypot(float(hit[0]) - float(u), float(hit[1]) - float(v))
            if d <= tol and (best is None or d < best[0]):
                best = (d, float(hit[0]), float(hit[1]))
        return best


def compile_planar_snap_cache(
    anchor_points: Iterable[Vec2] = (),
    edge_segments: Iterable[tuple[Vec2, Vec2]] = (),
) -> CompiledPlanarSnapCache:
    return CompiledPlanarSnapCache.build(anchor_points, edge_segments)


def _nearest_axis_coordinate(sorted_axis: tuple[tuple[float, float, float], ...], value: float, tolerance: float) -> tuple[float, float] | None:
    tol = max(float(tolerance), 0.0)
    if tol <= 0.0 or not sorted_axis:
        return None
    index = bisect_left(sorted_axis, (float(value), -math.inf, -math.inf))
    best: tuple[float, float] | None = None
    for candidate_index in (index - 1, index):
        if candidate_index < 0 or candidate_index >= len(sorted_axis):
            continue
        coord = float(sorted_axis[candidate_index][0])
        distance = abs(coord - float(value))
        if distance <= tol and (best is None or distance < best[0]):
            best = (distance, coord)
    return best


def _nearest_point_on_compiled_segment(point: Vec2, edge: _CompiledSegment2D) -> Vec2 | None:
    px, py = float(point[0]), float(point[1])
    ax, ay = edge.a
    t = ((px - ax) * edge.vx + (py - ay) * edge.vy) / edge.length2
    if t <= 1e-5 or t >= 1.0 - 1e-5:
        return None
    t = max(0.0, min(1.0, t))
    return (ax + edge.vx * t, ay + edge.vy * t)

def _nearest_point_on_segment_2d(point: Vec2, a: Vec2, b: Vec2) -> Vec2 | None:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 <= 1e-12 or not math.isfinite(length2):
        return None
    t = ((px - ax) * vx + (py - ay) * vy) / length2
    if t <= 1e-5 or t >= 1.0 - 1e-5:
        return None
    t = max(0.0, min(1.0, t))
    return (ax + vx * t, ay + vy * t)


def _snap_plane_point_grid_after_smart(
    point: Vec2,
    config: PlanarToolConfig,
    *,
    anchor_points: tuple[Vec2, ...] | list[Vec2] = (),
    edge_segments: tuple[tuple[Vec2, Vec2], ...] | list[tuple[Vec2, Vec2]] = (),
    compiled_cache: CompiledPlanarSnapCache | None = None,
) -> tuple[Vec2, str | None]:
    """Stable snap order: smart guides first, grid rounds last."""

    u = float(point[0])
    v = float(point[1])
    labels: list[str] = []

    if config.smart_snap_enabled and (anchor_points or edge_segments or compiled_cache is not None):
        tol = max(float(config.smart_snap_tolerance), 0.0)
        best_point: tuple[float, float, float] | None = compiled_cache.nearest_point(u, v, tol) if compiled_cache is not None else None
        best_u: tuple[float, float] | None = compiled_cache.nearest_u(u, tol) if compiled_cache is not None else None
        best_v: tuple[float, float] | None = compiled_cache.nearest_v(v, tol) if compiled_cache is not None else None
        for au, av in anchor_points:
            au = float(au)
            av = float(av)
            dist = math.hypot(au - u, av - v)
            if dist <= tol and (best_point is None or dist < best_point[0]):
                best_point = (dist, au, av)
            du = abs(au - u)
            dv = abs(av - v)
            if du <= tol and (best_u is None or du < best_u[0]):
                best_u = (du, au)
            if dv <= tol and (best_v is None or dv < best_v[0]):
                best_v = (dv, av)
        if best_point is not None:
            u = best_point[1]
            v = best_point[2]
            labels.append("smart point")
        else:
            best_edge: tuple[float, float, float] | None = compiled_cache.nearest_edge(u, v, tol) if compiled_cache is not None else None
            for a, b in edge_segments or ():
                try:
                    hit = _nearest_point_on_segment_2d((u, v), (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
                except Exception:
                    hit = None
                if hit is None:
                    continue
                d = math.hypot(float(hit[0]) - u, float(hit[1]) - v)
                if d <= tol and (best_edge is None or d < best_edge[0]):
                    best_edge = (d, float(hit[0]), float(hit[1]))
            if best_edge is not None:
                u = best_edge[1]
                v = best_edge[2]
                labels.append("smart edge")
            else:
                if best_u is not None:
                    u = best_u[1]
                    labels.append("smart U")
                if best_v is not None:
                    v = best_v[1]
                    labels.append("smart V")

    if config.grid_snap_enabled:
        step = max(float(config.grid_step), 1e-9)
        origin = getattr(config, "grid_origin", None) or (0.0, 0.0)
        ou, ov = float(origin[0]), float(origin[1])
        u = ou + round((u - ou) / step) * step
        v = ov + round((v - ov) / step) * step
        labels.append(f"grid {step:g}")

    return (float(u), float(v)), (" + ".join(labels) if labels else None)


def _snap_plane_point_smart_priority(
    point: Vec2,
    config: PlanarToolConfig,
    *,
    anchor_points: tuple[Vec2, ...] | list[Vec2] = (),
    edge_segments: tuple[tuple[Vec2, Vec2], ...] | list[tuple[Vec2, Vec2]] = (),
    compiled_cache: CompiledPlanarSnapCache | None = None,
) -> tuple[Vec2, str | None]:
    """Plan-tracer snap: smart endpoints/edges win; grid is fallback."""

    raw_u = float(point[0])
    raw_v = float(point[1])
    u = raw_u
    v = raw_v

    if config.smart_snap_enabled and (anchor_points or edge_segments or compiled_cache is not None):
        tol = max(float(config.smart_snap_tolerance), 0.0)
        best_point: tuple[float, float, float] | None = compiled_cache.nearest_point(raw_u, raw_v, tol) if compiled_cache is not None else None
        best_u: tuple[float, float] | None = compiled_cache.nearest_u(raw_u, tol) if compiled_cache is not None else None
        best_v: tuple[float, float] | None = compiled_cache.nearest_v(raw_v, tol) if compiled_cache is not None else None
        for au, av in anchor_points:
            au = float(au)
            av = float(av)
            dist = math.hypot(au - raw_u, av - raw_v)
            if dist <= tol and (best_point is None or dist < best_point[0]):
                best_point = (dist, au, av)
            du = abs(au - raw_u)
            dv = abs(av - raw_v)
            if du <= tol and (best_u is None or du < best_u[0]):
                best_u = (du, au)
            if dv <= tol and (best_v is None or dv < best_v[0]):
                best_v = (dv, av)
        if best_point is not None:
            return (float(best_point[1]), float(best_point[2])), "smart point"

        best_edge: tuple[float, float, float] | None = compiled_cache.nearest_edge(raw_u, raw_v, tol) if compiled_cache is not None else None
        for a, b in edge_segments or ():
            try:
                hit = _nearest_point_on_segment_2d((raw_u, raw_v), (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
            except Exception:
                hit = None
            if hit is None:
                continue
            d = math.hypot(float(hit[0]) - raw_u, float(hit[1]) - raw_v)
            if d <= tol and (best_edge is None or d < best_edge[0]):
                best_edge = (d, float(hit[0]), float(hit[1]))
        if best_edge is not None:
            return (float(best_edge[1]), float(best_edge[2])), "smart edge"

        labels: list[str] = []
        if best_u is not None:
            u = best_u[1]
            labels.append("smart U")
        if best_v is not None:
            v = best_v[1]
            labels.append("smart V")
        if labels:
            return (float(u), float(v)), " + ".join(labels)

    if config.grid_snap_enabled:
        step = max(float(config.grid_step), 1e-9)
        origin = getattr(config, "grid_origin", None) or (0.0, 0.0)
        ou, ov = float(origin[0]), float(origin[1])
        u = ou + round((raw_u - ou) / step) * step
        v = ov + round((raw_v - ov) / step) * step
        return (float(u), float(v)), f"grid {step:g}"

    return (float(raw_u), float(raw_v)), None


def snap_plane_point(
    point: Vec2,
    config: PlanarToolConfig | None = None,
    *,
    anchor_points: tuple[Vec2, ...] | list[Vec2] = (),
    edge_segments: tuple[tuple[Vec2, Vec2], ...] | list[tuple[Vec2, Vec2]] = (),
    compiled_cache: CompiledPlanarSnapCache | None = None,
) -> tuple[Vec2, str | None]:
    """Apply planar snap.

    Historical projects keep the contract where grid snapping rounds after
    smart alignment.  Plan tracer opts into ``smart_snap_priority`` so exact
    coincident endpoints are preserved when Smart snap and Grid snap are both on.
    """

    cfg = config or PlanarToolConfig()
    if bool(getattr(cfg, "smart_snap_priority", False)):
        return _snap_plane_point_smart_priority(point, cfg, anchor_points=anchor_points, edge_segments=edge_segments, compiled_cache=compiled_cache)
    return _snap_plane_point_grid_after_smart(point, cfg, anchor_points=anchor_points, edge_segments=edge_segments, compiled_cache=compiled_cache)


def resolve_pointer_on_plane(
    screen: tuple[float, float],
    ray: PlanarRay,
    plane: LockedPlaneSpec,
    config: PlanarToolConfig | None = None,
    *,
    anchor_points: tuple[Vec2, ...] | list[Vec2] = (),
    edge_segments: tuple[tuple[Vec2, Vec2], ...] | list[tuple[Vec2, Vec2]] = (),
    compiled_cache: CompiledPlanarSnapCache | None = None,
) -> PlanarPointerResult | None:
    raw_world = intersect_ray_with_locked_plane(ray, plane)
    if raw_world is None:
        return None
    raw_plane = world_to_plane(plane, raw_world)
    snapped_plane, label = snap_plane_point(raw_plane, config, anchor_points=anchor_points, edge_segments=edge_segments, compiled_cache=compiled_cache)
    snapped_world = plane_to_world(plane, snapped_plane[0], snapped_plane[1])
    return PlanarPointerResult(
        screen=(float(screen[0]), float(screen[1])),
        raw_world=raw_world,
        raw_plane=raw_plane,
        snapped_world=snapped_world,
        snapped_plane=snapped_plane,
        snap_label=label,
    )
