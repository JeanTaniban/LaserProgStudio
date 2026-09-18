"""Intelligent first-pass assistant for connecting existing Cloth panels.

The assistant intentionally produces deterministic, inspectable ruled-surface
proposals.  It does not silently mutate the document: analysis creates preview
rails, and acceptance materialises them through :class:`ClothDrawingController`.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Callable, Iterable, Sequence

from .drawing import ClothDrawingController, ClothDrawingOutcome
from .mesh_builder import build_cloth_surface_mesh
from .models import ClothDocument, Point3
from .solidification import cloth_stitch_tolerance_mm
from .topology import curve_endpoint_ids, sample_curve, sample_curve_loop_boundary, sample_patch_boundary

_EPS = 1.0e-9

ClosureCellValidator = Callable[[str, str, Point3, Point3, Point3, Point3], bool]


@dataclass(frozen=True, slots=True)
class ClothJoinPair:
    first_patch_id: str
    second_patch_id: str
    first_rail: tuple[Point3, ...]
    second_rail: tuple[Point3, ...]
    mean_width_mm: float
    max_width_mm: float
    twist_score: float
    coverage_first: float = 1.0
    coverage_second: float = 1.0
    strategy: str = "direct"

    @property
    def segment_count(self) -> int:
        return max(0, len(self.first_rail) - 1)

    @property
    def coverage(self) -> float:
        return max(0.0, min(1.0, min(self.coverage_first, self.coverage_second)))




@dataclass(frozen=True, slots=True)
class _ClosedBoundaryStrategy:
    id: str
    label: str
    pairs: tuple[ClothJoinPair, ...]
    coverage: float
    score: float

@dataclass(frozen=True, slots=True)
class ClothCloseCap:
    """One closed textile loop that can be filled as a new panel."""

    anchor_id: str
    boundary: tuple[Point3, ...]


@dataclass(frozen=True, slots=True)
class ClothJoinProposal:
    id: str
    patch_ids: tuple[str, ...]
    pairs: tuple[ClothJoinPair, ...]
    confidence: float
    score: float
    message: str
    curve_ids: tuple[str, ...] = ()
    caps: tuple[ClothCloseCap, ...] = ()

    @property
    def panel_count(self) -> int:
        return sum(pair.segment_count for pair in self.pairs) + len(self.caps)

    @property
    def triangle_preview(self) -> tuple[tuple[Point3, Point3, Point3], ...]:
        triangles: list[tuple[Point3, Point3, Point3]] = []
        for pair in self.pairs:
            for index in range(pair.segment_count):
                a0, a1 = pair.first_rail[index], pair.first_rail[index + 1]
                b0, b1 = pair.second_rail[index], pair.second_rail[index + 1]
                triangles.append((a0, a1, b1))
                triangles.append((a0, b1, b0))
        for cap in self.caps:
            triangles.extend(_triangulate_cap_preview(cap.boundary))
        return tuple(triangles)


def analyze_patch_join(
    document: ClothDocument,
    patch_ids: Iterable[str],
    *,
    minimum_samples: int = 8,
    maximum_samples: int = 72,
) -> tuple[ClothJoinProposal, ...]:
    """Return ranked connection proposals for two or more selected panels.

    Panels are connected with a minimum-spanning tree, avoiding the surprising
    all-to-all explosion that would otherwise occur with three or more faces.
    Closed boundaries are resampled, cyclically aligned and orientation-tested.
    """

    ids = tuple(dict.fromkeys(str(value) for value in patch_ids if str(value) in document.patches))
    if len(ids) < 2:
        return ()
    boundaries: dict[str, tuple[Point3, ...]] = {}
    for patch_id in ids:
        values = tuple(sample_patch_boundary(document, patch_id, arc_segments=24))
        if len(values) < 3:
            return ()
        boundaries[patch_id] = values

    candidate_pairs: list[tuple[float, ClothJoinPair]] = []
    for left_index, first_id in enumerate(ids):
        for second_id in ids[left_index + 1 :]:
            pair = _pair_boundaries(first_id, boundaries[first_id], second_id, boundaries[second_id], minimum_samples, maximum_samples)
            if pair is not None:
                candidate_pairs.append((_pair_cost(pair), pair))
    if not candidate_pairs:
        return ()

    candidate_pairs.sort(key=lambda item: (item[0], item[1].first_patch_id, item[1].second_patch_id))
    primary_pairs = _minimum_spanning_pairs(ids, candidate_pairs)
    if len(primary_pairs) != len(ids) - 1:
        return ()

    proposals: list[ClothJoinProposal] = []
    proposals.append(_proposal("join_direct", ids, primary_pairs, label="Direct logical connection"))

    # A second conservative alternative reverses every secondary rail.  It is
    # only kept when it produces a materially different and still plausible
    # surface, useful for nested or oppositely oriented source panels.
    reversed_pairs = tuple(
        ClothJoinPair(
            pair.first_patch_id,
            pair.second_patch_id,
            pair.first_rail,
            tuple(reversed(pair.second_rail)),
            pair.mean_width_mm,
            pair.max_width_mm,
            pair.twist_score,
        )
        for pair in primary_pairs
    )
    alternative = _proposal("join_reversed", ids, reversed_pairs, label="Reversed boundary correspondence")
    if abs(alternative.score - proposals[0].score) > 1.0e-6 and alternative.confidence >= 0.15:
        proposals.append(alternative)
    proposals.sort(key=lambda item: (-item.confidence, item.score, item.id))
    return tuple(proposals[:3])



def _patch_group_boundary_loops(
    document: ClothDocument,
    patch_ids: Iterable[str],
    *,
    arc_segments: int = 24,
) -> tuple[tuple[Point3, ...], ...]:
    """Return all external loops of one logical textile group, largest first.

    Curves shared by two technical patches cancel. Explicit hole loops are also
    included, which lets Close fill a hole from one selected logical face.
    """

    ids = tuple(dict.fromkeys(str(value) for value in patch_ids if str(value) in document.patches))
    if not ids:
        return ()
    counts: Counter[str] = Counter()
    for patch_id in ids:
        patch = document.patches[patch_id]
        counts.update(patch.outer_curve_ids)
        for loop in patch.hole_curve_loops:
            counts.update(loop)
    boundary_ids = tuple(curve_id for curve_id, count in counts.items() if count == 1 and curve_id in document.curves)
    if not boundary_ids:
        return ()

    point_to_curves: dict[str, set[str]] = defaultdict(set)
    for curve_id in boundary_ids:
        first, second = curve_endpoint_ids(document.curves[curve_id])
        if first:
            point_to_curves[first].add(curve_id)
        if second:
            point_to_curves[second].add(curve_id)
    remaining = set(boundary_ids)
    components: list[tuple[str, ...]] = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        component: set[str] = set()
        while stack:
            curve_id = stack.pop()
            if curve_id in component:
                continue
            component.add(curve_id)
            curve = document.curves[curve_id]
            for point_id in curve_endpoint_ids(curve):
                stack.extend(point_to_curves.get(point_id, ()))
        remaining.difference_update(component)
        components.append(tuple(sorted(component)))

    candidates: list[tuple[float, tuple[Point3, ...]]] = []
    for component in components:
        points = tuple(sample_curve_loop_boundary(document, component, arc_segments=arc_segments))
        if len(points) < 3:
            continue
        perimeter = sum(math.dist(points[index], points[(index + 1) % len(points)]) for index in range(len(points)))
        candidates.append((perimeter, points))
    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return tuple(points for _perimeter, points in candidates)


def _patch_group_boundary(
    document: ClothDocument,
    patch_ids: Iterable[str],
    *,
    arc_segments: int = 24,
) -> tuple[Point3, ...]:
    """Return the largest outer usable boundary of one logical group."""

    loops = _patch_group_boundary_loops(document, patch_ids, arc_segments=arc_segments)
    if loops:
        return loops[0]
    # Conservative fallback for malformed legacy groups.
    ids = tuple(dict.fromkeys(str(value) for value in patch_ids if str(value) in document.patches))
    patch_candidates: list[tuple[float, tuple[Point3, ...]]] = []
    for patch_id in ids:
        points = tuple(sample_patch_boundary(document, patch_id, arc_segments=arc_segments))
        if len(points) < 3:
            continue
        perimeter = sum(math.dist(points[index], points[(index + 1) % len(points)]) for index in range(len(points)))
        patch_candidates.append((perimeter, points))
    patch_candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return patch_candidates[0][1] if patch_candidates else ()


def _build_closure_cell_validator(
    document: ClothDocument,
    groups: Sequence[Sequence[str]],
) -> tuple[ClosureCellValidator | None, dict[str, object]]:
    """Return a conservative corridor validator for Close proposals.

    A valid closure may touch its source panels along the two selected rails,
    but it may not travel back over a source face or cross an existing textile
    panel.  The validator works on the canonical Cloth triangles and is only
    constructed when Close is explicitly analysed, so normal interaction does
    not pay this cost.
    """

    patch_ids = tuple(
        dict.fromkeys(
            str(patch_id)
            for group in groups
            for patch_id in group
            if str(patch_id) in document.patches
        )
    )
    if not patch_ids:
        return None, {"mode": "disabled", "triangle_count": 0}

    triangles: list[tuple[Point3, Point3, Point3]] = []
    triangle_owners: list[str] = []

    # Prefer the complete Cloth document so an unrelated textile panel can also
    # block a proposed corridor.  If one malformed legacy panel prevents a
    # canonical build, fall back to the selected source groups only; source
    # overlap protection must never disappear because of an unrelated issue.
    obstacle_patch_ids = tuple(document.patches)
    working = document.clone()
    built = build_cloth_surface_mesh(working, name="Cloth closure obstacles", solid=False)
    mode = "canonical_all"
    issues = tuple(built.issues)
    if built.mesh is None:
        working = document.clone()
        working.patches = {
            patch_id: working.patches[patch_id]
            for patch_id in patch_ids
            if patch_id in working.patches
        }
        built = build_cloth_surface_mesh(working, name="Cloth closure source obstacles", solid=False)
        obstacle_patch_ids = patch_ids
        mode = "canonical_sources"
        issues = tuple(dict.fromkeys((*issues, *built.issues)))
    if built.mesh is not None:
        mesh = built.mesh
        for patch_id in obstacle_patch_ids:
            start, end = built.patch_triangle_ranges.get(patch_id, (0, 0))
            for triangle_index in range(start, end):
                if triangle_index < 0 or triangle_index >= len(mesh.triangles):
                    continue
                indices = mesh.triangles[triangle_index]
                if len(indices) < 3:
                    continue
                triangle = tuple(mesh.vertices[index] for index in indices[:3])
                if len(triangle) == 3 and _triangle_area3(triangle) > _EPS:
                    triangles.append(triangle)  # type: ignore[arg-type]
                    triangle_owners.append(patch_id)

    # One malformed legacy panel must not disable protection for every other
    # selected panel.  Fall back patch-by-patch, then finally to a conservative
    # boundary fan for simple technical panels.
    missing = {
        patch_id
        for patch_id in obstacle_patch_ids
        if patch_id not in set(triangle_owners)
    }
    if missing:
        mode = "per_patch_fallback"
    for patch_id in sorted(missing):
        single = document.clone()
        single.patches = {patch_id: single.patches[patch_id]}
        local = build_cloth_surface_mesh(single, name=f"Cloth closure obstacle {patch_id}", solid=False)
        if local.mesh is not None:
            start, end = local.patch_triangle_ranges.get(patch_id, (0, len(local.mesh.triangles)))
            for triangle_index in range(start, end):
                indices = local.mesh.triangles[triangle_index]
                triangle = tuple(local.mesh.vertices[index] for index in indices[:3])
                if len(triangle) == 3 and _triangle_area3(triangle) > _EPS:
                    triangles.append(triangle)  # type: ignore[arg-type]
                    triangle_owners.append(patch_id)
            continue
        boundary = tuple(sample_patch_boundary(document, patch_id, arc_segments=24))
        for triangle in _triangulate_cap_preview(boundary):
            if _triangle_area3(triangle) > _EPS:
                triangles.append(triangle)
                triangle_owners.append(patch_id)

    if not triangles:
        return None, {
            "mode": "failed",
            "triangle_count": 0,
            "issues": list(issues),
        }

    tolerance = max(1.0e-5, min(0.25, cloth_stitch_tolerance_mm(document) * 0.75))
    indexed = tuple(
        (
            triangle,
            owner,
            _triangle_bounds(triangle, padding=tolerance * 2.0),
        )
        for triangle, owner in zip(triangles, triangle_owners)
    )

    def validator(
        first_anchor: str,
        second_anchor: str,
        a0: Point3,
        a1: Point3,
        b1: Point3,
        b0: Point3,
    ) -> bool:
        del first_anchor, second_anchor
        if _quad_area(a0, a1, b1, b0) <= max(_EPS, tolerance * tolerance * 0.01):
            return False
        cell_bounds = _points_bounds((a0, a1, b1, b0), padding=tolerance * 2.0)
        candidates = tuple(
            triangle
            for triangle, _owner, bounds in indexed
            if _bounds_overlap(cell_bounds, bounds)
        )
        if not candidates:
            return True

        # The complete interior of the ruled cell must remain in free space.
        # Sampling only the middle connector allowed twisted cells to pass over
        # a source panel near one end, which produced the visible "eaten"
        # textile in Close previews.  Probe a deterministic bilinear grid over
        # the whole quad while keeping the two source rails themselves legal.
        mid_a = _lerp3(a0, a1, 0.5)
        mid_b = _lerp3(b0, b1, 0.5)
        width = math.dist(mid_a, mid_b)
        if width <= tolerance:
            return False
        along_factors = (0.08, 0.28, 0.50, 0.72, 0.92)
        across_factors = (0.06, 0.18, 0.50, 0.82, 0.94)
        cross_sections: list[tuple[Point3, Point3]] = []
        for along in along_factors:
            rail_a_point = _lerp3(a0, a1, along)
            rail_b_point = _lerp3(b0, b1, along)
            cross_sections.append((rail_a_point, rail_b_point))
            for across in across_factors:
                point = _lerp3(rail_a_point, rail_b_point, across)
                if any(_point_on_triangle(point, triangle, tolerance=tolerance) for triangle in candidates):
                    return False

        # Catch non-coplanar crossings that point probes could miss.  Besides
        # the boundary connectors, test interior sections and both diagonals so
        # a folded or bow-tie cell cannot tunnel through an existing panel.
        segments = [
            (a0, b0),
            (a1, b1),
            *cross_sections,
            (a0, b1),
            (a1, b0),
        ]
        for start, end in segments:
            for triangle in candidates:
                hit = _segment_triangle_parameter(start, end, triangle, tolerance=tolerance)
                if hit is not None and 0.01 < hit < 0.99:
                    return False
        return True

    return validator, {
        "mode": mode,
        "triangle_count": len(triangles),
        "patch_count": len(set(triangle_owners)),
        "tolerance_mm": tolerance,
        "issues": list(issues),
    }


def _triangle_area3(triangle: Sequence[Point3]) -> float:
    if len(triangle) < 3:
        return 0.0
    return 0.5 * _cross_length(_sub(triangle[1], triangle[0]), _sub(triangle[2], triangle[0]))


def _triangle_bounds(
    triangle: Sequence[Point3],
    *,
    padding: float = 0.0,
) -> tuple[float, float, float, float, float, float]:
    return _points_bounds(triangle, padding=padding)


def _points_bounds(
    points: Sequence[Point3],
    *,
    padding: float = 0.0,
) -> tuple[float, float, float, float, float, float]:
    values = tuple(points)
    if not values:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    pad = max(0.0, float(padding))
    return (
        min(point[0] for point in values) - pad,
        max(point[0] for point in values) + pad,
        min(point[1] for point in values) - pad,
        max(point[1] for point in values) + pad,
        min(point[2] for point in values) - pad,
        max(point[2] for point in values) + pad,
    )


def _bounds_overlap(
    first: tuple[float, float, float, float, float, float],
    second: tuple[float, float, float, float, float, float],
) -> bool:
    return not (
        first[1] < second[0]
        or second[1] < first[0]
        or first[3] < second[2]
        or second[3] < first[2]
        or first[5] < second[4]
        or second[5] < first[4]
    )


def _lerp3(first: Point3, second: Point3, factor: float) -> Point3:
    value = max(0.0, min(1.0, float(factor)))
    return tuple(first[axis] + (second[axis] - first[axis]) * value for axis in range(3))  # type: ignore[return-value]


def _point_on_triangle(
    point: Point3,
    triangle: Sequence[Point3],
    *,
    tolerance: float,
) -> bool:
    if len(triangle) < 3:
        return False
    a, b, c = triangle[:3]
    normal = _cross3(_sub(b, a), _sub(c, a))
    normal_length = math.sqrt(_dot(normal, normal))
    if normal_length <= _EPS:
        return False
    signed = _dot(_sub(point, a), normal) / normal_length
    if abs(signed) > tolerance:
        return False
    projected = tuple(point[index] - normal[index] * signed / normal_length for index in range(3))
    v0 = _sub(b, a)
    v1 = _sub(c, a)
    v2 = _sub(projected, a)
    dot00 = _dot(v0, v0)
    dot01 = _dot(v0, v1)
    dot11 = _dot(v1, v1)
    dot20 = _dot(v2, v0)
    dot21 = _dot(v2, v1)
    denominator = dot00 * dot11 - dot01 * dot01
    if abs(denominator) <= _EPS:
        return False
    inv = 1.0 / denominator
    u = (dot11 * dot20 - dot01 * dot21) * inv
    v = (dot00 * dot21 - dot01 * dot20) * inv
    margin = max(1.0e-8, tolerance / max(math.sqrt(dot00), math.sqrt(dot11), 1.0))
    return u >= -margin and v >= -margin and u + v <= 1.0 + margin


def _segment_triangle_parameter(
    start: Point3,
    end: Point3,
    triangle: Sequence[Point3],
    *,
    tolerance: float,
) -> float | None:
    if len(triangle) < 3:
        return None
    a, b, c = triangle[:3]
    direction = _sub(end, start)
    edge1 = _sub(b, a)
    edge2 = _sub(c, a)
    pvec = _cross3(direction, edge2)
    determinant = _dot(edge1, pvec)
    epsilon = max(_EPS, tolerance * 1.0e-4)
    if abs(determinant) <= epsilon:
        return None
    inv = 1.0 / determinant
    tvec = _sub(start, a)
    u = _dot(tvec, pvec) * inv
    if u < -epsilon or u > 1.0 + epsilon:
        return None
    qvec = _cross3(tvec, edge1)
    v = _dot(direction, qvec) * inv
    if v < -epsilon or u + v > 1.0 + epsilon:
        return None
    t = _dot(edge2, qvec) * inv
    return t if -epsilon <= t <= 1.0 + epsilon else None


def _cross3(first: Point3, second: Point3) -> Point3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def analyze_textile_close_groups(
    document: ClothDocument,
    patch_groups: Iterable[Iterable[str]],
    curve_ids: Iterable[str] = (),
    *,
    minimum_samples: int = 8,
    maximum_samples: int = 72,
    diagnostics: Callable[[str, dict], None] | None = None,
) -> tuple[ClothJoinProposal, ...]:
    """Return closure proposals from logical textile groups and isolated edges."""

    def diag(stage: str, **payload) -> None:
        if diagnostics is not None:
            diagnostics(stage, payload)

    groups: list[tuple[str, ...]] = []
    for values in patch_groups:
        group = tuple(dict.fromkeys(str(value) for value in values if str(value) in document.patches))
        if group and group not in groups:
            groups.append(group)
    curve_values = tuple(dict.fromkeys(str(value) for value in curve_ids if str(value) in document.curves))
    diag(
        "input.normalized",
        group_count=len(groups),
        group_sizes=[len(group) for group in groups],
        groups=groups,
        curve_ids=curve_values,
        document_revision=document.revision,
        document_patch_count=len(document.patches),
        document_curve_count=len(document.curves),
    )
    cell_validator: ClosureCellValidator | None = None
    corridor_meta: dict[str, object] = {"mode": "disabled", "triangle_count": 0}
    if len(groups) >= 2:
        cell_validator, corridor_meta = _build_closure_cell_validator(document, groups)
    diag("corridor.obstacles", **corridor_meta)

    # One selected logical face can still contain one or more internal loops.
    # Close fills those holes without duplicating the group's outer surface.
    if len(groups) == 1 and not curve_values:
        loops = _patch_group_boundary_loops(document, groups[0])
        diag("single_group.loops", loop_count=len(loops), loop_point_counts=[len(loop) for loop in loops])
        holes = loops[1:] if len(loops) > 1 else ()
        if holes:
            caps = tuple(ClothCloseCap(f"group:0:hole:{index}", loop) for index, loop in enumerate(holes))
            patch_ids = tuple(dict.fromkeys(groups[0]))
            result = (
                ClothJoinProposal(
                    "close_group_holes",
                    patch_ids,
                    (),
                    0.98,
                    float(len(caps)),
                    f"Close {len(caps)} internal textile opening(s) in the selected logical face.",
                    (),
                    caps,
                ),
            )
            diag("result.single_group_holes", proposal_count=len(result), cap_count=len(caps))
            return result

    # Two logical groups may each expose several external loops (annular
    # panels, holes, disconnected but intentionally grouped islands).  Pair
    # every compatible loop before falling back to the largest boundary only.
    if len(groups) == 2 and not curve_values:
        first_loops = _patch_group_boundary_loops(document, groups[0])
        second_loops = _patch_group_boundary_loops(document, groups[1])
        if len(first_loops) > 1 and len(first_loops) == len(second_loops):
            multi_loop = _multi_loop_group_strategy(
                first_loops,
                second_loops,
                minimum_samples=minimum_samples,
                maximum_samples=maximum_samples,
                cell_validator=cell_validator,
            )
            diag(
                "multi_loop.analyzed",
                first_loop_count=len(first_loops),
                second_loop_count=len(second_loops),
                strategy_found=multi_loop is not None,
            )
            if multi_loop is not None:
                flat_patch_ids = tuple(dict.fromkeys(patch_id for group in groups for patch_id in group))
                base = _proposal(
                    "close_complete_multiloop",
                    ("group:0", "group:1"),
                    multi_loop.pairs,
                    label=multi_loop.label,
                )
                result = (
                    ClothJoinProposal(
                        base.id,
                        flat_patch_ids,
                        base.pairs,
                        base.confidence,
                        base.score,
                        base.message,
                    ),
                )
                diag(
                    "result.multi_loop",
                    proposal_count=1,
                    pair_count=len(base.pairs),
                    coverage=_pair_set_coverage(base.pairs),
                )
                return result

    # One isolated closed curve is also a valid Close input.
    if not groups and len(curve_values) == 1:
        curve_id = curve_values[0]
        curve = document.curves[curve_id]
        points = tuple(sample_curve(document, curve, arc_segments=32))
        diag("single_curve.sampled", curve_id=curve_id, closed=bool(curve.closed), point_count=len(points))
        if curve.closed and len(points) >= 3:
            result = (
                ClothJoinProposal(
                    "close_curve_loop",
                    (),
                    (),
                    0.96,
                    1.0,
                    "Close the selected textile loop with one new face.",
                    (curve_id,),
                    (ClothCloseCap(f"curve:{curve_id}", points),),
                ),
            )
            diag("result.single_curve", proposal_count=len(result), cap_count=1)
            return result

    anchors: dict[str, tuple[tuple[Point3, ...], bool]] = {}
    for index, group in enumerate(groups):
        points = _patch_group_boundary(document, group)
        if len(points) >= 3:
            anchors[f"group:{index}"] = (points, True)
    for curve_id in curve_values:
        points = tuple(sample_curve(document, document.curves[curve_id], arc_segments=32))
        if len(points) >= 2:
            anchors[f"curve:{curve_id}"] = (points, bool(document.curves[curve_id].closed))
    ids = tuple(anchors)
    diag(
        "anchors.built",
        anchor_ids=ids,
        anchor_count=len(ids),
        anchor_point_counts={anchor_id: len(values[0]) for anchor_id, values in anchors.items()},
        anchor_closed={anchor_id: bool(values[1]) for anchor_id, values in anchors.items()},
    )
    if len(ids) < 2:
        diag("result.no_proposal", reason="fewer_than_two_usable_anchors")
        return ()

    # Two closed logical inputs are the common interactive Close case.  Keep
    # all meaningful global strategies so Prev/Next can expose a full facing
    # cover, a complete perimeter loft and, only when useful, a local bridge.
    if len(ids) == 2 and all(anchors[anchor_id][1] for anchor_id in ids):
        strategies = _closed_boundary_strategies(
            ids[0],
            anchors[ids[0]][0],
            ids[1],
            anchors[ids[1]][0],
            minimum_samples,
            maximum_samples,
            cell_validator=cell_validator,
        )
        diag(
            "strategies.closed_pair",
            strategy_count=len(strategies),
            strategies=[{
                "id": strategy.id,
                "coverage": strategy.coverage,
                "pair_count": len(strategy.pairs),
                "segments": sum(pair.segment_count for pair in strategy.pairs),
                "score": strategy.score,
            } for strategy in strategies],
        )
        if strategies:
            flat_patch_ids = tuple(dict.fromkeys(patch_id for group in groups for patch_id in group))
            proposals: list[ClothJoinProposal] = []
            for strategy in strategies:
                base = _proposal(
                    f"close_{strategy.id}",
                    ids,
                    strategy.pairs,
                    label=strategy.label,
                )
                proposals.append(
                    ClothJoinProposal(
                        base.id,
                        flat_patch_ids,
                        base.pairs,
                        base.confidence,
                        base.score,
                        base.message,
                        curve_values,
                    )
                )
            diag(
                "result.closed_pair_proposals",
                proposal_count=len(proposals),
                proposal_ids=[item.id for item in proposals],
                panel_counts=[item.panel_count for item in proposals],
                coverages=[_pair_set_coverage(item.pairs) for item in proposals],
            )
            return tuple(proposals)

    candidates: list[tuple[float, ClothJoinPair]] = []
    for left_index, first_id in enumerate(ids):
        first_points, first_closed = anchors[first_id]
        for second_id in ids[left_index + 1 :]:
            second_points, second_closed = anchors[second_id]
            if first_closed and second_closed:
                pair = _pair_boundaries(
                    first_id,
                    first_points,
                    second_id,
                    second_points,
                    minimum_samples,
                    maximum_samples,
                    cell_validator=cell_validator,
                )
            elif not first_closed and not second_closed:
                pair = _pair_open_rails(first_id, first_points, second_id, second_points, minimum_samples, maximum_samples)
            elif first_closed:
                pair = _pair_closed_to_open(first_id, first_points, second_id, second_points, minimum_samples, maximum_samples)
            else:
                reversed_pair = _pair_closed_to_open(second_id, second_points, first_id, first_points, minimum_samples, maximum_samples)
                pair = None if reversed_pair is None else ClothJoinPair(
                    first_id,
                    second_id,
                    reversed_pair.second_rail,
                    reversed_pair.first_rail,
                    reversed_pair.mean_width_mm,
                    reversed_pair.max_width_mm,
                    reversed_pair.twist_score,
                )
            if pair is not None:
                candidates.append((_pair_cost(pair), pair))
    diag(
        "candidates.built",
        candidate_count=len(candidates),
        candidates=[{
            "cost": cost,
            "first": pair.first_patch_id,
            "second": pair.second_patch_id,
            "segments": pair.segment_count,
            "mean_width_mm": pair.mean_width_mm,
            "max_width_mm": pair.max_width_mm,
            "twist_score": pair.twist_score,
        } for cost, pair in candidates],
    )
    if not candidates:
        diag("result.no_proposal", reason="no_compatible_anchor_pairs")
        return ()
    candidates.sort(key=lambda item: (item[0], item[1].first_patch_id, item[1].second_patch_id))
    pairs = _minimum_spanning_pairs(ids, candidates)
    diag("mst.built", pair_count=len(pairs), expected_pair_count=max(0, len(ids) - 1))
    if len(pairs) != len(ids) - 1:
        diag("result.no_proposal", reason="anchors_not_fully_connected")
        return ()
    flat_patch_ids = tuple(dict.fromkeys(patch_id for group in groups for patch_id in group))
    proposal = _proposal("close_direct", ids, pairs, label="Logical textile closure")
    result = (
        ClothJoinProposal(
            proposal.id,
            flat_patch_ids,
            proposal.pairs,
            proposal.confidence,
            proposal.score,
            proposal.message,
            curve_values,
        ),
    )
    diag(
        "result.proposals",
        proposal_count=len(result),
        proposal_ids=[item.id for item in result],
        panel_counts=[item.panel_count for item in result],
        preview_triangle_counts=[len(item.triangle_preview) for item in result],
    )
    return result


def analyze_textile_close(
    document: ClothDocument,
    patch_ids: Iterable[str],
    curve_ids: Iterable[str] = (),
    *,
    minimum_samples: int = 8,
    maximum_samples: int = 72,
) -> tuple[ClothJoinProposal, ...]:
    """Backward-compatible singleton-group wrapper."""

    return analyze_textile_close_groups(
        document,
        ((patch_id,) for patch_id in patch_ids),
        curve_ids,
        minimum_samples=minimum_samples,
        maximum_samples=maximum_samples,
    )


def _resample_open(points: Sequence[Point3], count: int) -> tuple[Point3, ...]:
    values = tuple(points)
    if len(values) < 2 or count < 2:
        return ()
    segments = tuple(math.dist(values[index], values[index + 1]) for index in range(len(values) - 1))
    total = sum(segments)
    if total <= _EPS:
        return ()
    cumulative = [0.0]
    for length in segments:
        cumulative.append(cumulative[-1] + length)
    result: list[Point3] = []
    segment_index = 0
    for sample_index in range(count):
        distance = total * sample_index / max(1, count - 1)
        while segment_index + 1 < len(cumulative) and cumulative[segment_index + 1] < distance - _EPS:
            segment_index += 1
        segment_index = min(segment_index, len(segments) - 1)
        start = values[segment_index]
        end = values[segment_index + 1]
        length = max(segments[segment_index], _EPS)
        factor = max(0.0, min(1.0, (distance - cumulative[segment_index]) / length))
        result.append(tuple(start[axis] + (end[axis] - start[axis]) * factor for axis in range(3)))  # type: ignore[arg-type]
    return tuple(result)


def _pair_open_rails(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
) -> ClothJoinPair | None:
    count = max(2, min(maximum_samples, max(minimum_samples, len(first), len(second))))
    rail_a = _resample_open(first, count)
    direct = _resample_open(second, count)
    if len(rail_a) != count or len(direct) != count:
        return None
    alternatives = (direct, tuple(reversed(direct)))
    best: tuple[float, tuple[Point3, ...], float] | None = None
    for rail_b in alternatives:
        widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(count))
        mean = sum(widths) / count
        twist = _twist_score_open(rail_a, rail_b)
        variance = sum((value - mean) ** 2 for value in widths) / count
        cost = mean + math.sqrt(variance) * 0.7 + twist * max(mean, 1.0)
        if best is None or cost < best[0]:
            best = (cost, rail_b, twist)
    if best is None:
        return None
    widths = tuple(math.dist(rail_a[index], best[1][index]) for index in range(count))
    if min(widths, default=0.0) <= _EPS:
        return None
    return ClothJoinPair(first_id, second_id, rail_a, best[1], sum(widths) / count, max(widths), best[2])


def _pair_closed_to_open(
    closed_id: str,
    closed: Sequence[Point3],
    open_id: str,
    open_points: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
) -> ClothJoinPair | None:
    if len(closed) < 3 or len(open_points) < 2:
        return None
    # Choose the boundary path whose endpoints are closest to the open rail.
    first_index = min(range(len(closed)), key=lambda index: math.dist(closed[index], open_points[0]))
    second_index = min(range(len(closed)), key=lambda index: math.dist(closed[index], open_points[-1]))
    if first_index == second_index:
        second_index = (second_index + 1) % len(closed)

    def path(forward: bool) -> tuple[Point3, ...]:
        result = [closed[first_index]]
        index = first_index
        step = 1 if forward else -1
        guard = 0
        while index != second_index and guard <= len(closed):
            index = (index + step) % len(closed)
            result.append(closed[index])
            guard += 1
        return tuple(result)

    forward = path(True)
    backward = path(False)
    selected_path = min(
        (forward, backward),
        key=lambda values: _polyline_length(values) + math.dist(values[0], open_points[0]) + math.dist(values[-1], open_points[-1]),
    )
    return _pair_open_rails(closed_id, selected_path, open_id, open_points, minimum_samples, maximum_samples)


def _polyline_length(points: Sequence[Point3]) -> float:
    return sum(math.dist(points[index], points[index + 1]) for index in range(max(0, len(points) - 1)))


def _twist_score_open(first: Sequence[Point3], second: Sequence[Point3]) -> float:
    if len(first) < 2 or len(first) != len(second):
        return 1.0
    crossings = 0.0
    for index in range(len(first) - 1):
        if _dot(_sub(first[index + 1], first[index]), _sub(second[index + 1], second[index])) < 0.0:
            crossings += 1.0
    return crossings / max(1, len(first) - 1)

def commit_join_proposal(
    document: ClothDocument,
    proposal: ClothJoinProposal,
    *,
    drawing: ClothDrawingController | None = None,
) -> ClothDrawingOutcome:
    controller = drawing or ClothDrawingController(document)
    original = document.clone()
    created_points: list[str] = []
    created_curves: list[str] = []
    created_patch_ids: list[str] = []
    for pair_index, pair in enumerate(proposal.pairs):
        patches_before = set(document.patches)
        outcome = controller.create_ruled_strip_from_positions(
            pair.first_rail,
            pair.second_rail,
            metadata={
                "cloth_creation_kind": "join_faces",
                "cloth_join_proposal_id": proposal.id,
                "cloth_join_pair_index": pair_index,
                "cloth_join_anchor_ids": [pair.first_patch_id, pair.second_patch_id],
                "cloth_join_strategy": pair.strategy,
                "cloth_join_boundary_coverage": pair.coverage,
                "cloth_join_boundary_coverage_first": pair.coverage_first,
                "cloth_join_boundary_coverage_second": pair.coverage_second,
            },
        )
        if not outcome.committed:
            _restore_document(document, original)
            return ClothDrawingOutcome(False, message=outcome.message or "The proposed textile connection could not be created.")
        created_points.extend(outcome.created_point_ids)
        created_curves.extend(outcome.created_curve_ids)
        created_patch_ids.extend(patch_id for patch_id in document.patches if patch_id not in patches_before)
    for cap_index, cap in enumerate(proposal.caps):
        patches_before = set(document.patches)
        outcome = controller.create_surface_from_positions(
            cap.boundary,
            metadata={
                "cloth_creation_kind": "close_cap",
                "cloth_join_proposal_id": proposal.id,
                "cloth_close_cap_index": cap_index,
                "cloth_close_anchor_id": cap.anchor_id,
            },
        )
        if not outcome.committed:
            _restore_document(document, original)
            return ClothDrawingOutcome(False, message=outcome.message or "The selected textile opening could not be closed.")
        created_points.extend(outcome.created_point_ids)
        created_curves.extend(outcome.created_curve_ids)
        created_patch_ids.extend(patch_id for patch_id in document.patches if patch_id not in patches_before)
    if not created_patch_ids:
        _restore_document(document, original)
        return ClothDrawingOutcome(False, message="The proposal did not create any textile face.")
    return ClothDrawingOutcome(
        True,
        True,
        tuple(dict.fromkeys(created_points)),
        tuple(dict.fromkeys(created_curves)),
        created_patch_ids[0],
        (
            f"Created {len(created_patch_ids)} textile closure face(s)."
            if proposal.caps and not proposal.pairs
            else (
                f"Created {proposal.panel_count} connecting textile segment(s) between "
                f"{len({anchor for pair in proposal.pairs for anchor in (pair.first_patch_id, pair.second_patch_id)})} "
                "selected textile element(s)."
            )
        ),
    )



def _triangulate_cap_preview(boundary: Sequence[Point3]) -> tuple[tuple[Point3, Point3, Point3], ...]:
    """Triangulate a closed 3D loop for the non-destructive Close preview."""

    points = tuple(boundary[:-1] if len(boundary) > 3 and math.dist(boundary[0], boundary[-1]) <= 1.0e-7 else boundary)
    if len(points) < 3:
        return ()
    normal = _loop_normal(points)
    if normal is None:
        return ()
    origin = points[0]
    axis_u = None
    for point in points[1:]:
        edge = _sub(point, origin)
        projected = _sub(edge, tuple(normal[index] * _dot(edge, normal) for index in range(3)))
        axis_u = _unit(projected)
        if axis_u is not None:
            break
    if axis_u is None:
        return ()
    axis_v = _unit((
        normal[1] * axis_u[2] - normal[2] * axis_u[1],
        normal[2] * axis_u[0] - normal[0] * axis_u[2],
        normal[0] * axis_u[1] - normal[1] * axis_u[0],
    ))
    if axis_v is None:
        return ()
    points2 = [(_dot(_sub(point, origin), axis_u), _dot(_sub(point, origin), axis_v)) for point in points]
    try:
        from .mesh_builder import triangulate_simple_polygon

        indices = tuple(triangulate_simple_polygon(points2))
    except Exception:
        indices = ()
    if not indices:
        indices = tuple((0, index, index + 1) for index in range(1, len(points) - 1))
    return tuple((points[a], points[b], points[c]) for a, b, c in indices)

def _pair_boundaries(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    *,
    cell_validator: ClosureCellValidator | None = None,
) -> ClothJoinPair | None:
    """Return the strongest single rail pair for graph-based multi-anchor use.

    Two-anchor Close uses :func:`_closed_boundary_strategies` directly and can
    therefore expose several complete alternatives.  The graph path only needs
    one representative edge per anchor pair, so it keeps the longest pair from
    the best strategy.
    """

    strategies = _closed_boundary_strategies(
        first_id,
        first,
        second_id,
        second,
        minimum_samples,
        maximum_samples,
        cell_validator=cell_validator,
    )
    if not strategies:
        return None
    return max(
        strategies[0].pairs,
        key=lambda pair: (pair.coverage, pair.segment_count, -pair.mean_width_mm),
        default=None,
    )


def _closed_boundary_strategies(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    *,
    cell_validator: ClosureCellValidator | None = None,
) -> tuple[_ClosedBoundaryStrategy, ...]:
    """Build ranked, coverage-aware closure strategies for two closed loops.

    The old implementation selected one closest technical edge for lateral
    panels.  That was locally correct but contradicted the user's selection of
    complete logical faces.  This solver aligns the complete boundaries first,
    then derives long facing rail runs and a complete-perimeter alternative.
    Tiny local bridges are retained only as a last-resort proposal when they
    cover a meaningful fraction of both selected boundaries.
    """

    if len(first) < 3 or len(second) < 3:
        return ()
    count = max(12, min(maximum_samples, max(minimum_samples, len(first), len(second), 24)))
    aligned = _best_closed_alignment(
        first,
        second,
        count,
        first_id=first_id,
        second_id=second_id,
        cell_validator=cell_validator,
    )
    if aligned is None:
        return ()
    core_a, core_b, alignment_twist = aligned
    perimeter_a = _closed_perimeter(core_a)
    perimeter_b = _closed_perimeter(core_b)
    if perimeter_a <= _EPS or perimeter_b <= _EPS:
        return ()

    widths = [math.dist(core_a[index], core_b[index]) for index in range(count)]
    positive_widths = sorted(value for value in widths if value > _EPS)
    if not positive_widths:
        return ()
    median_width = _quantile(positive_widths, 0.5)
    collapse_tolerance = max(1.0e-7, median_width * 0.015)

    edge_lengths_a = [math.dist(core_a[index], core_a[(index + 1) % count]) for index in range(count)]
    edge_lengths_b = [math.dist(core_b[index], core_b[(index + 1) % count]) for index in range(count)]
    cell_widths: list[float] = []
    tangent_alignment: list[float] = []
    geometric_cells: list[bool] = []
    valid_cells: list[bool] = []
    for index in range(count):
        following = (index + 1) % count
        cell_width = 0.5 * (widths[index] + widths[following])
        cell_widths.append(cell_width)
        tangent_a = _unit(_sub(core_a[following], core_a[index]))
        tangent_b = _unit(_sub(core_b[following], core_b[index]))
        tangent_dot = _dot(tangent_a, tangent_b) if tangent_a is not None and tangent_b is not None else -1.0
        tangent_alignment.append(tangent_dot)
        area = _quad_area(core_a[index], core_a[following], core_b[following], core_b[index])
        connector0 = _unit(_sub(core_b[index], core_a[index]))
        connector1 = _unit(_sub(core_b[following], core_a[following]))
        connector_dot = _dot(connector0, connector1) if connector0 is not None and connector1 is not None else -1.0
        local_width_ratio = max(widths[index], widths[following]) / max(min(widths[index], widths[following]), _EPS)
        geometrically_valid = (
            widths[index] > collapse_tolerance
            and widths[following] > collapse_tolerance
            and edge_lengths_a[index] > _EPS
            and edge_lengths_b[index] > _EPS
            and tangent_dot > -0.35
            and connector_dot > -0.25
            and local_width_ratio < 6.0
            and area > max(1.0e-10, collapse_tolerance * min(edge_lengths_a[index], edge_lengths_b[index]) * 0.02)
        )
        geometric_cells.append(bool(geometrically_valid))
        corridor_valid = (
            cell_validator(
                first_id,
                second_id,
                core_a[index],
                core_a[following],
                core_b[following],
                core_b[index],
            )
            if geometrically_valid and cell_validator is not None
            else geometrically_valid
        )
        valid_cells.append(bool(corridor_valid))

    strategies: list[_ClosedBoundaryStrategy] = []
    vertex_complete = _vertex_complete_boundary_strategy(
        first_id,
        first,
        second_id,
        second,
        minimum_samples,
        maximum_samples,
        cell_validator=cell_validator,
    )
    if vertex_complete is not None:
        strategies.append(vertex_complete)

    # Explicit long facing chains are generated independently from the global
    # loop alignment.  This is essential for narrow U-shaped or ribbon-like
    # faces: the nearest technical edge is only a seed, and the correspondence
    # must continue over every smooth adjacent edge of the selected faces.
    strategies.extend(
        _facing_chain_strategies(
            first_id,
            first,
            second_id,
            second,
            minimum_samples,
            maximum_samples,
            cell_validator=cell_validator,
        )
    )

    # Endpoint-constrained arcs are a separate algorithm family.  They treat
    # sharp/extreme boundary points as possible user-intended ends, then test
    # both arcs between those ends.  This is deliberately broader than the
    # nearest-chain solver: a U-shaped ribbon can therefore expose its complete
    # long side even when local correspondence becomes irregular near a corner.
    strategies.extend(
        _translated_vertex_correspondence_strategies(
            first_id,
            first,
            second_id,
            second,
            minimum_samples,
            maximum_samples,
            cell_validator=cell_validator,
        )
    )

    strategies.extend(
        _endpoint_constrained_strategies(
            first_id,
            first,
            second_id,
            second,
            minimum_samples,
            maximum_samples,
            cell_validator=cell_validator,
        )
    )

    # Complete boundary closure.  Degenerate touching cells are split out, but
    # the remaining runs must still cover most of both selected boundaries.
    complete_pairs = _pairs_from_cell_mask(
        first_id,
        second_id,
        core_a,
        core_b,
        valid_cells,
        perimeter_a,
        perimeter_b,
        strategy="complete_boundary",
        minimum_run_cells=2,
    )
    complete_coverage = _pair_set_coverage(complete_pairs)
    geometric_count = sum(1 for value in geometric_cells if value)
    retained_ratio = sum(1 for value in valid_cells if value) / max(1, geometric_count)
    complete_minimum = 0.98 if cell_validator is not None else 0.68
    complete_retention = 0.995 if cell_validator is not None else 0.90
    if vertex_complete is None and complete_pairs and complete_coverage >= complete_minimum and retained_ratio >= complete_retention:
        strategies.append(
            _ClosedBoundaryStrategy(
                "complete_boundary",
                "Complete selected-boundary closure",
                complete_pairs,
                complete_coverage,
                _strategy_score(complete_pairs),
            )
        )

    # Long facing rails.  Width quantiles isolate the boundary portions that
    # actually face each other.  Unlike one closest edge, every contiguous run
    # has to carry a useful amount of the selected perimeter.
    valid_widths = [cell_widths[index] for index, valid in enumerate(valid_cells) if valid]
    if valid_widths:
        low = _quantile(valid_widths, 0.15)
        middle = _quantile(valid_widths, 0.55)
        high = _quantile(valid_widths, 0.90)
        spread = max(0.0, high - low)
        nearly_uniform = spread <= max(1.0e-6, middle * 0.12)
        threshold = high + 1.0e-9 if nearly_uniform else low + spread * 0.42
        facing_mask = [
            valid_cells[index]
            and cell_widths[index] <= threshold
            and tangent_alignment[index] > -0.10
            for index in range(count)
        ]
        facing_pairs = _pairs_from_cell_mask(
            first_id,
            second_id,
            core_a,
            core_b,
            facing_mask,
            perimeter_a,
            perimeter_b,
            strategy="facing_rails",
            minimum_run_cells=max(2, count // 24),
            minimum_pair_coverage=0.10,
        )
        facing_coverage = _pair_set_coverage(facing_pairs)
        facing_geometric_mask = [
            geometric_cells[index]
            and cell_widths[index] <= threshold
            and tangent_alignment[index] > -0.10
            for index in range(count)
        ]
        facing_geometric_count = sum(1 for value in facing_geometric_mask if value)
        facing_retained = sum(1 for value in facing_mask if value) / max(1, facing_geometric_count)
        if facing_pairs and facing_coverage >= 0.18 and facing_retained >= (0.98 if cell_validator is not None else 0.90):
            strategies.append(
                _ClosedBoundaryStrategy(
                    "facing_rails",
                    "Full facing-rail closure",
                    facing_pairs,
                    facing_coverage,
                    _strategy_score(facing_pairs),
                )
            )

    local = _closest_edge_pair(first_id, first, second_id, second)
    if local is not None and cell_validator is not None:
        safe_local = _split_pair_by_validator(local, cell_validator, minimum_run_cells=1)
        local = safe_local[0] if safe_local else None
    if local is not None and local.coverage >= 0.12:
        local_span = min(_polyline_length(local.first_rail), _polyline_length(local.second_rail))
        perimeter_scale = max(_EPS, min(perimeter_a, perimeter_b))
        is_complete_facing_edge = local_span / perimeter_scale >= 0.12
        strategies.append(
            _ClosedBoundaryStrategy(
                "facing_edge" if is_complete_facing_edge else "local_bridge",
                "Complete facing-edge closure" if is_complete_facing_edge else "Local compatible-edge closure",
                (local,),
                local.coverage,
                _strategy_score((local,)),
            )
        )

    if not strategies:
        return ()

    # Lateral/coplanar faces normally express a request for the long facing
    # sides.  Parallel offset rims normally express a complete perimeter loft.
    normal_a = _loop_normal(first)
    normal_b = _loop_normal(second)
    delta = _sub(_centroid(second), _centroid(first))
    delta_length = math.sqrt(_dot(delta, delta))
    normal_alignment = abs(_dot(normal_a, normal_b)) if normal_a is not None and normal_b is not None else 0.0
    through_normal = abs(_dot(delta, normal_a)) / delta_length if normal_a is not None and delta_length > _EPS else 0.0
    lateral = normal_alignment >= 0.70 and through_normal < 0.58

    if not lateral:
        # Closed loops separated mainly along their normal express one complete
        # sidewall intent.  A 90%-complete fallback looked plausible but left a
        # visible missing cap at the top.  Never promote partial facing chains
        # for this configuration: either the whole boundary is collision-free,
        # or Close must report that no safe proposal exists.
        strategies = [
            strategy
            for strategy in strategies
            if (strategy.id == "complete_boundary" and strategy.coverage >= 0.98)
            or (strategy.id.startswith(("endpoint_arc", "vertex_arc", "vertex_correspondence")) and strategy.coverage >= 0.18)
        ]
        strategies.sort(
            key=lambda strategy: (
                0 if strategy.id == "complete_boundary" else 1,
                -strategy.coverage,
                strategy.score,
            )
        )

    unique: list[_ClosedBoundaryStrategy] = []
    fingerprints: set[tuple] = set()
    for strategy in strategies:
        fingerprint = _strategy_fingerprint(strategy)
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        unique.append(strategy)

    has_complete = any(strategy.id == "complete_boundary" and strategy.coverage >= 0.75 for strategy in unique)
    if cell_validator is not None and _boundaries_touch(first, second) and not has_complete:
        # A shared point with no complete valid sidewall is topologically
        # ambiguous.  Partial endpoint arcs would merely hide the missing cell.
        return ()
    if has_complete and not _boundary_is_concave(first) and not _boundary_is_concave(second):
        # On convex parallel rims, a 90%-arc is visually just the complete loft
        # with one edge missing.  Keep the complete result and only retain
        # genuinely different partial alternatives.
        unique = [
            strategy for strategy in unique
            if not (
                strategy.id.startswith(("endpoint_arc", "vertex_arc", "vertex_correspondence"))
                and strategy.coverage >= 0.88
            )
        ]
    if has_complete and not lateral:
        # Parallel offset rims have one unambiguous intent: loft the complete
        # selected boundaries. Partial nearest-side chains add noise and can
        # recreate the historical short-bridge behaviour through Prev/Next.
        unique = [strategy for strategy in unique if not strategy.id.startswith("facing_chain")]
    elif has_complete:
        unique = [
            strategy
            for strategy in unique
            if not (strategy.id.startswith("facing_chain") and strategy.coverage < 0.14)
        ]

    def rank(strategy: _ClosedBoundaryStrategy) -> tuple[float, float, float, str]:
        preferred = 0.0
        # A partial facing chain is useful only when it genuinely represents a
        # substantial side of both selected faces.  Otherwise the complete
        # high-coverage closure must win: selecting complete faces is an
        # explicit request for complete coverage.
        if lateral and strategy.id.startswith("vertex_correspondence") and strategy.coverage >= 0.30:
            preferred = -4.6
        elif lateral and strategy.id.startswith("facing_chain_vertex") and strategy.coverage >= 0.24:
            preferred = -4.0
        elif strategy.id.startswith("vertex_arc") and strategy.coverage >= 0.24:
            preferred = -3.6 if lateral else -1.2
        elif lateral and strategy.id.startswith("facing_chain") and strategy.coverage >= 0.32:
            preferred = -3.0
        elif strategy.id == "complete_boundary" and strategy.coverage >= 0.75:
            preferred = -2.0
        elif lateral and strategy.id == "facing_rails" and strategy.coverage >= 0.32:
            preferred = -1.5
        elif strategy.id == "facing_edge":
            preferred = -3.25 if lateral else 1.0
        elif strategy.id.startswith("endpoint_arc"):
            preferred = (-2.9 if lateral else -1.0) if strategy.coverage >= 0.32 else -0.8
        elif strategy.id == "local_bridge":
            preferred = 2.0
        return (preferred, -strategy.coverage, strategy.score, strategy.id)

    unique.sort(key=rank)
    return tuple(unique[:20])





def _boundary_is_concave(points: Sequence[Point3]) -> bool:
    values = tuple(points)
    normal = _loop_normal(values)
    if len(values) < 4 or normal is None:
        return False
    signs: set[int] = set()
    for index in range(len(values)):
        previous = values[(index - 1) % len(values)]
        current = values[index]
        following = values[(index + 1) % len(values)]
        cross = _cross3(_sub(current, previous), _sub(following, current))
        signed = _dot(cross, normal)
        if abs(signed) <= 1.0e-8:
            continue
        signs.add(1 if signed > 0.0 else -1)
    return len(signs) > 1


def _boundaries_touch(first: Sequence[Point3], second: Sequence[Point3], *, tolerance: float = 1.0e-7) -> bool:
    threshold = max(1.0e-12, float(tolerance))
    return any(math.dist(a, b) <= threshold for a in first for b in second)

def _feature_boundary_indices(points: Sequence[Point3], *, limit: int = 14) -> tuple[int, ...]:
    """Return stable corners/extrema used as candidate closure endpoints."""

    values = tuple(points)
    count = len(values)
    if count <= 0:
        return ()
    if count <= limit:
        return tuple(range(count))
    scored: list[tuple[float, int]] = []
    for index in range(count):
        previous = values[(index - 1) % count]
        current = values[index]
        following = values[(index + 1) % count]
        incoming = _unit(_sub(current, previous))
        outgoing = _unit(_sub(following, current))
        corner = 0.0 if incoming is None or outgoing is None else max(0.0, 1.0 - _dot(incoming, outgoing))
        scored.append((corner, index))
    chosen = {index for _score, index in sorted(scored, key=lambda item: (-item[0], item[1]))[: max(4, limit - 6)]}
    for axis in range(3):
        chosen.add(min(range(count), key=lambda index: (values[index][axis], index)))
        chosen.add(max(range(count), key=lambda index: (values[index][axis], -index)))
    # Spread the remaining slots around the perimeter so smooth-but-important
    # endpoints are still explored on highly tessellated imported meshes.
    remaining = max(0, limit - len(chosen))
    for step in range(remaining):
        chosen.add(int(round(step * count / max(1, remaining))) % count)
    return tuple(sorted(chosen))


def _closed_arc(points: Sequence[Point3], start: int, end: int, *, forward: bool) -> tuple[Point3, ...]:
    values = tuple(points)
    count = len(values)
    if count < 3 or start == end:
        return ()
    step = 1 if forward else -1
    indices = [start]
    current = start
    for _ in range(count):
        if current == end:
            break
        current = (current + step) % count
        indices.append(current)
        if current == end:
            break
    if len(indices) < 2 or indices[-1] != end:
        return ()
    return tuple(values[index] for index in indices)


def _candidate_boundary_arcs(points: Sequence[Point3]) -> tuple[tuple[str, tuple[Point3, ...], float], ...]:
    values = tuple(points)
    perimeter = _closed_perimeter(values)
    if len(values) < 3 or perimeter <= _EPS:
        return ()
    features = _feature_boundary_indices(values)
    arcs: list[tuple[str, tuple[Point3, ...], float]] = []
    fingerprints: set[tuple] = set()
    for left_position, start in enumerate(features):
        for end in features[left_position + 1 :]:
            for forward in (True, False):
                arc = _closed_arc(values, start, end, forward=forward)
                length = _polyline_length(arc)
                coverage = length / perimeter
                if len(arc) < 2 or coverage < 0.10 or coverage > 0.93:
                    continue
                fingerprint = (
                    tuple(round(value, 5) for value in arc[0]),
                    tuple(round(value, 5) for value in arc[-1]),
                    round(coverage, 3),
                )
                if fingerprint in fingerprints:
                    continue
                fingerprints.add(fingerprint)
                direction = "f" if forward else "r"
                arcs.append((f"{start}_{end}_{direction}", arc, coverage))
    arcs.sort(key=lambda item: (-item[2], item[0]))
    return tuple(arcs[:48])



def _clean_open_vertices(points: Sequence[Point3]) -> tuple[Point3, ...]:
    """Return a deterministic open chain without coincident neighbours."""

    result: list[Point3] = []
    for raw in points:
        point = tuple(float(value) for value in raw)
        if not result or math.dist(result[-1], point) > 1.0e-8:
            result.append(point)  # type: ignore[arg-type]
    return tuple(result)


def _polyline_vertex_parameters(points: Sequence[Point3]) -> tuple[float, ...]:
    """Normalized arc-length parameters of every authored chain vertex."""

    values = _clean_open_vertices(points)
    if len(values) < 2:
        return ()
    lengths = [math.dist(values[index], values[index + 1]) for index in range(len(values) - 1)]
    total = sum(lengths)
    if total <= _EPS:
        return ()
    cumulative = [0.0]
    for length in lengths:
        cumulative.append(cumulative[-1] + length)
    return tuple(value / total for value in cumulative)


def _sample_open_fraction(points: Sequence[Point3], parameter: float) -> Point3 | None:
    values = _clean_open_vertices(points)
    if len(values) < 2:
        return None
    lengths = [math.dist(values[index], values[index + 1]) for index in range(len(values) - 1)]
    total = sum(lengths)
    if total <= _EPS:
        return None
    target = max(0.0, min(1.0, float(parameter))) * total
    travelled = 0.0
    for index, length in enumerate(lengths):
        following = travelled + length
        tolerance = max(1.0e-10, total * 1.0e-12)
        if abs(target - travelled) <= tolerance:
            return values[index]
        if abs(target - following) <= tolerance:
            return values[index + 1]
        if target <= following + tolerance or index == len(lengths) - 1:
            factor = 0.0 if length <= _EPS else max(0.0, min(1.0, (target - travelled) / length))
            start, end = values[index], values[index + 1]
            return tuple(start[axis] + (end[axis] - start[axis]) * factor for axis in range(3))  # type: ignore[return-value]
        travelled = following
    return values[-1]


def _reduced_vertex_parameters(points: Sequence[Point3], *, limit: int) -> tuple[float, ...]:
    """Keep endpoints, strong corners and evenly distributed authored vertices."""

    values = _clean_open_vertices(points)
    parameters = _polyline_vertex_parameters(values)
    if not parameters:
        return ()
    if len(parameters) <= max(2, limit):
        return parameters
    scored: list[tuple[float, int]] = []
    for index in range(1, len(values) - 1):
        incoming = _unit(_sub(values[index], values[index - 1]))
        outgoing = _unit(_sub(values[index + 1], values[index]))
        corner = 0.0 if incoming is None or outgoing is None else max(0.0, 1.0 - _dot(incoming, outgoing))
        scored.append((corner, index))
    keep = {0, len(values) - 1}
    corner_budget = max(0, min(len(scored), max(2, limit // 2) - 2))
    keep.update(index for _score, index in sorted(scored, key=lambda item: (-item[0], item[1]))[:corner_budget])
    remaining = max(0, limit - len(keep))
    for step in range(1, remaining + 1):
        target = step / (remaining + 1)
        keep.add(min(range(len(parameters)), key=lambda index: abs(parameters[index] - target)))
    return tuple(parameters[index] for index in sorted(keep))


def _closed_shape_signature(points: Sequence[Point3], *, samples: int = 32) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return a rotation/translation/scale invariant closed-loop signature.

    Authored boundaries often describe the same logical profile with different
    tessellation density, global orientation or a small scale change.  Absolute
    point residuals are deliberately not used here: normalized edge lengths and
    local turning cosines retain the shape while ignoring those harmless scene
    transforms.
    """

    values = tuple(points)
    if len(values) > 1 and math.dist(values[0], values[-1]) <= 1.0e-8:
        values = values[:-1]
    count = max(8, int(samples))
    sampled = _resample_closed(values, count)
    if len(sampled) == count + 1 and math.dist(sampled[0], sampled[-1]) <= 1.0e-8:
        sampled = sampled[:-1]
    if len(sampled) != count:
        return (), ()
    lengths = tuple(math.dist(sampled[index], sampled[(index + 1) % count]) for index in range(count))
    perimeter = sum(lengths)
    if perimeter <= _EPS:
        return (), ()
    normalized_lengths = tuple(value / perimeter for value in lengths)
    turns: list[float] = []
    for index in range(count):
        incoming = _unit(_sub(sampled[index], sampled[(index - 1) % count]))
        outgoing = _unit(_sub(sampled[(index + 1) % count], sampled[index]))
        turns.append(_dot(incoming, outgoing) if incoming is not None and outgoing is not None else 1.0)
    return normalized_lengths, tuple(turns)


