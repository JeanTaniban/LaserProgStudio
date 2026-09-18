"""Apply-time validation for piecewise-planar Cloth documents.

The V1 editor deliberately rejects geometry that its surface and unfolding
pipelines cannot represent faithfully.  Validation is therefore the single
source of truth used by both the UX and Apply, rather than allowing a seemingly
valid document to fail later during triangulation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable, Sequence

from laserprog_studio.tool_api.tracing import distance3

from .models import ClothCurve, ClothCurveKind, ClothDocument
from .topology import (
    chain_length,
    curve_endpoint_ids,
    curve_patch_incidence,
    order_curve_loop,
    patch_area,
    patch_frame,
    patch_point_ids,
    sample_patch_boundary,
)

Point2 = tuple[float, float]
_EPS = 1.0e-9


class ClothIssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ClothValidationIssue:
    code: str
    message: str
    severity: ClothIssueSeverity = ClothIssueSeverity.ERROR
    entity_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class ClothValidationReport:
    issues: list[ClothValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> tuple[ClothValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is ClothIssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ClothValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is ClothIssueSeverity.WARNING)

    @property
    def can_apply(self) -> bool:
        return not self.errors

    def add(self, code: str, message: str, *, severity: ClothIssueSeverity = ClothIssueSeverity.ERROR, entity_ids=()) -> None:
        self.issues.append(ClothValidationIssue(str(code), str(message), severity, tuple(str(value) for value in entity_ids)))


@dataclass(slots=True)
class ClothValidationCache:
    """Revision-keyed validation cache for interactive tools.

    Hover and cursor updates can happen dozens of times per second while the
    Cloth document itself stays unchanged.  Reusing the immutable report avoids
    repeatedly walking topology and sampling every arc on those events.
    """

    document_identity: int | None = None
    revision: int = -1
    report: ClothValidationReport | None = None

    def get(self, document: ClothDocument) -> ClothValidationReport:
        identity = id(document)
        revision = int(document.revision)
        if self.report is None or self.document_identity != identity or self.revision != revision:
            self.document_identity = identity
            self.revision = revision
            self.report = validate_cloth_document(document)
        return self.report

    def reset(self) -> None:
        self.document_identity = None
        self.revision = -1
        self.report = None


def _vector(first: Iterable[float], second: Iterable[float]) -> tuple[float, float, float]:
    a = tuple(float(value) for value in first)
    b = tuple(float(value) for value in second)
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _norm3(vector: Iterable[float]) -> float:
    values = tuple(float(value) for value in vector)
    return math.sqrt(sum(value * value for value in values))


def _cross3(a: Iterable[float], b: Iterable[float]) -> tuple[float, float, float]:
    ax, ay, az = tuple(float(value) for value in a)
    bx, by, bz = tuple(float(value) for value in b)
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def _arc_is_degenerate(document: ClothDocument, curve: ClothCurve) -> bool:
    if curve.kind is not ClothCurveKind.ARC or len(curve.point_ids) != 3:
        return False
    start = document.points[curve.point_ids[0]].position
    end = document.points[curve.point_ids[1]].position
    control = document.points[curve.point_ids[2]].position
    chord = _vector(start, end)
    to_control = _vector(start, control)
    chord_length = _norm3(chord)
    control_length = _norm3(to_control)
    if chord_length <= _EPS or control_length <= _EPS or distance3(control, end) <= _EPS:
        return True
    area_scale = _norm3(_cross3(chord, to_control))
    return area_scale <= 1.0e-8 * max(chord_length * control_length, 1.0)


def _orientation(a: Point2, b: Point2, c: Point2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(point: Point2, start: Point2, end: Point2, *, tolerance: float = 1.0e-8) -> bool:
    if abs(_orientation(start, end, point)) > tolerance:
        return False
    return (
        min(start[0], end[0]) - tolerance <= point[0] <= max(start[0], end[0]) + tolerance
        and min(start[1], end[1]) - tolerance <= point[1] <= max(start[1], end[1]) + tolerance
    )


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2, *, tolerance: float = 1.0e-8) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if ((o1 > tolerance and o2 < -tolerance) or (o1 < -tolerance and o2 > tolerance)) and (
        (o3 > tolerance and o4 < -tolerance) or (o3 < -tolerance and o4 > tolerance)
    ):
        return True
    return any(
        (
            abs(value) <= tolerance
            and _point_on_segment(point, start, end, tolerance=tolerance)
        )
        for value, point, start, end in (
            (o1, c, a, b),
            (o2, d, a, b),
            (o3, a, c, d),
            (o4, b, c, d),
        )
    )


def _clean_closed_polygon(points: Sequence[Point2]) -> tuple[Point2, ...]:
    cleaned: list[Point2] = []
    for point in points:
        value = (float(point[0]), float(point[1]))
        if cleaned and math.dist(cleaned[-1], value) <= _EPS:
            continue
        cleaned.append(value)
    if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) <= _EPS:
        cleaned.pop()
    return tuple(cleaned)


def _polygon_self_intersects(points: Sequence[Point2]) -> bool:
    polygon = _clean_closed_polygon(points)
    count = len(polygon)
    if count < 4:
        return False
    for first_index in range(count):
        a = polygon[first_index]
        b = polygon[(first_index + 1) % count]
        for second_index in range(first_index + 1, count):
            # Adjacent edges share a legitimate endpoint.  The first and last
            # edges are adjacent as well.
            if second_index in {first_index, (first_index + 1) % count}:
                continue
            if first_index == 0 and second_index == count - 1:
                continue
            c = polygon[second_index]
            d = polygon[(second_index + 1) % count]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _fold_cycle_issue(document: ClothDocument) -> tuple[str, ...] | None:
    parent: dict[str, str] = {patch_id: patch_id for patch_id in document.patches}

    def find(value: str) -> str:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            next_value = parent[value]
            parent[value] = root
            value = next_value
        return root

    for fold in document.folds.values():
        if fold.patch_a_id not in parent or fold.patch_b_id not in parent:
            continue
        first = find(fold.patch_a_id)
        second = find(fold.patch_b_id)
        if first == second:
            return (fold.id, fold.patch_a_id, fold.patch_b_id)
        parent[first] = second
    return None


def validate_cloth_document(
    document: ClothDocument,
    *,
    planarity_tolerance_mm: float = 1.0e-4,
    seam_length_relative_tolerance: float = 0.02,
) -> ClothValidationReport:
    report = ClothValidationReport()
    if not document.patches:
        report.add("cloth.no_faces", "Cloth needs at least one generated face before Apply.")

    for curve in document.curves.values():
        missing = [point_id for point_id in curve.point_ids if point_id not in document.points]
        if missing:
            report.add("cloth.curve.missing_point", f"Curve {curve.id} references missing points.", entity_ids=(curve.id, *missing))
            continue
        start_id, end_id = curve_endpoint_ids(curve)
        if not start_id or not end_id:
            report.add("cloth.curve.invalid_endpoints", f"Curve {curve.id} has invalid endpoints.", entity_ids=(curve.id,))
            continue
        if distance3(document.points[start_id].position, document.points[end_id].position) <= 1.0e-8:
            report.add("cloth.curve.degenerate", f"Curve {curve.id} has coincident endpoints.", entity_ids=(curve.id,))
        if curve.kind is ClothCurveKind.ARC:
            if len(curve.point_ids) != 3:
                report.add("cloth.arc.point_count", f"Arc {curve.id} must contain start, end and control points.", entity_ids=(curve.id,))
            elif _arc_is_degenerate(document, curve):
                report.add(
                    "cloth.arc.degenerate",
                    f"Arc {curve.id} needs a control point away from its chord to define a circular arc.",
                    entity_ids=(curve.id, *curve.point_ids),
                )

    seen_boundaries: dict[frozenset[str], str] = {}
    for patch in document.patches.values():
        missing = [curve_id for curve_id in patch.outer_curve_ids if curve_id not in document.curves]
        if missing:
            report.add("cloth.patch.missing_curve", f"Panel {patch.name} references missing curves.", entity_ids=(patch.id, *missing))
            continue
        boundary_key = frozenset(patch.outer_curve_ids)
        previous_patch = seen_boundaries.get(boundary_key)
        if previous_patch is not None:
            report.add(
                "cloth.patch.duplicate_boundary",
                f"Panel {patch.name} duplicates the boundary of another panel.",
                entity_ids=(previous_patch, patch.id),
            )
        else:
            seen_boundaries[boundary_key] = patch.id
        if order_curve_loop(document, patch.outer_curve_ids) is None:
            report.add("cloth.patch.open_boundary", f"Panel {patch.name} does not have one closed ordered boundary.", entity_ids=(patch.id,))
            continue
        frame = patch_frame(document, patch)
        if frame is None:
            report.add("cloth.patch.no_plane", f"Panel {patch.name} cannot define a stable local plane.", entity_ids=(patch.id,))
            continue
        max_deviation = max((frame.deviation(document.points[point_id].position) for point_id in patch_point_ids(document, patch)), default=0.0)
        if max_deviation > float(planarity_tolerance_mm):
            report.add(
                "cloth.patch.non_planar",
                f"Panel {patch.name} is not planar (maximum deviation {max_deviation:.6g} mm).",
                entity_ids=(patch.id,),
            )
        boundary = sample_patch_boundary(document, patch, arc_segments=32)
        projected = tuple(frame.project(point) for point in boundary)
        if _polygon_self_intersects(projected):
            report.add(
                "cloth.patch.self_intersection",
                f"Panel {patch.name} crosses itself. Move or split its boundary before creating the textile face.",
                entity_ids=(patch.id,),
            )
        if patch_area(document, patch) <= 1.0e-8:
            report.add("cloth.patch.zero_area", f"Panel {patch.name} has no usable surface area.", entity_ids=(patch.id,))
        if patch.hole_curve_loops:
            report.add(
                "cloth.patch.holes_unsupported",
                f"Panel {patch.name} contains holes. Cloth V1 cannot triangulate or unfold holes faithfully yet.",
                entity_ids=(patch.id,),
            )

    incidence = curve_patch_incidence(document)
    for curve_id, patch_ids in incidence.items():
        if len(patch_ids) > 2:
            report.add(
                "cloth.non_manifold_edge",
                f"Curve {curve_id} belongs to {len(patch_ids)} panels; a textile surface edge may belong to at most two.",
                entity_ids=(curve_id, *patch_ids),
            )

    seen_fold_curves: set[str] = set()
    for fold in document.folds.values():
        curve = document.curves.get(fold.curve_id)
        if curve is None:
            report.add("cloth.fold.missing_curve", f"Fold {fold.id} references a missing curve.", entity_ids=(fold.id, fold.curve_id))
            continue
        if curve.kind is not ClothCurveKind.LINE:
            report.add(
                "cloth.fold.not_straight",
                "V1 fold hinges must be straight lines. Curved creases will be represented later as segmented folds.",
                entity_ids=(fold.id, fold.curve_id),
            )
        expected = {fold.patch_a_id, fold.patch_b_id}
        actual = set(incidence.get(fold.curve_id, ()))
        if expected != actual:
            report.add(
                "cloth.fold.bad_incidence",
                f"Fold {fold.id} must be the shared boundary of exactly its two panels.",
                entity_ids=(fold.id, fold.curve_id, fold.patch_a_id, fold.patch_b_id),
            )
        if fold.curve_id in seen_fold_curves:
            report.add("cloth.fold.duplicate", f"Curve {fold.curve_id} has more than one fold relation.", entity_ids=(fold.curve_id,))
        seen_fold_curves.add(fold.curve_id)
        if not math.isfinite(fold.angle_degrees) or abs(fold.angle_degrees) > 180.0 + 1.0e-6:
            report.add("cloth.fold.angle", f"Fold {fold.id} angle must be between -180 and 180 degrees.", entity_ids=(fold.id,))

    cycle = _fold_cycle_issue(document)
    if cycle is not None:
        report.add(
            "cloth.fold.cycle_virtual_cut",
            (
                "The textile contains a closed fold cycle. The flat pattern will "
                "open it with non-destructive virtual cuts while preserving the 3D textile."
            ),
            severity=ClothIssueSeverity.WARNING,
            entity_ids=cycle,
        )

    for seam in document.seams.values():
        first = chain_length(document, seam.first_curve_ids)
        second = chain_length(document, seam.second_curve_ids) * seam.ease_ratio
        scale = max(first, second, 1.0e-9)
        mismatch = abs(first - second) / scale
        if mismatch > seam_length_relative_tolerance:
            report.add(
                "cloth.seam.length_mismatch",
                f"Seam {seam.id} chains differ by {mismatch * 100.0:.2f}% after ease.",
                severity=ClothIssueSeverity.WARNING,
                entity_ids=(seam.id,),
            )

    return report


__all__ = [
    "ClothIssueSeverity",
    "ClothValidationCache",
    "ClothValidationIssue",
    "ClothValidationReport",
    "validate_cloth_document",
]
