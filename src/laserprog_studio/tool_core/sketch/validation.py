"""Validation helpers for the pure sketch-kernel topology.

The compiler is allowed to normalize geometry aggressively, but it should leave
behind a coherent document.  This module keeps those checks separate from the
compiler so validation can be used by tests, diagnostics and future developer
HUDs without pulling UI code into the sketch kernel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import hypot

from laserprog_studio.tool_core.dimensions import DimensionReferenceType
from laserprog_studio.tool_core.geometry import arc_from_three_points, circle_from_two_points

Point2 = tuple[float, float]


class SketchValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SketchValidationIssue:
    """One non-fatal or fatal sketch-kernel invariant issue."""

    code: str
    message: str
    entity_type: str = "sketch"
    entity_id: str | None = None
    severity: SketchValidationSeverity = SketchValidationSeverity.ERROR


@dataclass(slots=True)
class SketchValidationReport:
    """Validation result for one sketch document."""

    issues: list[SketchValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity is SketchValidationSeverity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is SketchValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is SketchValidationSeverity.WARNING)

    def add(
        self,
        code: str,
        message: str,
        *,
        entity_type: str = "sketch",
        entity_id: str | None = None,
        severity: SketchValidationSeverity = SketchValidationSeverity.ERROR,
    ) -> None:
        self.issues.append(
            SketchValidationIssue(
                code=str(code),
                message=str(message),
                entity_type=str(entity_type),
                entity_id=None if entity_id is None else str(entity_id),
                severity=severity,
            )
        )

    def compact_notes(self, *, limit: int = 8) -> list[str]:
        """Return short compiler-friendly validation notes."""

        notes = []
        for issue in self.issues[: max(0, int(limit))]:
            target = f":{issue.entity_type}:{issue.entity_id}" if issue.entity_id else f":{issue.entity_type}"
            notes.append(f"validation_{issue.severity.value}:{issue.code}{target}")
        if len(self.issues) > limit:
            notes.append(f"validation_truncated:{len(self.issues) - limit}")
        return notes


def validate_sketch(sketch, *, min_edge_length: float = 1.0e-8, validate_generated: bool = True) -> SketchValidationReport:
    """Validate references and basic geometry invariants in a sketch.

    The function is intentionally conservative: it reports broken references,
    zero-length primitives and impossible curve definitions, but it does not
    reject open polylines or unused construction points because those are valid
    while the user is drawing.
    """

    report = SketchValidationReport()
    _validate_lines(sketch, report, min_edge_length=float(min_edge_length))
    _validate_arcs(sketch, report, min_edge_length=float(min_edge_length))
    _validate_beziers(sketch, report, min_edge_length=float(min_edge_length))
    _validate_circles(sketch, report, min_edge_length=float(min_edge_length))
    _validate_polylines(sketch, report)
    _validate_faces(sketch, report)
    _validate_dimensions(sketch, report)
    if validate_generated:
        _validate_hidden_controls(sketch, report)
    return report


def assert_sketch_valid(sketch, *, min_edge_length: float = 1.0e-8) -> None:
    """Raise ``AssertionError`` with compact details when a sketch is invalid."""

    report = validate_sketch(sketch, min_edge_length=min_edge_length)
    if not report.ok:
        raise AssertionError("; ".join(report.compact_notes(limit=16)))


def _validate_lines(sketch, report: SketchValidationReport, *, min_edge_length: float) -> None:
    for line_id, line in sketch.lines.items():
        start = sketch.points.get(line.start_point_id)
        end = sketch.points.get(line.end_point_id)
        if start is None:
            report.add("line_missing_start", "Line start point is missing", entity_type="line", entity_id=line_id)
        if end is None:
            report.add("line_missing_end", "Line end point is missing", entity_type="line", entity_id=line_id)
        if start is not None and end is not None and _distance(start.position, end.position) <= min_edge_length:
            report.add("line_degenerate", "Line has zero or near-zero length", entity_type="line", entity_id=line_id)


def _validate_arcs(sketch, report: SketchValidationReport, *, min_edge_length: float) -> None:
    for arc_id, arc in sketch.arcs.items():
        start = sketch.points.get(arc.start_point_id)
        end = sketch.points.get(arc.end_point_id)
        control = sketch.points.get(arc.control_point_id)
        if start is None:
            report.add("arc_missing_start", "Arc start point is missing", entity_type="arc", entity_id=arc_id)
        if end is None:
            report.add("arc_missing_end", "Arc end point is missing", entity_type="arc", entity_id=arc_id)
        if control is None:
            report.add("arc_missing_control", "Arc control point is missing", entity_type="arc", entity_id=arc_id)
        if start is None or end is None or control is None:
            continue
        if _distance(start.position, end.position) <= min_edge_length:
            report.add("arc_degenerate", "Arc endpoints are coincident", entity_type="arc", entity_id=arc_id)
        if arc_from_three_points(start.position, end.position, control.position, min_radius=min_edge_length) is None:
            report.add("arc_invalid", "Arc points do not define a valid circular arc", entity_type="arc", entity_id=arc_id)


def _validate_beziers(sketch, report: SketchValidationReport, *, min_edge_length: float) -> None:
    for bezier_id, bezier in getattr(sketch, "beziers", {}).items():
        point_ids = (
            bezier.start_point_id,
            bezier.end_point_id,
            bezier.control_1_point_id,
            bezier.control_2_point_id,
        )
        points = [sketch.points.get(point_id) for point_id in point_ids]
        labels = ("start", "end", "control_1", "control_2")
        for label, point in zip(labels, points):
            if point is None:
                report.add(
                    f"bezier_missing_{label}",
                    f"Bezier {label} point is missing",
                    entity_type="bezier",
                    entity_id=bezier_id,
                )
        if points[0] is not None and points[1] is not None and _distance(points[0].position, points[1].position) <= min_edge_length:
            report.add("bezier_degenerate", "Bezier endpoints are coincident", entity_type="bezier", entity_id=bezier_id)


def _validate_circles(sketch, report: SketchValidationReport, *, min_edge_length: float) -> None:
    for circle_id, circle in sketch.circles.items():
        center = sketch.points.get(circle.center_point_id)
        radius_point = sketch.points.get(circle.radius_point_id)
        if center is None:
            report.add("circle_missing_center", "Circle center point is missing", entity_type="circle", entity_id=circle_id)
        if radius_point is None:
            report.add("circle_missing_radius_point", "Circle radius point is missing", entity_type="circle", entity_id=circle_id)
        if center is not None and radius_point is not None:
            if circle_from_two_points(center.position, radius_point.position, min_radius=min_edge_length) is None:
                report.add("circle_degenerate", "Circle radius is zero or near-zero", entity_type="circle", entity_id=circle_id)


def _validate_polylines(sketch, report: SketchValidationReport) -> None:
    for polyline_id, polyline in sketch.polylines.items():
        if len(polyline.edge_ids) < 1:
            report.add("polyline_empty", "Polyline has no edges", entity_type="polyline", entity_id=polyline_id)
        for edge_id in polyline.edge_ids:
            if edge_id not in sketch.lines and edge_id not in sketch.arcs and edge_id not in getattr(sketch, "beziers", {}) and edge_id not in sketch.circles:
                report.add("polyline_missing_edge", "Polyline references a missing edge/curve", entity_type="polyline", entity_id=polyline_id)
        for point_id in polyline.point_ids:
            if point_id not in sketch.points:
                report.add("polyline_missing_point", "Polyline references a missing point", entity_type="polyline", entity_id=polyline_id)


def _validate_faces(sketch, report: SketchValidationReport) -> None:
    for face_id, face in sketch.faces.items():
        if len(face.polygon_points) < 3:
            report.add("face_invalid_outer", "Face outer loop has fewer than three points", entity_type="face", entity_id=face_id)
        for entity_id in face.boundary_entity_ids:
            if entity_id not in sketch.lines and entity_id not in sketch.arcs and entity_id not in getattr(sketch, "beziers", {}) and entity_id not in sketch.circles:
                report.add("face_missing_boundary", "Face references a missing boundary entity", entity_type="face", entity_id=face_id)
        for hole_index, hole in enumerate(face.hole_polygons):
            if len(hole) < 3:
                report.add("face_invalid_hole", f"Face hole {hole_index} has fewer than three points", entity_type="face", entity_id=face_id)
        for hole_boundary in face.hole_boundary_entity_ids:
            for entity_id in hole_boundary:
                if entity_id not in sketch.lines and entity_id not in sketch.arcs and entity_id not in getattr(sketch, "beziers", {}) and entity_id not in sketch.circles:
                    report.add("face_missing_hole_boundary", "Face hole references a missing boundary entity", entity_type="face", entity_id=face_id)


def _validate_dimensions(sketch, report: SketchValidationReport) -> None:
    for dimension_id, dimension in sketch.dimensions.items():
        if not dimension.references:
            report.add("dimension_missing_references", "Dimension has no references", entity_type="dimension", entity_id=dimension_id)
            continue
        for reference in dimension.references:
            ref_type = reference.normalized_type() if hasattr(reference, "normalized_type") else str(reference.type)
            mapping = {
                DimensionReferenceType.POINT.value: sketch.points,
                DimensionReferenceType.LINE.value: sketch.lines,
                DimensionReferenceType.ARC.value: sketch.arcs,
                DimensionReferenceType.CIRCLE.value: sketch.circles,
            }.get(ref_type)
            if mapping is None:
                report.add("dimension_unknown_reference_type", f"Unknown dimension reference type: {ref_type}", entity_type="dimension", entity_id=dimension_id)
            elif reference.id not in mapping:
                report.add("dimension_missing_reference", f"Dimension reference is missing: {ref_type}:{reference.id}", entity_type="dimension", entity_id=dimension_id)


def _validate_hidden_controls(sketch, report: SketchValidationReport) -> None:
    """Warn when generated curve-control points lost their owning curve.

    Hidden control points are implementation details. They may be left unused for
    a short time during editing, so this is a warning rather than an error.
    """

    arc_control_ids = {arc.control_point_id for arc in sketch.arcs.values()}
    for point_id, point in sketch.points.items():
        if point.metadata.get("hidden_control") and point_id not in arc_control_ids:
            report.add(
                "hidden_control_orphan",
                "Generated hidden control point is no longer used by an arc",
                entity_type="point",
                entity_id=point_id,
                severity=SketchValidationSeverity.WARNING,
            )


def _distance(a: Point2, b: Point2) -> float:
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


__all__ = [
    "SketchValidationIssue",
    "SketchValidationReport",
    "SketchValidationSeverity",
    "assert_sketch_valid",
    "validate_sketch",
]
