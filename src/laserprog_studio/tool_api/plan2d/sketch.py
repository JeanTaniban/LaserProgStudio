"""Public sketch facade for Plan 2D tools.

This module intentionally wraps the private ``tool_core.sketch`` document rather
than exposing it as the recommended API.  Built-in tools may still use the core
kernel directly while the public contract matures, but new Plan 2D tools should
start here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from laserprog_studio.tool_core.sketch import SketchCompileOptions as _SketchCompileOptions
from laserprog_studio.tool_core.sketch import SketchCompileResult as _SketchCompileResult
from laserprog_studio.tool_core.sketch import SketchDocument as _SketchDocument

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class PlanSketchCompileOptions:
    """Public topology-compile options for a Plan 2D sketch."""

    merge_tolerance: float = 1.0e-5
    split_tolerance: float = 1.0e-5
    min_edge_length: float = 1.0e-8
    solve_faces: bool = True

    def _to_core(self) -> _SketchCompileOptions:
        return _SketchCompileOptions(
            merge_tolerance=float(self.merge_tolerance),
            split_tolerance=float(self.split_tolerance),
            min_edge_length=float(self.min_edge_length),
            solve_faces=bool(self.solve_faces),
        )


@dataclass(frozen=True, slots=True)
class PlanSketchCompileResult:
    """Public summary returned after topology normalization."""

    merged_points: int = 0
    split_lines: int = 0
    intersection_points: int = 0
    curve_intersection_points: int = 0
    split_arcs: int = 0
    split_circles: int = 0
    removed_degenerate_edges: int = 0
    rebuilt_polylines: int = 0
    rebuilt_faces: int = 0
    validation_issues: int = 0
    changed: bool = False
    notes: tuple[str, ...] = ()

    @classmethod
    def from_core(cls, result: _SketchCompileResult) -> "PlanSketchCompileResult":
        return cls(
            merged_points=int(result.merged_points),
            split_lines=int(result.split_lines),
            intersection_points=int(result.intersection_points),
            curve_intersection_points=int(result.curve_intersection_points),
            split_arcs=int(result.split_arcs),
            split_circles=int(result.split_circles),
            removed_degenerate_edges=int(result.removed_degenerate_edges),
            rebuilt_polylines=int(result.rebuilt_polylines),
            rebuilt_faces=int(result.rebuilt_faces),
            validation_issues=int(result.validation_issues),
            changed=bool(result.changed),
            notes=tuple(str(note) for note in result.notes),
        )


class PlanSketch:
    """Small public builder around the private 2D sketch kernel."""

    def __init__(self, document: _SketchDocument | None = None) -> None:
        self._document = document or _SketchDocument()

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(self._document.points)

    @property
    def line_ids(self) -> tuple[str, ...]:
        return tuple(self._document.lines)

    @property
    def arc_ids(self) -> tuple[str, ...]:
        return tuple(self._document.arcs)

    @property
    def circle_ids(self) -> tuple[str, ...]:
        return tuple(self._document.circles)

    @property
    def face_ids(self) -> tuple[str, ...]:
        return tuple(self._document.faces)

    @property
    def document(self) -> _SketchDocument:
        """Return the internal document for built-in migration code.

        This is an escape hatch, not the recommended surface for external tools.
        Prefer the builder methods above when possible.
        """

        return self._document

    def clone(self) -> "PlanSketch":
        return PlanSketch(self._document.clone())

    def add_point(self, position: Point2, *, point_id: str | None = None) -> str:
        return self._document.add_point(position, point_id=point_id).id

    def move_point(self, point_id: str, position: Point2) -> bool:
        return self._document.move_point(point_id, position)

    def add_line(self, start_point_id: str, end_point_id: str, *, line_id: str | None = None) -> str:
        return self._document.add_line(start_point_id, end_point_id, line_id=line_id).id

    def add_arc(self, start_point_id: str, end_point_id: str, control_point_id: str, *, arc_id: str | None = None) -> str:
        return self._document.add_arc(start_point_id, end_point_id, control_point_id, arc_id=arc_id).id

    def add_circle(self, center_point_id: str, radius_point_id: str, *, circle_id: str | None = None) -> str:
        return self._document.add_circle(center_point_id, radius_point_id, circle_id=circle_id).id

    def delete_entity(self, entity_id: str) -> bool:
        return self._document.delete_entity(entity_id)

    def compile(self, options: PlanSketchCompileOptions | None = None) -> PlanSketchCompileResult:
        core_options = None if options is None else options._to_core()
        return PlanSketchCompileResult.from_core(self._document.compile(core_options))

    def entity_counts(self) -> dict[str, int]:
        return {
            "points": len(self._document.points),
            "lines": len(self._document.lines),
            "arcs": len(self._document.arcs),
            "circles": len(self._document.circles),
            "faces": len(self._document.faces),
            "polylines": len(self._document.polylines),
            "dimensions": len(self._document.dimensions),
        }


def create_sketch() -> PlanSketch:
    """Create an empty public Plan 2D sketch builder."""

    return PlanSketch()


def wrap_core_sketch(document: Any) -> PlanSketch:
    """Wrap an existing core sketch document during built-in migration."""

    if not isinstance(document, _SketchDocument):
        raise TypeError("wrap_core_sketch expects a tool_core.sketch.SketchDocument")
    return PlanSketch(document)


__all__ = [
    "PlanSketch",
    "PlanSketchCompileOptions",
    "PlanSketchCompileResult",
    "Point2",
    "create_sketch",
    "wrap_core_sketch",
]
