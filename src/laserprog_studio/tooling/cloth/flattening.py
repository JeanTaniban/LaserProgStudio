"""Exact rigid unfolding for the Cloth piecewise-planar panel graph."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
import math
from typing import Iterable

from .models import ClothDocument, ClothFold, ClothPatch, Point3
from .topology import PatchFrame, curve_endpoint_ids, patch_frame, sample_patch_boundary

Point2 = tuple[float, float]
_EPS = 1.0e-9


def _sub2(a: Point2, b: Point2) -> Point2:
    return (a[0] - b[0], a[1] - b[1])


def _add2(a: Point2, b: Point2) -> Point2:
    return (a[0] + b[0], a[1] + b[1])


def _scale2(v: Point2, value: float) -> Point2:
    return (v[0] * value, v[1] * value)


def _dot2(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross2(a: Point2, b: Point2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _length2(v: Point2) -> float:
    return math.hypot(v[0], v[1])


def _unit2(v: Point2) -> Point2 | None:
    length = _length2(v)
    if length <= _EPS:
        return None
    return (v[0] / length, v[1] / length)


def _centroid2(points: Iterable[Point2]) -> Point2:
    values = tuple(points)
    if not values:
        return (0.0, 0.0)
    return (sum(point[0] for point in values) / len(values), sum(point[1] for point in values) / len(values))


@dataclass(frozen=True, slots=True)
class FlatTransform:
    matrix: tuple[tuple[float, float], tuple[float, float]] = ((1.0, 0.0), (0.0, 1.0))
    offset: Point2 = (0.0, 0.0)

    def map(self, point: Point2) -> Point2:
        return (
            self.matrix[0][0] * point[0] + self.matrix[0][1] * point[1] + self.offset[0],
            self.matrix[1][0] * point[0] + self.matrix[1][1] * point[1] + self.offset[1],
        )

    def shifted(self, offset: Point2) -> "FlatTransform":
        return replace(self, offset=_add2(self.offset, offset))


@dataclass(frozen=True, slots=True)
class PatchPlacement:
    patch_id: str
    frame: PatchFrame
    transform: FlatTransform
    component_index: int = 0

    def map_world(self, point: Point3) -> Point2:
        return self.transform.map(self.frame.project(point))


@dataclass(frozen=True, slots=True)
class FlatteningIssue:
    code: str
    message: str
    patch_ids: tuple[str, ...] = ()
    error: bool = False


@dataclass(slots=True)
class ClothFlatteningResult:
    placements: dict[str, PatchPlacement] = field(default_factory=dict)
    component_patch_ids: tuple[tuple[str, ...], ...] = ()
    issues: list[FlatteningIssue] = field(default_factory=list)
    max_closure_error_mm: float = 0.0
    virtual_cut_fold_ids: tuple[str, ...] = ()
    virtual_cut_curve_ids: tuple[str, ...] = ()
    virtual_cut_reasons: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.placements) and not any(issue.error for issue in self.issues)

    def map_world(self, patch_id: str, point: Point3) -> Point2:
        return self.placements[str(patch_id)].map_world(point)


def _patch_local_centroid(document: ClothDocument, patch: ClothPatch, frame: PatchFrame) -> Point2:
    return _centroid2(frame.project(point) for point in sample_patch_boundary(document, patch, arc_segments=12))


def _transform_mapping_edge(
    source_a: Point2,
    source_b: Point2,
    target_a: Point2,
    target_b: Point2,
    *,
    reflected: bool,
) -> FlatTransform | None:
    source_u = _unit2(_sub2(source_b, source_a))
    target_u = _unit2(_sub2(target_b, target_a))
    if source_u is None or target_u is None:
        return None
    source_v = (-source_u[1], source_u[0])
    target_v = (-target_u[1], target_u[0])
    sign = -1.0 if reflected else 1.0
    # M = target_u * source_u^T + sign * target_v * source_v^T
    m00 = target_u[0] * source_u[0] + sign * target_v[0] * source_v[0]
    m01 = target_u[0] * source_u[1] + sign * target_v[0] * source_v[1]
    m10 = target_u[1] * source_u[0] + sign * target_v[1] * source_v[0]
    m11 = target_u[1] * source_u[1] + sign * target_v[1] * source_v[1]
    mapped_source_a = (m00 * source_a[0] + m01 * source_a[1], m10 * source_a[0] + m11 * source_a[1])
    return FlatTransform(((m00, m01), (m10, m11)), _sub2(target_a, mapped_source_a))


def _fold_neighbor(fold: ClothFold, patch_id: str) -> str | None:
    if fold.patch_a_id == patch_id:
        return fold.patch_b_id
    if fold.patch_b_id == patch_id:
        return fold.patch_a_id
    return None


def _logical_group_id(document: ClothDocument, patch_id: str) -> str:
    patch = document.patches.get(str(patch_id))
    if patch is None:
        return ""
    metadata = dict(patch.metadata or {})
    return str(
        metadata.get("cloth_logical_group_id")
        or metadata.get("cloth_creation_group_id")
        or ""
    )


def _flatten_fold_forest(
    document: ClothDocument,
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, str]]:
    """Choose a deterministic fold forest and non-destructive pattern cuts.

    Persistent textile groups are user-facing pieces. Interfaces between two
    different groups are therefore pattern cuts by definition, even though the
    folded 3D preview keeps the surfaces touching. Any remaining cycle inside a
    single group is opened with the minimum number of additional cuts required
    to obtain a tree-like unfolding graph.
    """

    parent: dict[str, str] = {patch_id: patch_id for patch_id in document.patches}
    rank: dict[str, int] = {patch_id: 0 for patch_id in document.patches}

    def find(value: str) -> str:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            next_value = parent[value]
            parent[value] = root
            value = next_value
        return root

    def union(first: str, second: str) -> bool:
        first_root = find(first)
        second_root = find(second)
        if first_root == second_root:
            return False
        if rank[first_root] < rank[second_root]:
            first_root, second_root = second_root, first_root
        parent[second_root] = first_root
        if rank[first_root] == rank[second_root]:
            rank[first_root] += 1
        return True

    kept: list[str] = []
    cut: list[str] = []
    reasons: dict[str, str] = {}

    candidates: list[ClothFold] = []
    for fold in document.folds.values():
        if fold.patch_a_id not in parent or fold.patch_b_id not in parent:
            continue
        first_group = _logical_group_id(document, fold.patch_a_id)
        second_group = _logical_group_id(document, fold.patch_b_id)
        if first_group and second_group and first_group != second_group:
            cut.append(fold.id)
            reasons[fold.id] = "logical_group_boundary"
            continue
        candidates.append(fold)

    # Stable document order gives reproducible flat patterns. Metadata can mark
    # a specific interface as a preferred pattern cut without changing 3D.
    candidates.sort(
        key=lambda fold: (
            bool(dict(fold.metadata or {}).get("cloth_pattern_cut_preferred")),
            str(fold.id),
        )
    )
    for fold in candidates:
        if union(fold.patch_a_id, fold.patch_b_id):
            kept.append(fold.id)
        else:
            cut.append(fold.id)
            reasons[fold.id] = "cycle_break"

    return tuple(kept), tuple(cut), reasons


def _placement_across_fold(
    document: ClothDocument,
    parent: ClothPatch,
    child: ClothPatch,
    fold: ClothFold,
    parent_placement: PatchPlacement,
    child_frame: PatchFrame,
) -> PatchPlacement | None:
    curve = document.curves.get(fold.curve_id)
    if curve is None:
        return None
    point_a_id, point_b_id = curve_endpoint_ids(curve)
    if point_a_id not in document.points or point_b_id not in document.points:
        return None
    world_a = document.points[point_a_id].position
    world_b = document.points[point_b_id].position
    target_a = parent_placement.map_world(world_a)
    target_b = parent_placement.map_world(world_b)
    source_a = child_frame.project(world_a)
    source_b = child_frame.project(world_b)

    parent_centroid = _centroid2(parent_placement.map_world(point) for point in sample_patch_boundary(document, parent, arc_segments=12))
    target_edge = _sub2(target_b, target_a)
    parent_side = _cross2(target_edge, _sub2(parent_centroid, target_a))
    child_local_centroid = _patch_local_centroid(document, child, child_frame)

    candidates: list[tuple[float, PatchPlacement]] = []
    for reflected in (False, True):
        transform = _transform_mapping_edge(source_a, source_b, target_a, target_b, reflected=reflected)
        if transform is None:
            continue
        child_centroid = transform.map(child_local_centroid)
        child_side = _cross2(target_edge, _sub2(child_centroid, target_a))
        # Adjacent panels must unfold to opposite sides of the shared hinge.
        opposite_penalty = 0.0 if parent_side * child_side < -_EPS else 1.0
        overlap_penalty = abs(child_side) * -1.0e-9
        candidates.append((opposite_penalty + overlap_penalty, PatchPlacement(child.id, child_frame, transform, parent_placement.component_index)))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def flatten_cloth_document(
    document: ClothDocument,
    *,
    component_margin_mm: float | None = None,
    closure_tolerance_mm: float = 1.0e-4,
    heal_stitches: bool = True,
) -> ClothFlatteningResult:
    """Unfold all connected panel components into the XY plane.

    Each panel is transformed rigidly, so lengths and curved boundary geometry
    are preserved exactly.  Fold angles are not needed for the pattern: they
    describe the 3D presentation, while unfolding uses shared-edge topology.
    """

    # Public callers receive a non-mutating operation.  Apply preflight
    # already owns a healed clone and opts out to avoid cloning and healing twice.
    if heal_stitches:
        from .stitching import heal_cloth_stitches as _heal_cloth_stitches

        document = document.clone()
        _heal_cloth_stitches(document)
    result = ClothFlatteningResult()
    if component_margin_mm is None:
        try:
            component_margin_mm = float(document.metadata.get("cloth_pattern_component_margin_mm", 20.0))
        except (TypeError, ValueError):
            component_margin_mm = 20.0
    component_margin_mm = max(0.0, min(1000.0, float(component_margin_mm)))
    frames: dict[str, PatchFrame] = {}
    for patch in document.patches.values():
        frame = patch_frame(document, patch)
        if frame is None:
            result.issues.append(FlatteningIssue("cloth.flatten.no_plane", f"Panel {patch.name} has no stable plane.", (patch.id,), True))
        else:
            frames[patch.id] = frame
    if len(frames) != len(document.patches):
        return result

    kept_fold_ids, virtual_cut_fold_ids, virtual_cut_reasons = _flatten_fold_forest(document)
    kept_fold_id_set = set(kept_fold_ids)
    result.virtual_cut_fold_ids = virtual_cut_fold_ids
    result.virtual_cut_curve_ids = tuple(
        document.folds[fold_id].curve_id
        for fold_id in virtual_cut_fold_ids
        if fold_id in document.folds
    )
    result.virtual_cut_reasons = dict(virtual_cut_reasons)

    folds_by_patch: dict[str, list[ClothFold]] = {patch_id: [] for patch_id in document.patches}
    for fold in document.folds.values():
        if fold.id not in kept_fold_id_set:
            continue
        folds_by_patch.setdefault(fold.patch_a_id, []).append(fold)
        folds_by_patch.setdefault(fold.patch_b_id, []).append(fold)

    visited: set[str] = set()
    components: list[tuple[str, ...]] = []
    for root_id in document.patches:
        if root_id in visited:
            continue
        component_index = len(components)
        root = document.patches[root_id]
        root_placement = PatchPlacement(root_id, frames[root_id], FlatTransform(), component_index)
        result.placements[root_id] = root_placement
        queue: deque[str] = deque([root_id])
        component: list[str] = []
        visited.add(root_id)
        while queue:
            parent_id = queue.popleft()
            component.append(parent_id)
            parent = document.patches[parent_id]
            parent_placement = result.placements[parent_id]
            for fold in folds_by_patch.get(parent_id, ()):
                child_id = _fold_neighbor(fold, parent_id)
                if child_id is None or child_id not in document.patches:
                    continue
                child = document.patches[child_id]
                candidate = _placement_across_fold(document, parent, child, fold, parent_placement, frames[child_id])
                if candidate is None:
                    result.issues.append(FlatteningIssue("cloth.flatten.bad_hinge", f"Fold {fold.id} cannot place its adjacent panel.", (parent_id, child_id), True))
                    continue
                if child_id not in result.placements:
                    result.placements[child_id] = candidate
                    visited.add(child_id)
                    queue.append(child_id)
                else:
                    existing = result.placements[child_id]
                    curve = document.curves.get(fold.curve_id)
                    if curve is None:
                        continue
                    for point_id in curve_endpoint_ids(curve):
                        world = document.points[point_id].position
                        first = existing.map_world(world)
                        second = candidate.map_world(world)
                        error = _length2(_sub2(first, second))
                        result.max_closure_error_mm = max(result.max_closure_error_mm, error)
        components.append(tuple(component))

    # Place disconnected components side by side without altering any component's
    # internal geometry.
    cursor_x = 0.0
    packed_placements = dict(result.placements)
    for component in components:
        points: list[Point2] = []
        for patch_id in component:
            placement = packed_placements[patch_id]
            points.extend(placement.map_world(point) for point in sample_patch_boundary(document, document.patches[patch_id], arc_segments=24))
        if not points:
            continue
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        shift = (cursor_x - min_x, -min_y)
        for patch_id in component:
            placement = packed_placements[patch_id]
            packed_placements[patch_id] = replace(placement, transform=placement.transform.shifted(shift))
        cursor_x += (max_x - min_x) + max(0.0, float(component_margin_mm))
    result.placements = packed_placements
    result.component_patch_ids = tuple(components)

    if result.virtual_cut_fold_ids:
        group_cut_count = sum(
            1
            for fold_id in result.virtual_cut_fold_ids
            if result.virtual_cut_reasons.get(fold_id) == "logical_group_boundary"
        )
        cycle_cut_count = len(result.virtual_cut_fold_ids) - group_cut_count
        details: list[str] = []
        if group_cut_count:
            details.append(f"{group_cut_count} textile-group interface(s)")
        if cycle_cut_count:
            details.append(f"{cycle_cut_count} cycle-breaking interface(s)")
        result.issues.append(
            FlatteningIssue(
                "cloth.flatten.virtual_cuts",
                "Flat pattern opened " + " and ".join(details) + " as non-destructive virtual cuts.",
                tuple(document.patches),
                False,
            )
        )

    if result.max_closure_error_mm > closure_tolerance_mm:
        result.issues.append(
            FlatteningIssue(
                "cloth.flatten.cycle_closure",
                f"Fold graph is geometrically inconsistent by {result.max_closure_error_mm:.6g} mm.",
                tuple(document.patches),
                True,
            )
        )
    return result


__all__ = [
    "ClothFlatteningResult",
    "FlatTransform",
    "FlatteningIssue",
    "PatchPlacement",
    "flatten_cloth_document",
]
