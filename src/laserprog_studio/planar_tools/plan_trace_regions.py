# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import Vec2
from .plan_trace_elements import PlanTraceAddKind, sample_plan_trace_element
from .validation import dedupe_consecutive_points, distance2d


@dataclass(frozen=True, slots=True)
class PlanTraceRegion:
    """A closed 2D face found in a Plan tracer sketch."""

    points: tuple[Vec2, ...]
    source: str = "sketch"

    @property
    def area(self) -> float:
        return abs(_signed_area(self.points))


def _as_vec2(point: Any) -> Vec2 | None:
    try:
        return (float(point[0]), float(point[1]))
    except Exception:
        return None


def _signed_area(points: Iterable[Vec2]) -> float:
    pts = [(float(u), float(v)) for u, v in points]
    if len(pts) < 3:
        return 0.0
    area2 = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        area2 += x0 * y1 - x1 * y0
    return area2 * 0.5


def _clean_region(points: Iterable[Vec2], *, tolerance: float = 1e-6) -> tuple[Vec2, ...]:
    pts = dedupe_consecutive_points([(float(u), float(v)) for u, v in points])
    if len(pts) >= 2 and distance2d(pts[0], pts[-1]) <= float(tolerance):
        pts = pts[:-1]
    if len(pts) < 3 or abs(_signed_area(pts)) <= 1e-7:
        return ()
    return tuple(pts)


def _node_key(point: Vec2, *, tolerance: float) -> tuple[int, int]:
    scale = 1.0 / max(float(tolerance), 1e-9)
    return (round(float(point[0]) * scale), round(float(point[1]) * scale))


def _element_path(element: Any, *, samples: int) -> list[Vec2]:
    try:
        kind = element.kind if isinstance(element.kind, PlanTraceAddKind) else PlanTraceAddKind(str(element.kind))
    except Exception:
        kind = getattr(element, "kind", PlanTraceAddKind.LINE)
    pts = [_as_vec2(p) for p in (getattr(element, "points", []) or [])]
    clean = [p for p in pts if p is not None]
    if kind is PlanTraceAddKind.LINE and len(clean) >= 2:
        return [clean[0], clean[1]]
    if kind is PlanTraceAddKind.SEMICIRCLE and len(clean) >= 3:
        return sample_plan_trace_element(PlanTraceAddKind.SEMICIRCLE, clean[:3], samples=max(8, int(samples)))
    return []


