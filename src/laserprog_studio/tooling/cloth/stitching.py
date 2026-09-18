"""Conservative healing of microscopic gaps between Cloth panel boundaries.

Stitch healing is a topology repair for older or numerically noisy files. It
joins only complete, straight, uncut panel boundaries whose endpoints agree
within the configured tolerance.  Explicit cuts and authored seams are never
converted into folds.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Iterable

from .drawing import infer_fold_angle
from .models import ClothCurve, ClothCurveKind, ClothCurveRole, ClothDocument
from .solidification import cloth_stitch_tolerance_mm
from .topology import curve_endpoint_ids, curve_patch_incidence

Point3 = tuple[float, float, float]
_CUT_KEYS = ("cloth_user_cut", "cloth_auto_cut")


@dataclass(frozen=True, slots=True)
class ClothStitchReport:
    tolerance_mm: float
    healed_curve_pairs: int = 0
    created_folds: int = 0
    snapped_points: int = 0
    scanned_boundaries: int = 0


@dataclass(frozen=True, slots=True)
class _BoundaryCandidate:
    order: int
    curve_id: str
    patch_id: str
    curve: ClothCurve
    first_point_id: str
    second_point_id: str
    first: Point3
    second: Point3

    @property
    def midpoint(self) -> Point3:
        return tuple((self.first[axis] + self.second[axis]) * 0.5 for axis in range(3))  # type: ignore[return-value]

    @property
    def length(self) -> float:
        return math.dist(self.first, self.second)


def _is_cut(curve: ClothCurve) -> bool:
    metadata = curve.metadata or {}
    return bool(
        any(metadata.get(key) for key in _CUT_KEYS)
        or metadata.get("cloth_pattern_edge_kind") == "cut"
    )


def _replace_curve_id(values: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if value == old else value for value in values)


def _curve_endpoints(
    document: ClothDocument,
    curve: ClothCurve,
) -> tuple[str, str, Point3, Point3] | None:
    first_id, second_id = curve_endpoint_ids(curve)
    first = document.points.get(first_id)
    second = document.points.get(second_id)
    if first is None or second is None:
        return None
    return first_id, second_id, first.position, second.position


def _match_orientation(
    first: _BoundaryCandidate,
    second: _BoundaryCandidate,
    tolerance: float,
) -> tuple[bool, float] | None:
    direct = max(
        math.dist(first.first, second.first),
        math.dist(first.second, second.second),
    )
    reverse = max(
        math.dist(first.first, second.second),
        math.dist(first.second, second.first),
    )
    best = min(direct, reverse)
    if best > tolerance:
        return None
    return reverse < direct, best


def _seam_curve_ids(document: ClothDocument) -> set[str]:
    return {
        curve_id
        for seam in document.seams.values()
        for curve_id in (*seam.first_curve_ids, *seam.second_curve_ids)
    }


def _candidate_boundaries(
    document: ClothDocument,
    incidence: dict[str, tuple[str, ...]],
) -> tuple[_BoundaryCandidate, ...]:
    seam_ids = _seam_curve_ids(document)
    fold_ids = {fold.curve_id for fold in document.folds.values()}
    candidates: list[_BoundaryCandidate] = []
    for curve_id, patch_ids in incidence.items():
        curve = document.curves.get(curve_id)
        if (
            curve is None
            or curve.kind is not ClothCurveKind.LINE
            or len(patch_ids) != 1
            or _is_cut(curve)
            or curve_id in seam_ids
            or curve_id in fold_ids
            or curve.role is ClothCurveRole.SEAM
        ):
            continue
        endpoints = _curve_endpoints(document, curve)
        if endpoints is None:
            continue
        first_id, second_id, first, second = endpoints
        if math.dist(first, second) <= 1.0e-12:
            continue
        candidates.append(
            _BoundaryCandidate(
                order=len(candidates),
                curve_id=curve_id,
                patch_id=patch_ids[0],
                curve=curve,
                first_point_id=first_id,
                second_point_id=second_id,
                first=first,
                second=second,
            )
        )
    return tuple(candidates)


def _bucket_key(candidate: _BoundaryCandidate, tolerance: float) -> tuple[int, int, int, int]:
    midpoint = candidate.midpoint
    return (
        int(math.floor(midpoint[0] / tolerance)),
        int(math.floor(midpoint[1] / tolerance)),
        int(math.floor(midpoint[2] / tolerance)),
        int(math.floor(candidate.length / tolerance)),
    )


def _nearby_candidates(
    candidate: _BoundaryCandidate,
    *,
    buckets: dict[tuple[int, int, int, int], list[_BoundaryCandidate]],
    tolerance: float,
) -> Iterable[_BoundaryCandidate]:
    x, y, z, length = _bucket_key(candidate, tolerance)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                # Endpoint agreement within tolerance can change total length by
                # at most twice that amount.
                for dl in (-2, -1, 0, 1, 2):
                    yield from buckets.get((x + dx, y + dy, z + dz, length + dl), ())


def _replace_curve_references(document: ClothDocument, old: str, new: str) -> None:
    for patch in document.patches.values():
        patch.outer_curve_ids = _replace_curve_id(patch.outer_curve_ids, old, new)
        patch.hole_curve_loops = tuple(
            _replace_curve_id(loop, old, new)
            for loop in patch.hole_curve_loops
        )
    for fold in document.folds.values():
        if fold.curve_id == old:
            fold.curve_id = new
    for seam in document.seams.values():
        seam.first_curve_ids = _replace_curve_id(seam.first_curve_ids, old, new)
        seam.second_curve_ids = _replace_curve_id(seam.second_curve_ids, old, new)


def _cleanup_orphans(document: ClothDocument) -> None:
    used_curves = {
        curve_id
        for patch in document.patches.values()
        for curve_id in (
            *patch.outer_curve_ids,
            *(value for loop in patch.hole_curve_loops for value in loop),
        )
    }
    used_curves.update(fold.curve_id for fold in document.folds.values())
    used_curves.update(
        value
        for seam in document.seams.values()
        for value in (*seam.first_curve_ids, *seam.second_curve_ids)
    )
    for curve_id in tuple(document.curves):
        if curve_id not in used_curves:
            document.curves.pop(curve_id, None)
    used_points = {
        point_id
        for curve in document.curves.values()
        for point_id in curve.point_ids
    }
    for point_id in tuple(document.points):
        if point_id not in used_points:
            document.points.pop(point_id, None)


def _ensure_fold(
    document: ClothDocument,
    curve_id: str,
    patch_a: str,
    patch_b: str,
) -> bool:
    if any(fold.curve_id == curve_id for fold in document.folds.values()):
        return False
    curve = document.curves.get(curve_id)
    if curve is None or _is_cut(curve) or curve.role is ClothCurveRole.SEAM:
        return False
    try:
        angle = infer_fold_angle(document, curve_id, patch_a, patch_b)
    except (KeyError, ValueError):
        angle = 0.0
    document.add_fold(
        curve_id,
        patch_a,
        patch_b,
        angle_degrees=float(angle),
        metadata={"cloth_stitch_inferred": True},
    )
    return True


def _snap_and_merge_pair(
    document: ClothDocument,
    canonical: _BoundaryCandidate,
    duplicate: _BoundaryCandidate,
    *,
    reverse: bool,
) -> tuple[int, bool]:
    duplicate_first_id = duplicate.second_point_id if reverse else duplicate.first_point_id
    duplicate_second_id = duplicate.first_point_id if reverse else duplicate.second_point_id
    duplicate_first = duplicate.second if reverse else duplicate.first
    duplicate_second = duplicate.first if reverse else duplicate.second

    average_first = tuple(
        (canonical.first[axis] + duplicate_first[axis]) * 0.5
        for axis in range(3)
    )
    average_second = tuple(
        (canonical.second[axis] + duplicate_second[axis]) * 0.5
        for axis in range(3)
    )
    snapped = 0
    if document.points[canonical.first_point_id].position != average_first:
        document.points[canonical.first_point_id].position = average_first  # type: ignore[assignment]
        snapped += 1
    if document.points[canonical.second_point_id].position != average_second:
        document.points[canonical.second_point_id].position = average_second  # type: ignore[assignment]
        snapped += 1

    duplicate_patch = document.patches[duplicate.patch_id]
    point_map = {
        duplicate_first_id: canonical.first_point_id,
        duplicate_second_id: canonical.second_point_id,
    }
    duplicate_patch_curve_ids = {
        curve_id
        for curve_id in (
            *duplicate_patch.outer_curve_ids,
            *(value for loop in duplicate_patch.hole_curve_loops for value in loop),
        )
        if curve_id != duplicate.curve_id
    }
    for adjacent_curve_id in duplicate_patch_curve_ids:
        adjacent = document.curves.get(adjacent_curve_id)
        if adjacent is not None:
            adjacent.point_ids = tuple(
                point_map.get(point_id, point_id)
                for point_id in adjacent.point_ids
            )

    _replace_curve_references(document, duplicate.curve_id, canonical.curve_id)
    canonical.curve.role = ClothCurveRole.FOLD
    canonical.curve.metadata["cloth_stitch_healed"] = True
    canonical.curve.metadata["cloth_stitch_source_curve"] = duplicate.curve_id
    document.curves.pop(duplicate.curve_id, None)
    created_fold = _ensure_fold(
        document,
        canonical.curve_id,
        canonical.patch_id,
        duplicate.patch_id,
    )
    return snapped, created_fold


def heal_cloth_stitches(
    document: ClothDocument,
    *,
    tolerance_mm: float | None = None,
) -> ClothStitchReport:
    """Heal complete near-coincident panel boundaries in-place.

    Partial overlaps are deliberately rejected because they require a real curve
    split.  The spatial bucket index keeps large panel sets near-linear while an
    exact endpoint test remains the final authority.
    """

    tolerance = (
        cloth_stitch_tolerance_mm(document)
        if tolerance_mm is None
        else max(1.0e-6, min(5.0, float(tolerance_mm)))
    )
    document.metadata["cloth_stitch_tolerance_mm"] = tolerance
    incidence = curve_patch_incidence(document)
    existing_fold_curves = {fold.curve_id for fold in document.folds.values()}
    created_folds = 0

    # A shared, non-cut curve is already one physical hinge.  Old files may miss
    # only the explicit fold relation.
    seam_ids = _seam_curve_ids(document)
    for curve_id, patch_ids in tuple(incidence.items()):
        curve = document.curves.get(curve_id)
        if (
            curve is None
            or len(patch_ids) != 2
            or curve_id in existing_fold_curves
            or curve_id in seam_ids
            or _is_cut(curve)
        ):
            continue
        if _ensure_fold(document, curve_id, patch_ids[0], patch_ids[1]):
            created_folds += 1
            existing_fold_curves.add(curve_id)

    candidates = _candidate_boundaries(document, incidence)
    buckets: dict[tuple[int, int, int, int], list[_BoundaryCandidate]] = defaultdict(list)
    for candidate in candidates:
        buckets[_bucket_key(candidate, tolerance)].append(candidate)

    consumed: set[str] = set()
    healed = 0
    snapped = 0
    for candidate in candidates:
        if candidate.curve_id in consumed or candidate.curve_id not in document.curves:
            continue
        best: tuple[float, bool, _BoundaryCandidate] | None = None
        for other in _nearby_candidates(candidate, buckets=buckets, tolerance=tolerance):
            if (
                other.order <= candidate.order
                or other.curve_id in consumed
                or other.curve_id not in document.curves
                or other.patch_id == candidate.patch_id
            ):
                continue
            match = _match_orientation(candidate, other, tolerance)
            if match is None:
                continue
            reverse, distance = match
            if best is None or (distance, other.order) < (best[0], best[2].order):
                best = distance, reverse, other
        if best is None:
            continue

        _distance, reverse, duplicate = best
        pair_snapped, pair_created_fold = _snap_and_merge_pair(
            document,
            candidate,
            duplicate,
            reverse=reverse,
        )
        consumed.add(duplicate.curve_id)
        snapped += pair_snapped
        healed += 1
        created_folds += int(pair_created_fold)

    if healed or created_folds or snapped:
        _cleanup_orphans(document)
        document.metadata["cloth_stitch_healed_count"] = (
            int(document.metadata.get("cloth_stitch_healed_count", 0)) + healed
        )
        document.revision += 1
    return ClothStitchReport(
        tolerance,
        healed,
        created_folds,
        snapped,
        len(candidates),
    )


__all__ = ["ClothStitchReport", "heal_cloth_stitches"]