def _closed_shape_signature_distance(first: Sequence[Point3], second: Sequence[Point3]) -> float:
    first_lengths, first_turns = _closed_shape_signature(first)
    second_lengths, second_turns = _closed_shape_signature(second)
    if not first_lengths or len(first_lengths) != len(second_lengths):
        return math.inf
    length_error = sum(abs(a - b) for a, b in zip(first_lengths, second_lengths))
    turn_error = sum(abs(a - b) for a, b in zip(first_turns, second_turns)) / len(first_turns)
    return length_error + turn_error * 0.35


def _vertex_anchored_rails(
    first: Sequence[Point3],
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
) -> tuple[tuple[Point3, ...], tuple[Point3, ...]] | None:
    """Align two chains while preserving their real boundary vertices.

    The old uniform sampler could start and turn at arbitrary positions on an
    edge.  Here every retained vertex of either source chain becomes a shared
    parameter.  Its opposite point may lie inside an edge, but authored corners
    and endpoints always remain exact on their own rail.
    """

    first_values = _clean_open_vertices(first)
    second_values = _clean_open_vertices(second)
    if len(first_values) < 2 or len(second_values) < 2:
        return None
    per_chain_limit = max(4, int(maximum_samples))
    parameters = set(_reduced_vertex_parameters(first_values, limit=per_chain_limit))
    parameters.update(_reduced_vertex_parameters(second_values, limit=per_chain_limit))
    required = max(2, min(maximum_samples, minimum_samples))
    if len(parameters) < required:
        parameters.update(index / max(1, required - 1) for index in range(required))
    ordered = sorted(max(0.0, min(1.0, value)) for value in parameters)
    deduped: list[float] = []
    for value in ordered:
        if not deduped or abs(value - deduped[-1]) > 1.0e-8:
            deduped.append(value)
    if len(deduped) > maximum_samples:
        essential = {0, len(deduped) - 1}
        for step in range(1, maximum_samples - 1):
            essential.add(round(step * (len(deduped) - 1) / max(1, maximum_samples - 1)))
        deduped = [deduped[index] for index in sorted(essential)]
    rail_a = tuple(_sample_open_fraction(first_values, value) for value in deduped)
    rail_b = tuple(_sample_open_fraction(second_values, value) for value in deduped)
    if any(point is None for point in (*rail_a, *rail_b)):
        return None
    return tuple(rail_a), tuple(rail_b)  # type: ignore[arg-type]