def _canonical_cycle_key(nodes: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not nodes:
        return ()
    if nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    variants: list[tuple[tuple[int, int], ...]] = []
    for seq in (nodes, list(reversed(nodes))):
        for i in range(len(seq)):
            variants.append(tuple(seq[i:] + seq[:i]))
    return min(variants) if variants else ()


def _effective_join_tolerance(draft: Any, tolerance: float | None) -> float:
    """Return the practical endpoint-join tolerance for sketch faces.

    The old detector used a numerical epsilon, which was correct for exact
    polygons but unusable for a drawing tool: two line endpoints that look
    connected on screen can easily differ by a few tenths of a millimetre.
    Keep the tolerance bounded so unrelated nearby geometry is not merged.
    """

    if tolerance is not None:
        return max(float(tolerance), 1e-9)
    try:
        custom = float(getattr(draft, "join_tolerance", 0.0) or 0.0)
        if custom > 0.0:
            return max(custom, 1e-9)
    except Exception:
        pass
    return 0.35


def plan_trace_closed_regions(draft: Any, *, tolerance: float | None = None, samples: int = 48) -> list[PlanTraceRegion]:
    """Find closed 2D faces in the current Plan tracer draft.

    The base polygon remains supported.  Independent circles are direct faces.
    Lines and 3-point arcs are joined by snapped endpoints into simple cycles;
    ambiguous branched graphs are ignored rather than producing a surprising
    extrusion.
    """

    tolerance = _effective_join_tolerance(draft, tolerance)

    regions: list[PlanTraceRegion] = []
    try:
        if bool(getattr(draft, "closed", False)) and len(getattr(draft, "points", []) or []) >= 3:
            pts = draft.sampled_boundary_points(samples_per_segment=max(8, int(samples)), include_closure=False)
            clean = _clean_region(pts, tolerance=tolerance)
            if clean:
                regions.append(PlanTraceRegion(clean, source="polygon"))
    except Exception:
        pass

    graph: dict[tuple[int, int], list[tuple[tuple[int, int], int, bool]]] = {}
    paths: list[list[Vec2]] = []
    node_refs: list[Vec2] = []

    def node_key(point: Vec2) -> tuple[int, int]:
        p = (float(point[0]), float(point[1]))
        for idx, ref in enumerate(node_refs):
            if distance2d(p, ref) <= float(tolerance):
                return (idx, 0)
        node_refs.append(p)
        return (len(node_refs) - 1, 0)

    for element in getattr(draft, "elements", []) or []:
        try:
            kind = element.kind if isinstance(element.kind, PlanTraceAddKind) else PlanTraceAddKind(str(element.kind))
        except Exception:
            continue
        if kind is PlanTraceAddKind.CIRCLE:
            pts = sample_plan_trace_element(kind, getattr(element, "points", []) or [], samples=max(24, int(samples)))
            clean = _clean_region(pts, tolerance=tolerance)
            if clean:
                regions.append(PlanTraceRegion(clean, source="circle"))
            continue
        path = _element_path(element, samples=max(8, int(samples)))
        path = dedupe_consecutive_points(path)
        if len(path) < 2:
            continue
        start = node_key(path[0])
        end = node_key(path[-1])
        if start == end:
            clean = _clean_region(path, tolerance=tolerance)
            if clean:
                regions.append(PlanTraceRegion(clean, source="closed_element"))
            continue
        edge_index = len(paths)
        paths.append(path)
        graph.setdefault(start, []).append((end, edge_index, False))
        graph.setdefault(end, []).append((start, edge_index, True))

    used_edges: set[int] = set()
    seen_cycles: set[tuple[tuple[int, int], ...]] = set()
    for start_node in list(graph):
        for next_node, edge_index, reversed_path in list(graph.get(start_node, [])):
            if edge_index in used_edges:
                continue
            cycle_nodes = [start_node]
            cycle_points: list[Vec2] = []
            current = start_node
            prev_edge: int | None = None
            first = True
            guard = 0
            while guard < max(len(paths) + 2, 4):
                guard += 1
                candidates = [entry for entry in graph.get(current, []) if entry[1] != prev_edge]
                if first:
                    candidates = [(next_node, edge_index, reversed_path)]
                if not candidates:
                    break
                # Simple sketch loops have degree 2.  If the node branches, pick
                # the unused continuation only if it is unique; otherwise skip the
                # ambiguous zone for safety.
                unused = [entry for entry in candidates if entry[1] not in used_edges or entry[1] == edge_index]
                if not unused:
                    break
                if not first and len(unused) > 1:
                    break
                nxt, eidx, rev = unused[0]
                path = list(reversed(paths[eidx])) if rev else list(paths[eidx])
                if cycle_points:
                    cycle_points.extend(path[1:])
                else:
                    cycle_points.extend(path)
                cycle_nodes.append(nxt)
                prev_edge = eidx
                current = nxt
                first = False
                if current == start_node:
                    key = _canonical_cycle_key(cycle_nodes)
                    clean = _clean_region(cycle_points, tolerance=tolerance)
                    if clean and key and key not in seen_cycles:
                        seen_cycles.add(key)
                        regions.append(PlanTraceRegion(clean, source="joined"))
                        for node_a, node_b, idx in _cycle_edges_from_nodes(cycle_nodes, graph):
                            used_edges.add(idx)
                    break

    # Largest/earliest regions first gives stable preview and apply behavior.
    return [r for r in sorted(regions, key=lambda r: (-r.area, r.source)) if r.area > 1e-7]


def _cycle_edges_from_nodes(nodes: list[tuple[int, int]], graph: dict[tuple[int, int], list[tuple[tuple[int, int], int, bool]]]):
    if len(nodes) < 2:
        return []
    out = []
    for a, b in zip(nodes, nodes[1:]):
        for nxt, idx, _rev in graph.get(a, []):
            if nxt == b:
                out.append((a, b, idx))
                break
    return out
