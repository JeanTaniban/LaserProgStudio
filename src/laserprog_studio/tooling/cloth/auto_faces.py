"""Reliable automatic closed-loop discovery for Cloth drawing.

A topological cycle is not necessarily a usable face: curved edges may cross,
several routes may connect the same endpoints, and the shortest *length* route
is not always the intended panel.  This solver enumerates a small set of simple
candidate paths, validates their sampled geometry, and only commits a face when
one candidate is unambiguous.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Iterable

from .face_geometry import analyze_curve_loop
from .models import ClothCurveKind, ClothCurveRole, ClothDocument
from .topology import curve_endpoint_ids, curve_patch_incidence, order_curve_loop, sample_curve


@dataclass(frozen=True, slots=True)
class ClothAutoFaceLoop:
    curve_ids: tuple[str, ...]
    trigger_curve_id: str


@dataclass(frozen=True, slots=True)
class ClothAutoFacePlan:
    loops: tuple[ClothAutoFaceLoop, ...] = ()
    message: str = ""

    @property
    def found(self) -> bool:
        return bool(self.loops)


def discover_auto_face_loops(document: ClothDocument, new_curve_ids: Iterable[str]) -> ClothAutoFacePlan:
    """Find safe newly closed loops involving the committed curves.

    The smallest valid geometric region is preferred, but only when it is
    clearly smaller than alternative valid regions.  Otherwise automatic face
    creation stops and asks the user to choose the intended curves in Face
    mode.  This is much safer than silently filling the wrong side of two arcs.
    """

    triggers = tuple(dict.fromkeys(str(value) for value in new_curve_ids if str(value) in document.curves))
    if not triggers:
        return ClothAutoFacePlan()

    incidence = curve_patch_incidence(document)
    existing_boundaries = {frozenset(patch.outer_curve_ids) for patch in document.patches.values()}
    emitted: set[frozenset[str]] = set()
    loops: list[ClothAutoFaceLoop] = []
    messages: list[str] = []

    for trigger_id in triggers:
        trigger = document.curves.get(trigger_id)
        if trigger is None or trigger.role not in {ClothCurveRole.BOUNDARY, ClothCurveRole.SEAM}:
            continue
        start_id, end_id = curve_endpoint_ids(trigger)
        if not start_id or not end_id or start_id == end_id:
            continue

        candidates: list[tuple[float, float, tuple[str, ...]]] = []
        rejected_reasons: list[str] = []
        seen_candidates: set[frozenset[str]] = set()
        for path, path_length in _candidate_boundary_paths(
            document,
            start_id,
            end_id,
            exclude_curve_id=trigger_id,
            incidence=incidence,
        ):
            cycle = tuple((*path, trigger_id))
            boundary = frozenset(cycle)
            if boundary in existing_boundaries or boundary in emitted or boundary in seen_candidates:
                continue
            seen_candidates.add(boundary)
            # Reusing one edge creates an adjacent panel. Reusing two or more
            # usually cuts across an existing panel and remains an explicit Face
            # operation.
            used_edges = sum(1 for curve_id in cycle if len(incidence.get(curve_id, ())) == 1)
            if used_edges > 1 or order_curve_loop(document, cycle) is None:
                continue
            all_straight = all(
                document.curves[curve_id].kind is ClothCurveKind.LINE
                for curve_id in cycle
                if curve_id in document.curves
            )
            analysis = analyze_curve_loop(
                document,
                cycle,
                planarity_tolerance_mm=float("inf") if all_straight else 0.05,
            )
            if not analysis.valid:
                if analysis.reason:
                    rejected_reasons.append(analysis.reason)
                continue
            trigger_length = _curve_length(document, trigger_id)
            candidates.append((analysis.area, path_length + trigger_length, cycle))

        if not candidates:
            if rejected_reasons:
                messages.append(rejected_reasons[0])
            continue
        candidates.sort(key=lambda item: (item[0], item[1], len(item[2]), item[2]))
        chosen = candidates[0]
        if len(candidates) > 1:
            first_area = max(chosen[0], 1.0e-12)
            second_area = candidates[1][0]
            # A 35% area margin is intentionally conservative. When two regions
            # are comparable, the user's intent is genuinely ambiguous.
            if second_area / first_area < 1.35:
                messages.append(
                    "Several valid Cloth faces are possible around the new curve. Use Face mode and select the intended arc/edge loop."
                )
                continue
        boundary = frozenset(chosen[2])
        emitted.add(boundary)
        loops.append(ClothAutoFaceLoop(chosen[2], trigger_id))

    return ClothAutoFacePlan(tuple(loops), " ".join(dict.fromkeys(messages)))


def _candidate_boundary_paths(
    document: ClothDocument,
    start_id: str,
    end_id: str,
    *,
    exclude_curve_id: str,
    incidence: dict[str, tuple[str, ...]],
    max_paths: int = 16,
    max_edges: int = 64,
    max_expansions: int = 4096,
    max_queue_size: int = 8192,
) -> tuple[tuple[tuple[str, ...], float], ...]:
    adjacency: dict[str, list[tuple[str, str, float]]] = {}
    for curve in document.curves.values():
        if curve.id == exclude_curve_id:
            continue
        if curve.role not in {ClothCurveRole.BOUNDARY, ClothCurveRole.SEAM}:
            continue
        if len(incidence.get(curve.id, ())) >= 2:
            continue
        first_id, second_id = curve_endpoint_ids(curve)
        if not first_id or not second_id or first_id == second_id:
            continue
        length = _curve_length(document, curve.id)
        adjacency.setdefault(first_id, []).append((second_id, curve.id, length))
        adjacency.setdefault(second_id, []).append((first_id, curve.id, length))
    for values in adjacency.values():
        values.sort(key=lambda item: (item[2], item[1], item[0]))

    queue: list[tuple[float, int, str, tuple[str, ...], frozenset[str], frozenset[str]]] = [
        (0.0, 0, start_id, (), frozenset({start_id}), frozenset())
    ]
    results: list[tuple[tuple[str, ...], float]] = []
    expansions = 0
    while queue and len(results) < max_paths and expansions < max(1, int(max_expansions)):
        distance, edge_count, point_id, path, visited_points, visited_curves = heapq.heappop(queue)
        expansions += 1
        if point_id == end_id and path:
            results.append((path, distance))
            continue
        if edge_count >= max_edges:
            continue
        for next_id, curve_id, length in adjacency.get(point_id, ()):
            if curve_id in visited_curves:
                continue
            if next_id in visited_points and next_id != end_id:
                continue
            if len(queue) >= max(1, int(max_queue_size)):
                continue
            heapq.heappush(
                queue,
                (
                    distance + max(length, 1.0e-9),
                    edge_count + 1,
                    next_id,
                    (*path, curve_id),
                    visited_points | {next_id},
                    visited_curves | {curve_id},
                ),
            )
    return tuple(results)


def _curve_length(document: ClothDocument, curve_id: str) -> float:
    points = sample_curve(document, curve_id, arc_segments=16)
    total = 0.0
    for index in range(1, len(points)):
        a, b = points[index - 1], points[index]
        total += ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5
    return total


__all__ = ["ClothAutoFaceLoop", "ClothAutoFacePlan", "discover_auto_face_loops"]