def _best_source_arc_for_rail(boundary: Sequence[Point3], rail: Sequence[Point3]) -> tuple[Point3, ...]:
    values = tuple(boundary)
    if len(values) < 3 or len(rail) < 2:
        return ()
    start = min(range(len(values)), key=lambda index: math.dist(values[index], rail[0]))
    end = min(range(len(values)), key=lambda index: math.dist(values[index], rail[-1]))
    if start == end:
        return ()
    candidates = tuple(
        arc for arc in (
            _closed_arc(values, start, end, forward=True),
            _closed_arc(values, start, end, forward=False),
        ) if len(arc) >= 2
    )
    if not candidates:
        return ()
    target_length = _polyline_length(rail)
    target_center = _centroid(rail)
    return min(
        candidates,
        key=lambda arc: abs(_polyline_length(arc) - target_length) + math.dist(_centroid(arc), target_center) * 0.35,
    )


def _vertex_reanchor_pair(
    pair: ClothJoinPair,
    first_boundary: Sequence[Point3],
    second_boundary: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    validator: ClosureCellValidator | None,
) -> ClothJoinPair | None:
    """Rebuild a sampled pair from exact source-boundary arcs."""

    arc_a = _best_source_arc_for_rail(first_boundary, pair.first_rail)
    arc_b = _best_source_arc_for_rail(second_boundary, pair.second_rail)
    if len(arc_a) < 2 or len(arc_b) < 2:
        return None
    direct = math.dist(arc_a[0], arc_b[0]) + math.dist(arc_a[-1], arc_b[-1])
    reverse = math.dist(arc_a[0], arc_b[-1]) + math.dist(arc_a[-1], arc_b[0])
    if reverse < direct:
        arc_b = tuple(reversed(arc_b))
    aligned = _vertex_anchored_rails(arc_a, arc_b, minimum_samples, maximum_samples)
    if aligned is None:
        return None
    rail_a, rail_b = aligned
    if len(rail_a) < 2 or len(rail_a) != len(rail_b):
        return None
    if validator is not None and any(
        not validator(
            pair.first_patch_id,
            pair.second_patch_id,
            rail_a[index],
            rail_a[index + 1],
            rail_b[index + 1],
            rail_b[index],
        )
        for index in range(len(rail_a) - 1)
    ):
        return None
    widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a)))
    if min(widths, default=0.0) <= _EPS:
        return None
    return ClothJoinPair(
        pair.first_patch_id,
        pair.second_patch_id,
        rail_a,
        rail_b,
        sum(widths) / len(widths),
        max(widths),
        _twist_score_open(rail_a, rail_b),
        min(1.0, _polyline_length(arc_a) / max(_closed_perimeter(first_boundary), _EPS)),
        min(1.0, _polyline_length(arc_b) / max(_closed_perimeter(second_boundary), _EPS)),
        f"vertex_anchored:{pair.strategy}",
    )




def _rotated_closed_chain(points: Sequence[Point3], start: int, *, forward: bool) -> tuple[Point3, ...]:
    values = tuple(points)
    if len(values) < 3:
        return ()
    step = 1 if forward else -1
    indices = tuple((start + step * offset) % len(values) for offset in range(len(values)))
    chain = tuple(values[index] for index in indices)
    return (*chain, chain[0])


def _vertex_complete_boundary_strategy(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    *,
    cell_validator: ClosureCellValidator | None = None,
) -> _ClosedBoundaryStrategy | None:
    """Return a complete closure whose turns stay on authored vertices."""

    values_a = tuple(first)
    values_b = tuple(second)
    if len(values_a) < 3 or len(values_b) < 3:
        return None
    # A shared source vertex makes the cyclic correspondence ambiguous.  The
    # legacy collision-aware solver deliberately rejects this case rather than
    # rotating one loop to hide the zero-width cell; preserve that invariant.
    if _boundaries_touch(values_a, values_b):
        return None
    center_a = _centroid(values_a)
    center_b = _centroid(values_b)
    translation = _sub(center_b, center_a)
    features_a = _feature_boundary_indices(values_a, limit=14)
    features_b = _feature_boundary_indices(values_b, limit=14)
    if not features_a or not features_b:
        return None

    candidates: list[tuple[float, ClothJoinPair]] = []
    for start_a in features_a:
        target = tuple(values_a[start_a][axis] + translation[axis] for axis in range(3))
        ranked_b = sorted(features_b, key=lambda index: math.dist(target, values_b[index]))[:3]
        chain_a = _rotated_closed_chain(values_a, start_a, forward=True)
        for start_b in ranked_b:
            for forward_b in (True, False):
                chain_b = _rotated_closed_chain(values_b, start_b, forward=forward_b)
                aligned = _vertex_anchored_rails(chain_a, chain_b, minimum_samples, maximum_samples)
                if aligned is None:
                    continue
                rail_a, rail_b = aligned
                if len(rail_a) < 4 or rail_a[0] != rail_a[-1] or rail_b[0] != rail_b[-1]:
                    continue
                if cell_validator is not None and any(
                    not cell_validator(
                        first_id,
                        second_id,
                        rail_a[index],
                        rail_a[index + 1],
                        rail_b[index + 1],
                        rail_b[index],
                    )
                    for index in range(len(rail_a) - 1)
                ):
                    continue
                widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a) - 1))
                if min(widths, default=0.0) <= _EPS:
                    continue
                mean = sum(widths) / len(widths)
                variance = sum((value - mean) ** 2 for value in widths) / len(widths)
                deviation_ratio = math.sqrt(variance) / max(mean, _EPS)
                twist = _twist_score_open(rail_a, rail_b)
                width_ratio = max(widths) / max(_quantile(widths, 0.5), _EPS)

                # Compare the two closed paths after applying only their gross
                # centroid displacement.  Authored homologous contours retain
                # the same turns under this comparison; a square paired with a
                # triangle (or a loop missing one corner) produces a large
                # residual even when a cyclic rotation happens to avoid direct
                # cell collisions.
                residuals: list[float] = []
                for fraction in (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875):
                    sample_a = _sample_open_fraction(chain_a, fraction)
                    sample_b = _sample_open_fraction(chain_b, fraction)
                    if sample_a is None or sample_b is None:
                        residuals = []
                        break
                    translated_a = tuple(sample_a[axis] + translation[axis] for axis in range(3))
                    residuals.append(math.dist(translated_a, sample_b))
                shape_residual = sum(residuals) / len(residuals) if residuals else math.inf
                perimeter_first = _closed_perimeter(values_a)
                perimeter_second = _closed_perimeter(values_b)
                shape_limit = max(1.0e-6, min(perimeter_first, perimeter_second) * 0.065)
                scale_ratio = max(perimeter_first, perimeter_second) / max(min(perimeter_first, perimeter_second), _EPS)
                signature_distance = _closed_shape_signature_distance(chain_a, chain_b)
                transform_invariant_homology = scale_ratio <= 1.45 and signature_distance <= 0.095

                # Vertex anchoring is preferred only for genuinely homologous
                # loops.  Absolute residuals remain the strict path, while the
                # invariant signature safely accepts the same authored profile
                # after moderate rotation, scale change or collinear retessellation.
                # Missing corners and unrelated contours still fail the turn/
                # normalized-edge signature and stay with conservative solvers.
                if (
                    twist > 0.24
                    or width_ratio > 2.20
                    or deviation_ratio > 0.38
                    or (shape_residual > shape_limit and not transform_invariant_homology)
                ):
                    continue
                pair = ClothJoinPair(
                    first_id,
                    second_id,
                    rail_a,
                    rail_b,
                    mean,
                    max(widths),
                    twist,
                    1.0,
                    1.0,
                    "complete_boundary_vertex",
                )
                start_residual = math.dist(target, values_b[start_b])
                cost = (
                    mean
                    + math.sqrt(variance) * 0.65
                    + twist * max(mean, 1.0)
                    + start_residual * 0.08
                    + min(signature_distance, 1.0) * max(mean, 1.0) * 0.35
                )
                candidates.append((cost, pair))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].segment_count))
    pair = candidates[0][1]
    return _ClosedBoundaryStrategy(
        "complete_boundary",
        "Vertex-anchored complete selected-boundary closure",
        (pair,),
        1.0,
        _strategy_score((pair,)),
    )


def _translated_vertex_correspondence_strategies(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    *,
    cell_validator: ClosureCellValidator | None = None,
) -> tuple[_ClosedBoundaryStrategy, ...]:
    """Match homologous authored vertices before constructing closure arcs.

    Imported textile groups often have the same logical profile translated or
    slightly deformed in space. Edge-nearest growth becomes unstable around a
    U-turn because the locally nearest counterpart can jump to the other side
    of the ribbon. This strategy estimates the group displacement, maps
    structural vertices first, then evaluates complete paths between them.
    """

    values_a = tuple(first)
    values_b = tuple(second)
    if len(values_a) < 4 or len(values_b) < 4:
        return ()
    perimeter_a = _closed_perimeter(values_a)
    perimeter_b = _closed_perimeter(values_b)
    if perimeter_a <= _EPS or perimeter_b <= _EPS:
        return ()
    center_a = _centroid(values_a)
    center_b = _centroid(values_b)
    translation = _sub(center_b, center_a)
    features_a = _feature_boundary_indices(values_a, limit=14)
    features_b = _feature_boundary_indices(values_b, limit=14)
    if len(features_a) < 2 or len(features_b) < 2:
        return ()

    def translated(point: Point3) -> Point3:
        return tuple(point[axis] + translation[axis] for axis in range(3))  # type: ignore[return-value]

    mapping: dict[int, int] = {}
    residuals: dict[int, float] = {}
    for index_a in features_a:
        target = translated(values_a[index_a])
        index_b = min(features_b, key=lambda value: math.dist(target, values_b[value]))
        mapping[index_a] = index_b
        residuals[index_a] = math.dist(target, values_b[index_b])

    # Rank cheaply first. The corridor validator performs many triangle tests,
    # so it must only see geometrically homologous paths, not every combinatorial
    # arc pair.
    raw: list[tuple[float, tuple[Point3, ...], tuple[Point3, ...], float, float, str]] = []
    for position, start_a in enumerate(features_a):
        for end_a in features_a[position + 1 :]:
            start_b = mapping.get(start_a)
            end_b = mapping.get(end_a)
            if start_b is None or end_b is None or start_b == end_b:
                continue
            anchor_residual = residuals[start_a] + residuals[end_a]
            for forward_a in (True, False):
                arc_a = _closed_arc(values_a, start_a, end_a, forward=forward_a)
                length_a = _polyline_length(arc_a)
                coverage_a = length_a / perimeter_a
                if len(arc_a) < 2 or coverage_a < 0.12 or coverage_a > 0.94:
                    continue
                for forward_b in (True, False):
                    arc_b = _closed_arc(values_b, start_b, end_b, forward=forward_b)
                    length_b = _polyline_length(arc_b)
                    coverage_b = length_b / perimeter_b
                    if len(arc_b) < 2 or coverage_b < 0.12 or coverage_b > 0.94:
                        continue
                    length_ratio = max(length_a, length_b) / max(min(length_a, length_b), _EPS)
                    if length_ratio > 2.25 or abs(coverage_a - coverage_b) > 0.22:
                        continue
                    direct = math.dist(arc_a[0], arc_b[0]) + math.dist(arc_a[-1], arc_b[-1])
                    reverse = math.dist(arc_a[0], arc_b[-1]) + math.dist(arc_a[-1], arc_b[0])
                    if reverse < direct:
                        arc_b = tuple(reversed(arc_b))
                    # Five translated shape probes reject paths that merely share
                    # endpoints but travel around different sides of the loop.
                    shape_residual = 0.0
                    valid_probes = True
                    for parameter in (0.0, 0.25, 0.5, 0.75, 1.0):
                        point_a = _sample_open_fraction(arc_a, parameter)
                        point_b = _sample_open_fraction(arc_b, parameter)
                        if point_a is None or point_b is None:
                            valid_probes = False
                            break
                        shape_residual += math.dist(translated(point_a), point_b)
                    if not valid_probes:
                        continue
                    shape_residual /= 5.0
                    scale = max(1.0, min(perimeter_a, perimeter_b))
                    if shape_residual > scale * 0.12:
                        continue
                    heuristic = (
                        shape_residual
                        + anchor_residual * 0.35
                        + abs(math.log(max(length_a, _EPS) / max(length_b, _EPS))) * scale * 0.10
                        - min(coverage_a, coverage_b) * scale * 0.04
                    )
                    identity = f"{start_a}:{end_a}:{int(forward_a)}:{int(forward_b)}"
                    raw.append((heuristic, arc_a, arc_b, coverage_a, coverage_b, identity))

    raw.sort(key=lambda item: (item[0], -min(item[3], item[4]), item[5]))
    candidates: list[_ClosedBoundaryStrategy] = []
    seen: set[tuple] = set()
    for serial, (_heuristic, arc_a, arc_b, coverage_a, coverage_b, identity) in enumerate(raw[:48]):
        aligned = _vertex_anchored_rails(arc_a, arc_b, minimum_samples, maximum_samples)
        if aligned is None:
            continue
        rail_a, rail_b = aligned
        if cell_validator is not None and any(
            not cell_validator(
                first_id,
                second_id,
                rail_a[index],
                rail_a[index + 1],
                rail_b[index + 1],
                rail_b[index],
            )
            for index in range(len(rail_a) - 1)
        ):
            continue
        widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a)))
        if min(widths, default=0.0) <= _EPS:
            continue
        twist = _twist_score_open(rail_a, rail_b)
        coverage = min(coverage_a, coverage_b)
        width_ratio = max(widths) / max(_quantile(widths, 0.5), _EPS)
        if twist > 0.48 or width_ratio > 8.0:
            continue
        pair = ClothJoinPair(
            first_id,
            second_id,
            rail_a,
            rail_b,
            sum(widths) / len(widths),
            max(widths),
            twist,
            coverage_a,
            coverage_b,
            f"vertex_correspondence:{identity}",
        )
        strategy = _ClosedBoundaryStrategy(
            f"vertex_correspondence_{serial}",
            "Vertex-correspondence boundary closure",
            (pair,),
            coverage,
            _strategy_score((pair,)),
        )
        fingerprint = _strategy_fingerprint(strategy)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        candidates.append(strategy)
        if len(candidates) >= 10:
            break

    candidates.sort(key=lambda item: (-item.coverage, item.score, item.id))
    return tuple(candidates)

def _endpoint_constrained_strategies(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    *,
    cell_validator: ClosureCellValidator | None = None,
) -> tuple[_ClosedBoundaryStrategy, ...]:
    """Generate diverse full-arc closures locked to explicit endpoints.

    Unlike local facing-chain growth, this family chooses two endpoints on each
    boundary first and requires every cell between them to be valid.  It is
    intentionally suitable for browsing: several topologically different arcs
    can survive and are later deduplicated with the other solver families.
    """

    if len(first) < 4 or len(second) < 4:
        # Endpoint sweeps need at least two independent arcs on both sides.
        # Triangular or collapsed legacy boundaries remain with the conservative
        # established solvers, which reject ambiguous missing-corner closures.
        return ()
    arcs_a = _candidate_boundary_arcs(first)
    arcs_b = _candidate_boundary_arcs(second)
    if not arcs_a or not arcs_b:
        return ()
    perimeter_a = _closed_perimeter(first)
    perimeter_b = _closed_perimeter(second)
    ranked: list[tuple[float, str, tuple[Point3, ...], float, str, tuple[Point3, ...], float, bool]] = []
    for id_a, arc_a, coverage_a in arcs_a:
        length_a = _polyline_length(arc_a)
        center_a = _centroid(arc_a)
        for id_b, arc_b, coverage_b in arcs_b:
            length_b = _polyline_length(arc_b)
            if min(length_a, length_b) <= _EPS:
                continue
            ratio = max(length_a, length_b) / max(min(length_a, length_b), _EPS)
            if ratio > 3.8:
                continue
            direct = math.dist(arc_a[0], arc_b[0]) + math.dist(arc_a[-1], arc_b[-1])
            reverse = math.dist(arc_a[0], arc_b[-1]) + math.dist(arc_a[-1], arc_b[0])
            reversed_b = reverse < direct
            endpoint_cost = min(direct, reverse)
            scale = max(length_a, length_b, 1.0)
            coverage = min(coverage_a, coverage_b)
            # Long arcs are intentionally rewarded.  Endpoint and centroid cost
            # still keep obviously unrelated sides out of the exact shortlist.
            cost = (
                endpoint_cost
                + math.dist(center_a, _centroid(arc_b)) * 0.12
                + abs(math.log(max(length_a, _EPS) / max(length_b, _EPS))) * scale * 0.55
                + (1.0 - coverage) * scale * 0.18
            )
            ranked.append((cost, id_a, arc_a, coverage_a, id_b, arc_b, coverage_b, reversed_b))
    ranked.sort(key=lambda item: (item[0], -min(item[3], item[6]), item[1], item[4]))

    results: list[_ClosedBoundaryStrategy] = []
    seen: set[tuple] = set()
    for candidate_index, (_cost, id_a, arc_a, coverage_a, id_b, raw_b, coverage_b, reversed_b) in enumerate(ranked[:80]):
        arc_b = tuple(reversed(raw_b)) if reversed_b else raw_b
        length_a = _polyline_length(arc_a)
        length_b = _polyline_length(arc_b)
        base_count = max(minimum_samples, len(arc_a), len(arc_b), 10)
        # Vertex-anchored correspondence is evaluated first.  Uniform
        # resampling remains as a secondary robustness parameter family, but it
        # is no longer allowed to displace real endpoints/corners in the primary
        # result.
        anchored = _vertex_anchored_rails(arc_a, arc_b, base_count, maximum_samples)
        variants: list[tuple[str, tuple[Point3, ...], tuple[Point3, ...]]] = []
        if anchored is not None:
            variants.append(("vertex", anchored[0], anchored[1]))
        counts = tuple(dict.fromkeys(
            max(4, min(maximum_samples, value))
            for value in (base_count, max(12, base_count * 2), 24, 36, 48)
        ))
        variants.extend(
            (f"n{count}", _resample_open(arc_a, count), _resample_open(arc_b, count))
            for count in counts
        )
        for density_index, (variant_id, rail_a, rail_b) in enumerate(variants):
            if len(rail_a) != len(rail_b) or len(rail_a) < 3:
                continue
            widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a)))
            if min(widths, default=0.0) <= _EPS:
                continue
            width_ratio = max(widths) / max(_quantile(widths, 0.5), _EPS)
            if width_ratio > 9.0:
                continue
            valid = True
            if cell_validator is not None:
                for index in range(len(rail_a) - 1):
                    if not cell_validator(first_id, second_id, rail_a[index], rail_a[index + 1], rail_b[index + 1], rail_b[index]):
                        valid = False
                        break
            if not valid:
                continue
            pair = ClothJoinPair(
                first_id,
                second_id,
                rail_a,
                rail_b,
                sum(widths) / len(widths),
                max(widths),
                _twist_score_open(rail_a, rail_b),
                min(1.0, length_a / max(perimeter_a, _EPS)),
                min(1.0, length_b / max(perimeter_b, _EPS)),
                f"endpoint_arc:{id_a}:{id_b}:{variant_id}",
            )
            if pair.coverage < 0.12 or pair.twist_score > 0.45:
                continue
            strategy = _ClosedBoundaryStrategy(
                f"vertex_arc_{candidate_index}" if variant_id == "vertex" else f"endpoint_arc_{candidate_index}_{density_index}",
                "Vertex-anchored endpoint closure" if variant_id == "vertex" else "Endpoint-constrained complete arc closure",
                (pair,),
                pair.coverage,
                _strategy_score((pair,)),
            )
            fingerprint = _strategy_fingerprint(strategy)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            results.append(strategy)
            # Keep the exact vertex-anchored variant and then one uniform
            # fallback for the same endpoint pair.  The latter can flatten more
            # easily on some highly warped chains; additional density-only
            # duplicates remain suppressed.
            if variant_id != "vertex":
                break
        if len(results) >= 16:
            break
    results.sort(key=lambda item: (-item.coverage, item.score, item.id))
    return tuple(results[:12])


def _multi_loop_group_strategy(
    first_loops: Sequence[Sequence[Point3]],
    second_loops: Sequence[Sequence[Point3]],
    *,
    minimum_samples: int,
    maximum_samples: int,
    cell_validator: ClosureCellValidator | None = None,
) -> _ClosedBoundaryStrategy | None:
    """Pair corresponding loops of two logical groups as one closure intent."""

    if len(first_loops) != len(second_loops) or len(first_loops) < 2:
        return None
    remaining = set(range(len(second_loops)))
    loop_pairs: list[tuple[int, int]] = []
    for first_index, first in enumerate(first_loops):
        perimeter_first = _closed_perimeter(first)
        center_first = _centroid(first)
        if perimeter_first <= _EPS:
            return None
        best: tuple[float, int] | None = None
        for second_index in remaining:
            second = second_loops[second_index]
            perimeter_second = _closed_perimeter(second)
            if perimeter_second <= _EPS:
                continue
            ratio_penalty = abs(math.log(max(perimeter_first, _EPS) / max(perimeter_second, _EPS)))
            center_distance = math.dist(center_first, _centroid(second))
            scale = max(perimeter_first, perimeter_second, 1.0)
            cost = ratio_penalty * scale + center_distance * 0.08
            if best is None or cost < best[0]:
                best = (cost, second_index)
        if best is None:
            return None
        remaining.remove(best[1])
        loop_pairs.append((first_index, best[1]))

    pairs: list[ClothJoinPair] = []
    for loop_index, (first_index, second_index) in enumerate(loop_pairs):
        strategies = _closed_boundary_strategies(
            "group:0",
            first_loops[first_index],
            "group:1",
            second_loops[second_index],
            minimum_samples,
            maximum_samples,
            cell_validator=cell_validator,
        )
        if not strategies or strategies[0].coverage < 0.60:
            return None
        for pair in strategies[0].pairs:
            pairs.append(
                ClothJoinPair(
                    pair.first_patch_id,
                    pair.second_patch_id,
                    pair.first_rail,
                    pair.second_rail,
                    pair.mean_width_mm,
                    pair.max_width_mm,
                    pair.twist_score,
                    pair.coverage_first,
                    pair.coverage_second,
                    f"multi_loop_{loop_index}:{pair.strategy}",
                )
            )
    if not pairs:
        return None
    return _ClosedBoundaryStrategy(
        "complete_multiloop",
        "Complete multi-loop selected-boundary closure",
        tuple(pairs),
        _pair_set_coverage(pairs),
        _strategy_score(pairs),
    )


def _facing_chain_strategies(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
    minimum_samples: int,
    maximum_samples: int,
    *,
    cell_validator: ClosureCellValidator | None = None,
) -> tuple[_ClosedBoundaryStrategy, ...]:
    """Find long, monotone edge-chain correspondences between two loops.

    A nearest-edge bridge is used only as a seed.  Adjacent compatible edge
    pairs are followed around both loops, allowing the solver to span a whole
    curved ribbon even when it is represented by dozens of technical faces.
    """

    count = max(24, min(maximum_samples, max(minimum_samples, len(first), len(second), 36)))
    sampled_a = _resample_closed(first, count)
    sampled_b = _resample_closed(second, count)
    if len(sampled_a) != count + 1 or len(sampled_b) != count + 1:
        return ()
    core_a = tuple(sampled_a[:-1])
    core_b = tuple(sampled_b[:-1])
    perimeter_a = _closed_perimeter(core_a)
    perimeter_b = _closed_perimeter(core_b)
    if perimeter_a <= _EPS or perimeter_b <= _EPS:
        return ()

    edge_a = []
    edge_b = []
    for values, target in ((core_a, edge_a), (core_b, edge_b)):
        for index in range(count):
            start = values[index]
            end = values[(index + 1) % count]
            direction = _unit(_sub(end, start))
            length = math.dist(start, end)
            midpoint = tuple((start[axis] + end[axis]) * 0.5 for axis in range(3))
            target.append((start, end, direction, length, midpoint))

    # Best oriented counterpart for each edge of A.
    mappings: list[tuple[int, int, float, float] | None] = []
    all_costs: list[float] = []
    for index_a, (a0, a1, direction_a, length_a, _mid_a) in enumerate(edge_a):
        best: tuple[float, int, int, float] | None = None
        if direction_a is None or length_a <= _EPS:
            mappings.append(None)
            continue
        for index_b, (b0, b1, direction_b, length_b, _mid_b) in enumerate(edge_b):
            if direction_b is None or length_b <= _EPS:
                continue
            direct_dot = _dot(direction_a, direction_b)
            for orientation in (1, -1):
                if orientation > 0:
                    first_b, second_b = b0, b1
                    tangent_dot = direct_dot
                else:
                    first_b, second_b = b1, b0
                    tangent_dot = -direct_dot
                if tangent_dot < 0.55:
                    continue
                width0 = math.dist(a0, first_b)
                width1 = math.dist(a1, second_b)
                mean_width = 0.5 * (width0 + width1)
                width_change = abs(width0 - width1)
                length_ratio = max(length_a, length_b) / max(min(length_a, length_b), _EPS)
                length_penalty = max(0.0, length_ratio - 1.6) * min(length_a, length_b)
                angle_penalty = (1.0 - tangent_dot) * max(mean_width, length_a, length_b)
                cost = mean_width + width_change * 0.55 + angle_penalty * 0.55 + length_penalty * 0.25
                if best is None or cost < best[0]:
                    best = (cost, index_b, orientation, mean_width)
        if best is None:
            mappings.append(None)
        else:
            mappings.append((best[1], best[2], best[0], best[3]))
            all_costs.append(best[0])

    if not all_costs:
        return ()
    low_cost = _quantile(all_costs, 0.10)
    middle_cost = _quantile(all_costs, 0.55)
    high_cost = _quantile(all_costs, 0.85)
    cost_threshold = low_cost + max((high_cost - low_cost) * 0.45, middle_cost * 0.18, 1.0e-6)

    # A cell participates only when the counterpart progression is monotone.
    compatibility = [False] * count
    for index in range(count):
        current = mappings[index]
        following = mappings[(index + 1) % count]
        if current is None or following is None:
            continue
        j, orientation, cost, _width = current
        next_j, next_orientation, next_cost, _next_width = following
        expected = (j + orientation) % count
        # Allow one skipped sample when the two loops have locally different
        # parameterisation; a larger jump indicates a true correspondence break.
        expected2 = (j + 2 * orientation) % count
        compatibility[index] = (
            orientation == next_orientation
            and next_j in {j, expected, expected2}
            and cost <= cost_threshold
            and next_cost <= cost_threshold * 1.12
        )

    runs = tuple(
        _expand_facing_run(run, mappings, count, cost_threshold)
        for run in _cyclic_true_runs(compatibility)
    )
    candidates: list[_ClosedBoundaryStrategy] = []
    for run_index, run_cells in enumerate(runs):
        if len(run_cells) < max(3, count // 18):
            continue
        start_edge = run_cells[0]
        mapping = mappings[start_edge]
        if mapping is None:
            continue
        orientation = mapping[1]
        a_indices = [start_edge]
        b_indices: list[int] = []
        first_b_index = mapping[0]
        b_indices.append(first_b_index if orientation > 0 else (first_b_index + 1) % count)
        valid = True
        previous_b_edge = first_b_index
        for cell in run_cells:
            mapped = mappings[cell]
            if mapped is None or mapped[1] != orientation:
                valid = False
                break
            b_edge = mapped[0]
            if cell != run_cells[0]:
                step = (b_edge - previous_b_edge) % count if orientation > 0 else (previous_b_edge - b_edge) % count
                if step > 2:
                    valid = False
                    break
            a_indices.append((cell + 1) % count)
            b_indices.append((b_edge + 1) % count if orientation > 0 else b_edge)
            previous_b_edge = b_edge
        if not valid or len(a_indices) != len(b_indices):
            continue
        rail_a = tuple(core_a[index] for index in a_indices)
        rail_b = tuple(core_b[index] for index in b_indices)
        if len(rail_a) < 4:
            continue
        widths = [math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a))]
        if min(widths, default=0.0) <= _EPS:
            continue
        coverage_a = min(1.0, _polyline_length(rail_a) / perimeter_a)
        coverage_b = min(1.0, _polyline_length(rail_b) / perimeter_b)
        coverage = min(coverage_a, coverage_b)
        if coverage < 0.14:
            continue
        pair = ClothJoinPair(
            first_id,
            second_id,
            rail_a,
            rail_b,
            sum(widths) / len(widths),
            max(widths),
            _twist_score_open(rail_a, rail_b),
            coverage_a,
            coverage_b,
            f"facing_chain_{run_index}",
        )
        pair = _snap_pair_ends_to_boundary(pair, first, second, cell_validator)
        anchored_pair = _vertex_reanchor_pair(
            pair,
            first,
            second,
            minimum_samples,
            maximum_samples,
            cell_validator,
        )
        if anchored_pair is not None:
            pair = anchored_pair
        if cell_validator is not None:
            safe_pairs = _split_pair_by_validator(pair, cell_validator, minimum_run_cells=2)
            if not safe_pairs:
                continue
            safe_coverage = _pair_set_coverage(safe_pairs)
            if len(safe_pairs) != 1 or safe_coverage + 1.0e-9 < pair.coverage * 0.98:
                continue
            candidates.append(
                _ClosedBoundaryStrategy(
                    f"facing_chain_vertex_{run_index}" if pair.strategy.startswith("vertex_anchored") else f"facing_chain_{run_index}",
                    "Vertex-anchored collision-free boundary closure" if pair.strategy.startswith("vertex_anchored") else "Continuous collision-free facing-boundary closure",
                    safe_pairs,
                    safe_coverage,
                    _strategy_score(safe_pairs),
                )
            )
            continue
        candidates.append(
            _ClosedBoundaryStrategy(
                f"facing_chain_vertex_{run_index}" if pair.strategy.startswith("vertex_anchored") else f"facing_chain_{run_index}",
                "Vertex-anchored facing-boundary closure" if pair.strategy.startswith("vertex_anchored") else "Continuous facing-boundary closure",
                (pair,),
                coverage,
                _strategy_score((pair,)),
            )
        )

    # Keep geometrically distinct chains.  The closest/longest chain is first;
    # opposite sides remain available through Prev/Next.
    candidates.sort(key=lambda item: (item.score, -item.coverage, item.id))
    return tuple(candidates[:3])


def _expand_facing_run(
    run: Sequence[int],
    mappings: Sequence[tuple[int, int, float, float] | None],
    count: int,
    cost_threshold: float,
) -> tuple[int, ...]:
    """Extend a strong facing run through nearby corner samples.

    The strict seed intentionally avoids jumps, but it used to stop one or two
    samples before a real panel endpoint.  A bounded relaxed extension keeps the
    same orientation and monotone counterpart progression while tolerating the
    local cost increase caused by a corner.
    """

    values = list(run)
    if not values or count <= 0:
        return tuple(values)
    present = set(values)
    maximum_extensions = max(2, min(6, count // 10))

    def compatible(cell: int) -> bool:
        current = mappings[cell]
        following = mappings[(cell + 1) % count]
        if current is None or following is None:
            return False
        j, orientation, cost, width = current
        next_j, next_orientation, next_cost, next_width = following
        if orientation != next_orientation:
            return False
        step = (next_j - j) % count if orientation > 0 else (j - next_j) % count
        if step > 3:
            return False
        if cost > cost_threshold * 2.8 or next_cost > cost_threshold * 3.0:
            return False
        width_ratio = max(width, next_width) / max(min(width, next_width), _EPS)
        return width_ratio <= 2.8

    for _ in range(maximum_extensions):
        candidate = (values[0] - 1) % count
        if candidate in present or not compatible(candidate):
            break
        values.insert(0, candidate)
        present.add(candidate)
    for _ in range(maximum_extensions):
        candidate = (values[-1] + 1) % count
        if candidate in present or not compatible(candidate):
            break
        values.append(candidate)
        present.add(candidate)
    return tuple(values)


def _split_pair_by_validator(
    pair: ClothJoinPair,
    validator: ClosureCellValidator,
    *,
    minimum_run_cells: int = 1,
) -> tuple[ClothJoinPair, ...]:
    """Remove cells that overlap/cross existing textiles and keep safe runs."""

    cell_count = pair.segment_count
    if cell_count <= 0 or len(pair.first_rail) != len(pair.second_rail):
        return ()
    safe = [
        validator(
            pair.first_patch_id,
            pair.second_patch_id,
            pair.first_rail[index],
            pair.first_rail[index + 1],
            pair.second_rail[index + 1],
            pair.second_rail[index],
        )
        for index in range(cell_count)
    ]
    runs: list[tuple[int, ...]] = []
    current: list[int] = []
    for index, value in enumerate(safe):
        if value:
            current.append(index)
        elif current:
            runs.append(tuple(current))
            current = []
    if current:
        runs.append(tuple(current))

    total_a = max(_polyline_length(pair.first_rail), _EPS)
    total_b = max(_polyline_length(pair.second_rail), _EPS)
    result: list[ClothJoinPair] = []
    for run_index, run in enumerate(runs):
        if len(run) < max(1, minimum_run_cells):
            continue
        start = run[0]
        end = run[-1] + 1
        rail_a = tuple(pair.first_rail[index] for index in range(start, end + 1))
        rail_b = tuple(pair.second_rail[index] for index in range(start, end + 1))
        if len(rail_a) < 2 or len(rail_a) != len(rail_b):
            continue
        widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a)))
        if not widths or min(widths) <= _EPS:
            continue
        coverage_a = pair.coverage_first * min(1.0, _polyline_length(rail_a) / total_a)
        coverage_b = pair.coverage_second * min(1.0, _polyline_length(rail_b) / total_b)
        result.append(
            ClothJoinPair(
                pair.first_patch_id,
                pair.second_patch_id,
                rail_a,
                rail_b,
                sum(widths) / len(widths),
                max(widths),
                _twist_score_open(rail_a, rail_b),
                coverage_a,
                coverage_b,
                f"{pair.strategy}:safe:{run_index}",
            )
        )
    result.sort(key=lambda value: (-value.coverage, -value.segment_count, value.mean_width_mm))
    return tuple(result)


def _snap_pair_ends_to_boundary(
    pair: ClothJoinPair,
    first_boundary: Sequence[Point3],
    second_boundary: Sequence[Point3],
    validator: ClosureCellValidator | None,
) -> ClothJoinPair:
    """Complete a facing rail up to nearby real boundary vertices.

    Resampling can stop a continuous rail one sample before a corner.  That
    leaves a visible triangular gap even though both source boundaries expose a
    compatible endpoint.  This helper adds at most one true boundary vertex at
    either end, after validating the added corridor cell.
    """

    if pair.segment_count < 1 or len(pair.first_rail) != len(pair.second_rail):
        return pair
    rail_a = list(pair.first_rail)
    rail_b = list(pair.second_rail)
    source_a = tuple(first_boundary)
    source_b = tuple(second_boundary)
    if not source_a or not source_b:
        return pair
    local_step = max(
        math.dist(rail_a[0], rail_a[1]),
        math.dist(rail_b[0], rail_b[1]),
        math.dist(rail_a[-2], rail_a[-1]),
        math.dist(rail_b[-2], rail_b[-1]),
        1.0e-6,
    )
    maximum_distance = max(local_step * 2.25, min(_closed_perimeter(source_a), _closed_perimeter(source_b)) * 0.035)

    def candidates(point: Point3, source: Sequence[Point3]) -> tuple[Point3, ...]:
        ranked = sorted(source, key=lambda value: math.dist(point, value))
        return tuple(value for value in ranked[:6] if math.dist(point, value) <= maximum_distance)

    def try_prepend() -> None:
        best: tuple[float, Point3, Point3] | None = None
        tangent_a = _unit(_sub(rail_a[0], rail_a[1]))
        tangent_b = _unit(_sub(rail_b[0], rail_b[1]))
        for new_a in candidates(rail_a[0], source_a):
            for new_b in candidates(rail_b[0], source_b):
                if math.dist(new_a, rail_a[0]) <= _EPS and math.dist(new_b, rail_b[0]) <= _EPS:
                    continue
                if validator is not None and not validator(
                    pair.first_patch_id,
                    pair.second_patch_id,
                    new_a,
                    rail_a[1],
                    rail_b[1],
                    new_b,
                ):
                    continue
                extension_a = _unit(_sub(new_a, rail_a[0]))
                extension_b = _unit(_sub(new_b, rail_b[0]))
                if extension_a is not None and tangent_a is not None and _dot(extension_a, tangent_a) < -0.40:
                    continue
                if extension_b is not None and tangent_b is not None and _dot(extension_b, tangent_b) < -0.40:
                    continue
                alignment = (
                    _dot(extension_a, extension_b)
                    if extension_a is not None and extension_b is not None
                    else 1.0
                )
                if extension_a is not None and extension_b is not None and alignment < 0.10:
                    continue
                width_change = abs(math.dist(new_a, new_b) - math.dist(rail_a[1], rail_b[1]))
                score = (
                    math.dist(new_a, rail_a[0])
                    + math.dist(new_b, rail_b[0])
                    + width_change * 0.35
                    + (1.0 - alignment) * local_step * 2.0
                )
                if best is None or score < best[0]:
                    best = (score, new_a, new_b)
        if best is not None:
            rail_a[0] = best[1]
            rail_b[0] = best[2]

    def try_append() -> None:
        best: tuple[float, Point3, Point3] | None = None
        tangent_a = _unit(_sub(rail_a[-1], rail_a[-2]))
        tangent_b = _unit(_sub(rail_b[-1], rail_b[-2]))
        for new_a in candidates(rail_a[-1], source_a):
            for new_b in candidates(rail_b[-1], source_b):
                if math.dist(new_a, rail_a[-1]) <= _EPS and math.dist(new_b, rail_b[-1]) <= _EPS:
                    continue
                if validator is not None and not validator(
                    pair.first_patch_id,
                    pair.second_patch_id,
                    rail_a[-2],
                    new_a,
                    new_b,
                    rail_b[-2],
                ):
                    continue
                extension_a = _unit(_sub(new_a, rail_a[-1]))
                extension_b = _unit(_sub(new_b, rail_b[-1]))
                if extension_a is not None and tangent_a is not None and _dot(extension_a, tangent_a) < -0.40:
                    continue
                if extension_b is not None and tangent_b is not None and _dot(extension_b, tangent_b) < -0.40:
                    continue
                alignment = (
                    _dot(extension_a, extension_b)
                    if extension_a is not None and extension_b is not None
                    else 1.0
                )
                if extension_a is not None and extension_b is not None and alignment < 0.10:
                    continue
                width_change = abs(math.dist(new_a, new_b) - math.dist(rail_a[-2], rail_b[-2]))
                score = (
                    math.dist(new_a, rail_a[-1])
                    + math.dist(new_b, rail_b[-1])
                    + width_change * 0.35
                    + (1.0 - alignment) * local_step * 2.0
                )
                if best is None or score < best[0]:
                    best = (score, new_a, new_b)
        if best is not None:
            rail_a[-1] = best[1]
            rail_b[-1] = best[2]

    try_prepend()
    try_append()
    if tuple(rail_a) == pair.first_rail and tuple(rail_b) == pair.second_rail:
        return pair
    widths = tuple(math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a)))
    return ClothJoinPair(
        pair.first_patch_id,
        pair.second_patch_id,
        tuple(rail_a),
        tuple(rail_b),
        sum(widths) / max(1, len(widths)),
        max(widths, default=pair.max_width_mm),
        _twist_score_open(rail_a, rail_b),
        min(1.0, _polyline_length(rail_a) / max(_closed_perimeter(source_a), _EPS)),
        min(1.0, _polyline_length(rail_b) / max(_closed_perimeter(source_b), _EPS)),
        f"{pair.strategy}:endpoint_complete",
    )


def _best_closed_alignment(
    first: Sequence[Point3],
    second: Sequence[Point3],
    count: int,
    *,
    first_id: str = "",
    second_id: str = "",
    cell_validator: ClosureCellValidator | None = None,
) -> tuple[tuple[Point3, ...], tuple[Point3, ...], float] | None:
    rail_a = _resample_closed(first, count)
    rail_b = _resample_closed(second, count)
    if len(rail_a) != count + 1 or len(rail_b) != count + 1:
        return None
    core_a = tuple(rail_a[:-1])
    raw_b = tuple(rail_b[:-1])

    # Geometry-only scoring is cheap.  Evaluate every cyclic alignment first,
    # then run the expensive source-surface corridor validator only on a small
    # deterministic shortlist.  This preserves collision-aware alignment while
    # keeping Close interactive on groups made of many technical patches.
    raw_candidates: list[tuple[float, tuple[Point3, ...], float, float]] = []
    for reversed_order in (False, True):
        values = tuple(reversed(raw_b)) if reversed_order else raw_b
        for offset in range(count):
            aligned = values[offset:] + values[:offset]
            widths = [math.dist(core_a[index], aligned[index]) for index in range(count)]
            mean = sum(widths) / count
            variance = sum((value - mean) ** 2 for value in widths) / count
            twist = _twist_score(core_a, aligned)
            tangent_penalty = 0.0
            for index in range(count):
                following = (index + 1) % count
                unit_a = _unit(_sub(core_a[following], core_a[index]))
                unit_b = _unit(_sub(aligned[following], aligned[index]))
                if unit_a is None or unit_b is None:
                    tangent_penalty += 1.0
                else:
                    tangent_penalty += max(0.0, 1.0 - _dot(unit_a, unit_b))
            tangent_penalty /= count
            base_cost = (
                mean
                + math.sqrt(variance) * 0.65
                + twist * max(mean, 1.0) * 0.45
                + tangent_penalty * max(mean, 1.0) * 0.18
            )
            raw_candidates.append((base_cost, tuple(aligned), twist, mean))

    if not raw_candidates:
        return None
    raw_candidates.sort(key=lambda item: item[0])
    if cell_validator is None:
        best = raw_candidates[0]
        return core_a, best[1], best[2]

    coarse_step = max(1, count // 18)
    coarse_indices = tuple(range(0, count, coarse_step))
    coarse_ranked: list[tuple[float, float, tuple[Point3, ...], float]] = []
    # Collision checks are deliberately lexicographic: a slightly shorter or
    # more uniform alignment may never beat an alignment with fewer cells that
    # cross existing textile.  Twelve coarse candidates and three exact
    # candidates keep the stricter bilinear corridor test interactive.
    for base_cost, aligned, twist, _mean in raw_candidates[: min(12, len(raw_candidates))]:
        invalid = 0
        for index in coarse_indices:
            following = (index + 1) % count
            if not cell_validator(
                first_id,
                second_id,
                core_a[index],
                core_a[following],
                aligned[following],
                aligned[index],
            ):
                invalid += 1
        invalid_ratio = invalid / max(1, len(coarse_indices))
        coarse_ranked.append((invalid_ratio, base_cost, aligned, twist))
    coarse_ranked.sort(key=lambda item: (item[0], item[1]))

    best: tuple[int, float, tuple[Point3, ...], float] | None = None
    for _coarse_invalid, base_cost, aligned, twist in coarse_ranked[: min(3, len(coarse_ranked))]:
        invalid = 0
        for index in range(count):
            following = (index + 1) % count
            if not cell_validator(
                first_id,
                second_id,
                core_a[index],
                core_a[following],
                aligned[following],
                aligned[index],
            ):
                invalid += 1
        candidate = (invalid, base_cost, aligned, twist)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        return None
    return core_a, best[2], best[3]


def _pairs_from_cell_mask(
    first_id: str,
    second_id: str,
    first: Sequence[Point3],
    second: Sequence[Point3],
    mask: Sequence[bool],
    perimeter_first: float,
    perimeter_second: float,
    *,
    strategy: str,
    minimum_run_cells: int,
    minimum_pair_coverage: float = 0.0,
) -> tuple[ClothJoinPair, ...]:
    runs = _cyclic_true_runs(mask)
    pairs: list[ClothJoinPair] = []
    count = len(first)
    for run in runs:
        if len(run) < max(1, minimum_run_cells):
            continue
        indices = [run[0]]
        for cell_index in run:
            indices.append((cell_index + 1) % count)
        rail_a = tuple(first[index] for index in indices)
        rail_b = tuple(second[index] for index in indices)
        length_a = _polyline_length(rail_a)
        length_b = _polyline_length(rail_b)
        coverage_a = min(1.0, length_a / max(perimeter_first, _EPS))
        coverage_b = min(1.0, length_b / max(perimeter_second, _EPS))
        coverage = min(coverage_a, coverage_b)
        if coverage + 1.0e-9 < minimum_pair_coverage:
            continue
        widths = [math.dist(rail_a[index], rail_b[index]) for index in range(len(rail_a))]
        if not widths or min(widths) <= _EPS:
            continue
        twist = _twist_score_open(rail_a, rail_b)
        pairs.append(
            ClothJoinPair(
                first_id,
                second_id,
                rail_a,
                rail_b,
                sum(widths) / len(widths),
                max(widths),
                twist,
                coverage_a,
                coverage_b,
                strategy,
            )
        )
    pairs.sort(key=lambda pair: (-pair.coverage, -pair.segment_count, pair.mean_width_mm))
    return tuple(pairs)


def _cyclic_true_runs(mask: Sequence[bool]) -> tuple[tuple[int, ...], ...]:
    values = tuple(bool(value) for value in mask)
    count = len(values)
    if count == 0 or not any(values):
        return ()
    if all(values):
        return (tuple(range(count)),)
    start = next(index for index, value in enumerate(values) if not value)
    runs: list[tuple[int, ...]] = []
    current: list[int] = []
    for step in range(1, count + 1):
        index = (start + step) % count
        if values[index]:
            current.append(index)
        elif current:
            runs.append(tuple(current))
            current = []
    if current:
        runs.append(tuple(current))
    return tuple(runs)


def _pair_set_coverage(pairs: Sequence[ClothJoinPair]) -> float:
    if not pairs:
        return 0.0
    return max(0.0, min(1.0, sum(pair.coverage for pair in pairs)))


def _strategy_score(pairs: Sequence[ClothJoinPair]) -> float:
    segments = sum(max(1, pair.segment_count) for pair in pairs)
    mean_width = sum(pair.mean_width_mm * max(1, pair.segment_count) for pair in pairs) / max(1, segments)
    twist = sum(pair.twist_score * max(1, pair.segment_count) for pair in pairs) / max(1, segments)
    coverage = _pair_set_coverage(pairs)
    max_width = max((pair.max_width_mm for pair in pairs), default=mean_width)
    width_spread = max(0.0, max_width - mean_width)
    return mean_width + width_spread * 0.25 + twist * max(mean_width, 1.0) + (1.0 - coverage) * max(mean_width, 1.0) * 1.8


def _strategy_fingerprint(strategy: _ClosedBoundaryStrategy) -> tuple:
    values: list[tuple] = []
    for pair in strategy.pairs:
        values.append(
            (
                pair.first_patch_id,
                pair.second_patch_id,
                pair.segment_count,
                round(pair.coverage, 3),
                tuple(round(value, 4) for value in pair.first_rail[0]),
                tuple(round(value, 4) for value in pair.first_rail[-1]),
                tuple(round(value, 4) for value in pair.second_rail[0]),
                tuple(round(value, 4) for value in pair.second_rail[-1]),
            )
        )
    return tuple(values)


def _closed_perimeter(points: Sequence[Point3]) -> float:
    return sum(math.dist(points[index], points[(index + 1) % len(points)]) for index in range(len(points))) if points else 0.0


def _quad_area(a0: Point3, a1: Point3, b1: Point3, b0: Point3) -> float:
    return 0.5 * (_cross_length(_sub(a1, a0), _sub(b1, a0)) + _cross_length(_sub(b1, a0), _sub(b0, a0)))


def _cross_length(a: Point3, b: Point3) -> float:
    x = a[1] * b[2] - a[2] * b[1]
    y = a[2] * b[0] - a[0] * b[2]
    z = a[0] * b[1] - a[1] * b[0]
    return math.sqrt(x * x + y * y + z * z)


def _quantile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = max(0.0, min(1.0, float(fraction))) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = min(len(ordered) - 1, lower + 1)
    factor = position - lower
    return ordered[lower] * (1.0 - factor) + ordered[upper] * factor

def _closest_edge_pair(
    first_id: str,
    first: Sequence[Point3],
    second_id: str,
    second: Sequence[Point3],
) -> ClothJoinPair | None:
    best: tuple[float, tuple[Point3, Point3], tuple[Point3, Point3]] | None = None
    for first_index in range(len(first)):
        a0 = first[first_index]
        a1 = first[(first_index + 1) % len(first)]
        length_a = math.dist(a0, a1)
        if length_a <= _EPS:
            continue
        for second_index in range(len(second)):
            b0 = second[second_index]
            b1 = second[(second_index + 1) % len(second)]
            length_b = math.dist(b0, b1)
            if length_b <= _EPS:
                continue
            direct = math.dist(a0, b0) + math.dist(a1, b1)
            reversed_cost = math.dist(a0, b1) + math.dist(a1, b0)
            aligned = (b1, b0) if reversed_cost < direct else (b0, b1)
            distance_cost = min(direct, reversed_cost) * 0.5
            length_cost = abs(length_a - length_b)
            direction_a = _unit(_sub(a1, a0))
            direction_b = _unit(_sub(aligned[1], aligned[0]))
            angle_cost = 1.0 - abs(_dot(direction_a, direction_b)) if direction_a is not None and direction_b is not None else 1.0
            cost = distance_cost + length_cost * 0.7 + angle_cost * max(length_a, length_b)
            if best is None or cost < best[0]:
                best = (cost, (a0, a1), aligned)
    if best is None:
        return None
    rail_a = best[1]
    rail_b = best[2]
    widths = (math.dist(rail_a[0], rail_b[0]), math.dist(rail_a[1], rail_b[1]))
    if min(widths) <= _EPS:
        return None
    perimeter_a = sum(math.dist(first[index], first[(index + 1) % len(first)]) for index in range(len(first)))
    perimeter_b = sum(math.dist(second[index], second[(index + 1) % len(second)]) for index in range(len(second)))
    coverage_a = min(1.0, math.dist(rail_a[0], rail_a[1]) / max(perimeter_a, _EPS))
    coverage_b = min(1.0, math.dist(rail_b[0], rail_b[1]) / max(perimeter_b, _EPS))
    return ClothJoinPair(
        first_id,
        second_id,
        rail_a,
        rail_b,
        sum(widths) / 2.0,
        max(widths),
        0.0,
        coverage_a,
        coverage_b,
        "local_bridge",
    )


def _loop_normal(points: Sequence[Point3]) -> Point3 | None:
    if len(points) < 3:
        return None
    nx = ny = nz = 0.0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    return _unit((nx, ny, nz))


def _centroid(points: Sequence[Point3]) -> Point3:
    count = max(1, len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _unit(value: Point3) -> Point3 | None:
    length = math.sqrt(_dot(value, value))
    if length <= _EPS:
        return None
    return (value[0] / length, value[1] / length, value[2] / length)


def _proposal(identifier: str, patch_ids: tuple[str, ...], pairs: tuple[ClothJoinPair, ...], *, label: str) -> ClothJoinProposal:
    segment_weight = sum(max(1, pair.segment_count) for pair in pairs)
    mean_width = sum(pair.mean_width_mm * max(1, pair.segment_count) for pair in pairs) / max(1, segment_weight)
    max_width = max((pair.max_width_mm for pair in pairs), default=0.0)
    twist = sum(pair.twist_score * max(1, pair.segment_count) for pair in pairs) / max(1, segment_weight)
    coverage = _pair_set_coverage(pairs)
    width_ratio = max_width / max(mean_width, _EPS)
    confidence = max(
        0.0,
        min(
            1.0,
            1.0
            - twist * 0.55
            - max(0.0, width_ratio - 1.8) * 0.18
            - max(0.0, 0.72 - coverage) * 0.65,
        ),
    )
    score = (
        mean_width
        + twist * max(mean_width, 1.0)
        + max(0.0, width_ratio - 1.0) * 0.5
        + (1.0 - coverage) * max(mean_width, 1.0) * 1.5
    )
    return ClothJoinProposal(
        identifier,
        patch_ids,
        pairs,
        confidence,
        score,
        (
            f"{label} · {sum(pair.segment_count for pair in pairs)} panel segment(s) · "
            f"boundary coverage {coverage * 100:.0f}% · mean width {mean_width:.3g} mm · "
            f"confidence {confidence * 100:.0f}%"
        ),
    )


def _minimum_spanning_pairs(ids: tuple[str, ...], candidates: list[tuple[float, ClothJoinPair]]) -> tuple[ClothJoinPair, ...]:
    parent = {item: item for item in ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    result: list[ClothJoinPair] = []
    for _cost, pair in candidates:
        left = find(pair.first_patch_id)
        right = find(pair.second_patch_id)
        if left == right:
            continue
        parent[right] = left
        result.append(pair)
        if len(result) == len(ids) - 1:
            break
    return tuple(result)


def _resample_closed(points: Sequence[Point3], count: int) -> tuple[Point3, ...]:
    values = tuple(points)
    if len(values) < 3 or count < 3:
        return ()
    segments = tuple(math.dist(values[index], values[(index + 1) % len(values)]) for index in range(len(values)))
    perimeter = sum(segments)
    if perimeter <= _EPS:
        return ()
    cumulative = [0.0]
    for length in segments:
        cumulative.append(cumulative[-1] + length)
    result: list[Point3] = []
    segment_index = 0
    for sample_index in range(count):
        distance = perimeter * sample_index / count
        while segment_index + 1 < len(cumulative) and cumulative[segment_index + 1] < distance - _EPS:
            segment_index += 1
        start = values[segment_index % len(values)]
        end = values[(segment_index + 1) % len(values)]
        length = max(segments[segment_index % len(segments)], _EPS)
        factor = max(0.0, min(1.0, (distance - cumulative[segment_index]) / length))
        result.append(tuple(start[axis] + (end[axis] - start[axis]) * factor for axis in range(3)))  # type: ignore[arg-type]
    result.append(result[0])
    return tuple(result)


def _twist_score(first: Sequence[Point3], second: Sequence[Point3]) -> float:
    if len(first) < 2 or len(first) != len(second):
        return 1.0
    crossings = 0.0
    for index in range(len(first)):
        following = (index + 1) % len(first)
        a = _sub(first[following], first[index])
        b = _sub(second[following], second[index])
        if _dot(a, b) < 0.0:
            crossings += 1.0
    return crossings / len(first)


def _pair_cost(pair: ClothJoinPair) -> float:
    return (
        pair.mean_width_mm
        + pair.twist_score * max(pair.mean_width_mm, 1.0)
        + max(0.0, pair.max_width_mm - pair.mean_width_mm) * 0.25
        + (1.0 - pair.coverage) * max(pair.mean_width_mm, 1.0) * 1.5
    )


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _restore_document(target: ClothDocument, source: ClothDocument) -> None:
    target.points = source.points
    target.curves = source.curves
    target.patches = source.patches
    target.folds = source.folds
    target.seams = source.seams
    if hasattr(target, "layers") and hasattr(source, "layers"):
        target.layers = source.layers
    target.metadata = source.metadata
    target.revision = source.revision
    target._next_id = source._next_id


__all__ = [
    "ClothJoinPair",
    "ClothJoinProposal",
    "analyze_patch_join",
    "analyze_textile_close",
    "analyze_textile_close_groups",
    "commit_join_proposal",
]
