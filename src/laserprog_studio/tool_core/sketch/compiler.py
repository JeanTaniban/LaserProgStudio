"""Topology compiler for the canonical 2D sketch document.

The compiler turns loose construction entities into a normalized planar graph:

* duplicate vertices are merged;
* every vertex lying on a line splits that line;
* line connectivity is rebuilt into polylines;
* closed loops are passed to the face solver.

It intentionally stays UI-free so the Plan tracer, tests and future tools can
share the same invariants instead of duplicating fragile per-tool logic.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from math import atan2, cos, floor, hypot, sin
import time

from laserprog_studio.tool_core.geometry import (
    Arc2,
    Circle2,
    arc_arc_intersections,
    arc_from_three_points,
    circle_arc_intersections,
    circle_circle_intersections,
    circle_from_two_points,
    control_point_for_arc_segment,
    line_arc_intersections,
    line_circle_intersections,
)

from .entities import SketchArc, SketchLine, SketchPolyline

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class SketchCompileOptions:
    merge_tolerance: float = 1.0e-5
    split_tolerance: float = 1.0e-5
    min_edge_length: float = 1.0e-8
    solve_faces: bool = True
    split_curve_intersections: bool = True
    split_curves_at_vertices: bool = True


@dataclass(slots=True)
class SketchCompileResult:
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
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Projection:
    t: float
    distance: float


class SketchCompiler:
    def __init__(self, options: SketchCompileOptions | None = None) -> None:
        self.options = options or SketchCompileOptions()

    def compile(self, sketch) -> SketchCompileResult:
        timings_enabled = _compile_timing_enabled()
        compile_started = time.perf_counter() if timings_enabled else 0.0
        result = SketchCompileResult()
        result.merged_points = self._timed_phase("merge_duplicate_points", self.merge_duplicate_points, sketch)
        result.removed_degenerate_edges += self._timed_phase("remove_degenerate_lines.initial", self.remove_degenerate_lines, sketch)
        result.intersection_points = self._timed_phase("insert_line_intersections", self.insert_line_intersection_points, sketch)
        if self.options.split_curve_intersections:
            result.curve_intersection_points = self._timed_phase(
                "insert_curve_intersections", self.insert_curve_intersection_points, sketch
            )
        result.split_lines = self._timed_phase("split_lines_at_vertices", self.split_lines_at_vertices, sketch)
        if self.options.split_curves_at_vertices:
            result.split_arcs = self._timed_phase("split_arcs_at_vertices", self.split_arcs_at_vertices, sketch)
            result.split_circles = self._timed_phase("split_circles_at_vertices", self.split_circles_at_vertices, sketch)
        result.removed_degenerate_edges += self._timed_phase("remove_degenerate_lines.final", self.remove_degenerate_lines, sketch)
        result.removed_degenerate_edges += self._timed_phase("remove_degenerate_curves", self.remove_degenerate_curves, sketch)
        result.removed_degenerate_edges += self._timed_phase("remove_duplicate_lines", self.remove_duplicate_lines, sketch)
        result.rebuilt_polylines = self._timed_phase("rebuild_polylines", self.rebuild_polylines, sketch)
        if self.options.solve_faces:
            try:
                from .face_solver import FaceSolveOptions, FaceSolver

                solver = FaceSolver(
                    FaceSolveOptions(
                        join_tolerance=max(float(self.options.merge_tolerance), float(self.options.split_tolerance)),
                    )
                )
                created = self._timed_phase("solve_faces", solver.solve, sketch)
                result.rebuilt_faces = len(created)
            except Exception as exc:  # pragma: no cover - defensive for host tools
                sketch.faces.clear()
                result.notes.append(f"face_solve_failed:{type(exc).__name__}")
        else:
            sketch.faces.clear()
        self._timed_phase("validation", self._attach_validation_notes, sketch, result)
        result.changed = any(
            value
            for value in (
                result.merged_points,
                result.split_lines,
                result.intersection_points,
                result.curve_intersection_points,
                result.split_arcs,
                result.split_circles,
                result.removed_degenerate_edges,
                result.rebuilt_polylines,
                result.rebuilt_faces,
            )
        )
        if timings_enabled:
            _record_compile_timing("total", (time.perf_counter() - compile_started) * 1000.0)
        return result

    @staticmethod
    def _timed_phase(name: str, callback, *args):
        if not _compile_timing_enabled():
            return callback(*args)
        started = time.perf_counter()
        try:
            return callback(*args)
        finally:
            _record_compile_timing(str(name), (time.perf_counter() - started) * 1000.0)

    def _attach_validation_notes(self, sketch, result: SketchCompileResult) -> None:
        """Append compact validation diagnostics without making compile UI-aware."""

        try:
            from .validation import validate_sketch

            report = validate_sketch(sketch, min_edge_length=self.options.min_edge_length)
        except Exception as exc:  # pragma: no cover - defensive for host tools
            result.notes.append(f"validation_failed:{type(exc).__name__}")
            return
        result.validation_issues = len(report.issues)
        result.notes.extend(report.compact_notes())

    # ------------------------------------------------------------------
    # Point / line normalization
    # ------------------------------------------------------------------
    def merge_duplicate_points(self, sketch) -> int:
        tolerance = max(float(self.options.merge_tolerance), 0.0)
        if tolerance <= 0.0 or len(sketch.points) < 2:
            return 0
        point_ids = list(sketch.points.keys())
        canonical_for: dict[str, str] = {}
        # Duplicate merging used to compare every point against every following
        # point (O(P²)).  A tolerance-sized spatial hash preserves the same
        # "earliest surviving point wins" semantics while limiting comparisons
        # to the 3x3 neighborhood that can possibly contain a duplicate.
        cell_size = tolerance
        cells: dict[tuple[int, int], list[tuple[int, str]]] = {}
        removed = 0
        for index, point_id in enumerate(point_ids):
            point = sketch.points.get(point_id)
            if point is None:
                continue
            cx, cy = _spatial_cell(point.position, cell_size)
            best: tuple[int, str] | None = None
            for nx in range(cx - 1, cx + 2):
                for ny in range(cy - 1, cy + 2):
                    for canonical_index, canonical_id in cells.get((nx, ny), ()):
                        canonical = sketch.points.get(canonical_id)
                        if canonical is None or _distance(canonical.position, point.position) > tolerance:
                            continue
                        if best is None or canonical_index < best[0]:
                            best = (canonical_index, canonical_id)
            if best is not None:
                canonical_for[point_id] = best[1]
                continue
            cells.setdefault((cx, cy), []).append((index, point_id))
        if not canonical_for:
            return 0
        for line in sketch.lines.values():
            line.start_point_id = canonical_for.get(line.start_point_id, line.start_point_id)
            line.end_point_id = canonical_for.get(line.end_point_id, line.end_point_id)
        for arc in sketch.arcs.values():
            arc.start_point_id = canonical_for.get(arc.start_point_id, arc.start_point_id)
            arc.end_point_id = canonical_for.get(arc.end_point_id, arc.end_point_id)
            arc.control_point_id = canonical_for.get(arc.control_point_id, arc.control_point_id)
        for bezier in getattr(sketch, "beziers", {}).values():
            bezier.start_point_id = canonical_for.get(bezier.start_point_id, bezier.start_point_id)
            bezier.end_point_id = canonical_for.get(bezier.end_point_id, bezier.end_point_id)
            bezier.control_1_point_id = canonical_for.get(bezier.control_1_point_id, bezier.control_1_point_id)
            bezier.control_2_point_id = canonical_for.get(bezier.control_2_point_id, bezier.control_2_point_id)
        for circle in sketch.circles.values():
            circle.center_point_id = canonical_for.get(circle.center_point_id, circle.center_point_id)
            circle.radius_point_id = canonical_for.get(circle.radius_point_id, circle.radius_point_id)
        for duplicate_id in canonical_for:
            if duplicate_id in sketch.points:
                sketch.points.pop(duplicate_id, None)
                removed += 1
        if removed:
            sketch.faces.clear()
            sketch.polylines.clear()
        return removed

    def insert_line_intersection_points(self, sketch) -> int:
        """Create real vertices where two line edges cross.

        This keeps the core invariant true: once compiled, a crossing is no
        longer just a visual overlap.  The following ``split_lines_at_vertices``
        pass then turns both original lines into connected line pieces.
        """

        tolerance = max(float(self.options.split_tolerance), 0.0)
        if tolerance <= 0.0 or len(sketch.lines) < 2:
            return 0
        inserted = 0
        lines = list(sketch.lines.items())
        # Broad-phase sweep: only line pairs with overlapping screen-independent
        # 2D bounding boxes can intersect.  The old nested loop tested every
        # pair, which made a large collection of unrelated rectangles quadratic.
        records: list[tuple[float, float, float, float, int]] = []
        for line_index, (_line_id, line) in enumerate(lines):
            start = sketch.points.get(line.start_point_id)
            end = sketch.points.get(line.end_point_id)
            if start is None or end is None:
                continue
            min_x = min(float(start.position[0]), float(end.position[0]))
            max_x = max(float(start.position[0]), float(end.position[0]))
            min_y = min(float(start.position[1]), float(end.position[1]))
            max_y = max(float(start.position[1]), float(end.position[1]))
            records.append((min_x, max_x, min_y, max_y, line_index))
        records.sort(key=lambda item: (item[0], item[4]))
        active: list[tuple[float, float, float, float, int]] = []
        candidate_pairs: set[tuple[int, int]] = set()
        for record in records:
            min_x, _max_x, min_y, max_y, line_index = record
            active = [other for other in active if other[1] + tolerance >= min_x]
            for other in active:
                if other[3] + tolerance < min_y or max_y + tolerance < other[2]:
                    continue
                first_index, second_index = sorted((int(other[4]), int(line_index)))
                candidate_pairs.add((first_index, second_index))
            active.append(record)

        for index, second_index in sorted(candidate_pairs):
            first_id, first = lines[index]
            if first_id not in sketch.lines:
                continue
            first_start = sketch.points.get(first.start_point_id)
            first_end = sketch.points.get(first.end_point_id)
            if first_start is None or first_end is None:
                continue
            second_id, second = lines[second_index]
            if second_id not in sketch.lines:
                continue
            if {first.start_point_id, first.end_point_id} & {second.start_point_id, second.end_point_id}:
                continue
            second_start = sketch.points.get(second.start_point_id)
            second_end = sketch.points.get(second.end_point_id)
            if second_start is None or second_end is None:
                continue
            hit = _segment_intersection(first_start.position, first_end.position, second_start.position, second_end.position)
            if hit is None:
                continue
            point, t_first, t_second = hit
            if not (tolerance < t_first < 1.0 - tolerance and tolerance < t_second < 1.0 - tolerance):
                continue
            if self._find_point_near(sketch, point, tolerance) is not None:
                continue
            new_point = sketch.add_point(point)
            new_point.metadata.update({"generated_by": "line_intersection", "source_lines": (first_id, second_id)})
            inserted += 1
        if inserted:
            sketch.faces.clear()
            sketch.polylines.clear()
        return inserted

    def insert_curve_intersection_points(self, sketch) -> int:
        """Create real vertices at line/curve and curve/curve crossings."""

        tolerance = max(float(self.options.split_tolerance), 0.0)
        if tolerance <= 0.0:
            return 0
        inserted = 0
        lines = list(sketch.lines.items())
        circles = [(circle_id, self._circle2_for(sketch, circle_id)) for circle_id in list(sketch.circles)]
        circles = [(circle_id, circle) for circle_id, circle in circles if circle is not None]
        arcs = [(arc_id, self._arc2_for(sketch, arc_id)) for arc_id in list(sketch.arcs)]
        arcs = [(arc_id, arc) for arc_id, arc in arcs if arc is not None]

        def add_hit(point: Point2, *, generated_by: str, sources: tuple[str, ...]) -> None:
            nonlocal inserted
            existing = self._find_point_near(sketch, point, tolerance)
            if existing is not None:
                sketch.points[existing].metadata.setdefault("curve_intersection_sources", sources)
                sketch.points[existing].metadata["force_arc_split"] = True
                return
            new_point = sketch.add_point(point)
            new_point.metadata.update({"generated_by": generated_by, "source_entities": sources})
            inserted += 1

        for line_id, line in lines:
            if line_id not in sketch.lines:
                continue
            start = sketch.points.get(line.start_point_id)
            end = sketch.points.get(line.end_point_id)
            if start is None or end is None:
                continue
            for circle_id, circle in circles:
                for point, t_line in line_circle_intersections(start.position, end.position, circle, tolerance=tolerance):
                    if tolerance < t_line < 1.0 - tolerance:
                        add_hit(point, generated_by="line_circle_intersection", sources=(line_id, circle_id))
            for arc_id, arc in arcs:
                for point, t_line, t_arc in line_arc_intersections(start.position, end.position, arc, tolerance=tolerance):
                    if tolerance < t_line < 1.0 - tolerance and tolerance < t_arc < 1.0 - tolerance:
                        add_hit(point, generated_by="line_arc_intersection", sources=(line_id, arc_id))

        for index, (first_id, first) in enumerate(circles):
            for second_id, second in circles[index + 1 :]:
                for point in circle_circle_intersections(first, second, tolerance=tolerance):
                    add_hit(point, generated_by="circle_circle_intersection", sources=(first_id, second_id))
            for arc_id, arc in arcs:
                for point, t_arc in circle_arc_intersections(first, arc, tolerance=tolerance):
                    if tolerance < t_arc < 1.0 - tolerance:
                        add_hit(point, generated_by="circle_arc_intersection", sources=(first_id, arc_id))

        for index, (first_id, first) in enumerate(arcs):
            for second_id, second in arcs[index + 1 :]:
                for point, t_first, t_second in arc_arc_intersections(first, second, tolerance=tolerance):
                    if tolerance < t_first < 1.0 - tolerance and tolerance < t_second < 1.0 - tolerance:
                        add_hit(point, generated_by="arc_arc_intersection", sources=(first_id, second_id))
        if inserted:
            sketch.faces.clear()
            sketch.polylines.clear()
        return inserted

    def _find_point_near(self, sketch, point: Point2, tolerance: float) -> str | None:
        for point_id, existing in sketch.points.items():
            if _distance(existing.position, point) <= tolerance:
                return point_id
        return None

    def split_lines_at_vertices(self, sketch) -> int:
        split_count = 0
        tolerance = max(float(self.options.split_tolerance), 0.0)
        if tolerance <= 0.0 or not sketch.lines or len(sketch.points) < 3:
            return 0
        # Query candidate vertices by the line's X-range rather than projecting
        # every sketch point onto every line.  Exact distance/t checks below are
        # unchanged, so this is only a broad phase and cannot alter topology.
        point_records = sorted(
            (float(point.position[0]), float(point.position[1]), str(point_id))
            for point_id, point in sketch.points.items()
        )
        point_xs = [record[0] for record in point_records]
        for line_id, line in list(sketch.lines.items()):
            if line_id not in sketch.lines:
                continue
            start = sketch.points.get(line.start_point_id)
            end = sketch.points.get(line.end_point_id)
            if start is None or end is None:
                sketch.lines.pop(line_id, None)
                continue
            split_points: list[tuple[float, str]] = []
            min_x = min(float(start.position[0]), float(end.position[0])) - tolerance
            max_x = max(float(start.position[0]), float(end.position[0])) + tolerance
            min_y = min(float(start.position[1]), float(end.position[1])) - tolerance
            max_y = max(float(start.position[1]), float(end.position[1])) + tolerance
            lo = bisect_left(point_xs, min_x)
            hi = bisect_right(point_xs, max_x)
            for point_index in range(lo, hi):
                _px, py, point_id = point_records[point_index]
                if point_id in {line.start_point_id, line.end_point_id}:
                    continue
                if py < min_y or py > max_y:
                    continue
                point = sketch.points.get(point_id)
                if point is None:
                    continue
                projection = _project_point_on_segment(point.position, start.position, end.position)
                if projection.distance <= tolerance and 1.0e-9 < projection.t < 1.0 - 1.0e-9:
                    split_points.append((projection.t, point_id))
            if not split_points:
                continue
            split_points.sort(key=lambda item: item[0])
            ordered_point_ids = [line.start_point_id]
            for _t, point_id in split_points:
                if point_id != ordered_point_ids[-1]:
                    ordered_point_ids.append(point_id)
            if ordered_point_ids[-1] != line.end_point_id:
                ordered_point_ids.append(line.end_point_id)
            metadata = {**line.metadata, "split_from_line_id": line.metadata.get("split_from_line_id", line.id)}
            sketch.remove_dimensions_referencing({line_id})
            sketch.lines.pop(line_id, None)
            created = 0
            for a, b in zip(ordered_point_ids, ordered_point_ids[1:]):
                if a == b:
                    continue
                if _distance(sketch.points[a].position, sketch.points[b].position) <= self.options.min_edge_length:
                    continue
                entity = SketchLine(sketch.new_id("l"), a, b, dict(metadata))
                sketch.lines[entity.id] = entity
                created += 1
            if created:
                split_count += 1
        if split_count:
            sketch.faces.clear()
            sketch.polylines.clear()
        return split_count

    def split_arcs_at_vertices(self, sketch) -> int:
        """Split explicit arcs when existing vertices lie on their curve."""

        tolerance = max(float(self.options.split_tolerance), 0.0)
        if tolerance <= 0.0 or not sketch.arcs:
            return 0
        split_count = 0
        for arc_id, arc_entity in list(sketch.arcs.items()):
            if arc_id not in sketch.arcs:
                continue
            arc = self._arc2_for(sketch, arc_id)
            if arc is None:
                continue
            split_points: list[tuple[float, str]] = []
            for point_id, point in sketch.points.items():
                if point_id in {arc_entity.start_point_id, arc_entity.end_point_id}:
                    continue
                if point_id == arc_entity.control_point_id and not bool(point.metadata.get("force_arc_split")):
                    continue
                t = arc.parameter_for_point(point.position, tolerance=tolerance)
                if t is not None and 1.0e-8 < t < 1.0 - 1.0e-8:
                    split_points.append((t, point_id))
            if not split_points:
                continue
            split_points.sort(key=lambda item: item[0])
            point_chain = [(0.0, arc_entity.start_point_id), *split_points, (1.0, arc_entity.end_point_id)]
            metadata = {**arc_entity.metadata, "split_from_arc_id": arc_entity.metadata.get("split_from_arc_id", arc_entity.id)}
            sketch.remove_dimensions_referencing({arc_id})
            sketch.arcs.pop(arc_id, None)
            created = 0
            for (t0, start_id), (t1, end_id) in zip(point_chain, point_chain[1:]):
                if start_id == end_id:
                    continue
                start = sketch.points[start_id].position
                end = sketch.points[end_id].position
                if _distance(start, end) <= self.options.min_edge_length:
                    continue
                control_pos = control_point_for_arc_segment(arc, t0, t1)
                control = sketch.add_point(control_pos)
                control.metadata.update({"generated_by": "arc_split_control", "hidden_control": True, "source_arc_id": arc_id})
                entity = SketchArc(sketch.new_id("a"), start_id, end_id, control.id, dict(metadata))
                sketch.arcs[entity.id] = entity
                created += 1
            if created:
                split_count += 1
        if split_count:
            sketch.faces.clear()
            sketch.polylines.clear()
        return split_count

    def split_circles_at_vertices(self, sketch) -> int:
        """Turn intersected circles into arc edges so faces can use them."""

        tolerance = max(float(self.options.split_tolerance), 0.0)
        if tolerance <= 0.0 or not sketch.circles:
            return 0
        split_count = 0
        for circle_id, circle_entity in list(sketch.circles.items()):
            if circle_id not in sketch.circles:
                continue
            circle = self._circle2_for(sketch, circle_id)
            if circle is None:
                continue
            angle_points: list[tuple[float, str]] = []
            for point_id, point in sketch.points.items():
                if point_id == circle_entity.center_point_id:
                    continue
                if abs(_distance(point.position, circle.center) - circle.radius) <= tolerance:
                    angle = _angle_for_point(circle.center, point.position)
                    if all(_distance(point.position, sketch.points[existing_id].position) > tolerance for _a, existing_id in angle_points):
                        angle_points.append((angle, point_id))
            if len(angle_points) < 2:
                continue
            angle_points.sort(key=lambda item: item[0])
            metadata = {**circle_entity.metadata, "split_from_circle_id": circle_entity.metadata.get("split_from_circle_id", circle_entity.id)}
            sketch.circles.pop(circle_id, None)
            sketch.remove_dimensions_referencing({circle_id})
            created = 0
            chain = angle_points + [(angle_points[0][0] + 6.283185307179586, angle_points[0][1])]
            for (angle0, start_id), (angle1, end_id) in zip(chain, chain[1:]):
                if start_id == end_id:
                    continue
                sweep = angle1 - angle0
                if sweep <= 1.0e-8:
                    continue
                mid_angle = angle0 + sweep * 0.5
                control_pos = (
                    circle.center[0] + circle.radius * cos(mid_angle),
                    circle.center[1] + circle.radius * sin(mid_angle),
                )
                control = sketch.add_point(control_pos)
                control.metadata.update({"generated_by": "circle_split_control", "hidden_control": True, "source_circle_id": circle_id})
                entity = SketchArc(sketch.new_id("a"), start_id, end_id, control.id, dict(metadata))
                sketch.arcs[entity.id] = entity
                created += 1
            if created:
                split_count += 1
        if split_count:
            sketch.faces.clear()
            sketch.polylines.clear()
        return split_count

    def remove_degenerate_lines(self, sketch) -> int:
        removed = 0
        for line_id, line in list(sketch.lines.items()):
            start = sketch.points.get(line.start_point_id)
            end = sketch.points.get(line.end_point_id)
            if start is None or end is None or line.start_point_id == line.end_point_id or _distance(start.position, end.position) <= self.options.min_edge_length:
                sketch.lines.pop(line_id, None)
                removed += 1
        if removed:
            sketch.faces.clear()
            sketch.polylines.clear()
        return removed

    def remove_degenerate_curves(self, sketch) -> int:
        removed = 0
        for arc_id, arc in list(sketch.arcs.items()):
            start = sketch.points.get(arc.start_point_id)
            end = sketch.points.get(arc.end_point_id)
            control = sketch.points.get(arc.control_point_id)
            if (
                start is None
                or end is None
                or control is None
                or arc.start_point_id == arc.end_point_id
                or _distance(start.position, end.position) <= self.options.min_edge_length
                or self._arc2_for(sketch, arc_id) is None
            ):
                sketch.arcs.pop(arc_id, None)
                removed += 1
        for bezier_id, bezier in list(getattr(sketch, "beziers", {}).items()):
            start = sketch.points.get(bezier.start_point_id)
            end = sketch.points.get(bezier.end_point_id)
            control_1 = sketch.points.get(bezier.control_1_point_id)
            control_2 = sketch.points.get(bezier.control_2_point_id)
            if (
                start is None
                or end is None
                or control_1 is None
                or control_2 is None
                or bezier.start_point_id == bezier.end_point_id
                or _distance(start.position, end.position) <= self.options.min_edge_length
            ):
                sketch.beziers.pop(bezier_id, None)
                removed += 1
        for circle_id, circle in list(sketch.circles.items()):
            center = sketch.points.get(circle.center_point_id)
            radius_point = sketch.points.get(circle.radius_point_id)
            if center is None or radius_point is None or _distance(center.position, radius_point.position) <= self.options.min_edge_length:
                sketch.circles.pop(circle_id, None)
                sketch.remove_dimensions_referencing({circle_id})
                removed += 1
        if removed:
            sketch.faces.clear()
            sketch.polylines.clear()
        return removed

    def remove_duplicate_lines(self, sketch) -> int:
        seen: dict[frozenset[str], str] = {}
        removed = 0
        for line_id, line in list(sketch.lines.items()):
            key = frozenset((line.start_point_id, line.end_point_id))
            if len(key) < 2:
                continue
            if key in seen:
                sketch.lines.pop(line_id, None)
                removed += 1
            else:
                seen[key] = line_id
        if removed:
            sketch.faces.clear()
            sketch.polylines.clear()
        return removed

    # ------------------------------------------------------------------
    # Polyline rebuild
    # ------------------------------------------------------------------
    def rebuild_polylines(self, sketch) -> int:
        sketch.polylines.clear()
        adjacency: dict[str, list[str]] = {}
        edge_endpoints: dict[str, tuple[str, str]] = {}
        for line_id, line in sketch.lines.items():
            edge_endpoints[line_id] = (line.start_point_id, line.end_point_id)
        for arc_id, arc in sketch.arcs.items():
            edge_endpoints[arc_id] = (arc.start_point_id, arc.end_point_id)
        for bezier_id, bezier in getattr(sketch, "beziers", {}).items():
            edge_endpoints[bezier_id] = (bezier.start_point_id, bezier.end_point_id)
        for edge_id, (start_id, end_id) in edge_endpoints.items():
            adjacency.setdefault(start_id, []).append(edge_id)
            adjacency.setdefault(end_id, []).append(edge_id)
        visited: set[str] = set()
        polylines: list[SketchPolyline] = []

        # Prefer chain starts at endpoints or branching vertices. Closed loops
        # where every degree is 2 are picked up in the second pass below.
        start_vertices = sorted(adjacency, key=lambda pid: (len(adjacency[pid]) == 2, pid))
        for start in start_vertices:
            if len(adjacency[start]) == 2:
                continue
            for edge_id in list(adjacency[start]):
                if edge_id in visited:
                    continue
                poly = self._walk_polyline(sketch, start, edge_id, adjacency, edge_endpoints, visited)
                if poly is not None:
                    polylines.append(poly)
        for edge_id, (start_id, _end_id) in list(edge_endpoints.items()):
            if edge_id in visited:
                continue
            poly = self._walk_polyline(sketch, start_id, edge_id, adjacency, edge_endpoints, visited)
            if poly is not None:
                polylines.append(poly)
        for circle_id, circle in sketch.circles.items():
            center = sketch.points.get(circle.center_point_id)
            radius_point = sketch.points.get(circle.radius_point_id)
            if center is None or radius_point is None:
                continue
            if _distance(center.position, radius_point.position) <= self.options.min_edge_length:
                continue
            polylines.append(
                SketchPolyline(
                    id=sketch.new_id("pl"),
                    edge_ids=(circle_id,),
                    point_ids=(circle.center_point_id, circle.radius_point_id),
                    closed=True,
                    recognized_shape="circle",
                    metadata={"curve_type": "circle"},
                )
            )
        for poly in polylines:
            sketch.polylines[poly.id] = poly
        return len(polylines)

    def _walk_polyline(
        self,
        sketch,
        start_point_id: str,
        first_edge_id: str,
        adjacency: dict[str, list[str]],
        edge_endpoints: dict[str, tuple[str, str]],
        visited: set[str],
    ) -> SketchPolyline | None:
        point_ids = [start_point_id]
        edge_ids: list[str] = []
        current = start_point_id
        edge_id = first_edge_id
        guard = 0
        while guard < 10000:
            guard += 1
            if edge_id in visited or edge_id not in edge_endpoints:
                break
            start_id, end_id = edge_endpoints[edge_id]
            visited.add(edge_id)
            edge_ids.append(edge_id)
            nxt = end_id if start_id == current else start_id
            point_ids.append(nxt)
            current = nxt
            if current == start_point_id:
                break
            # Stop chains at endpoints and branches. For degree-2 vertices, keep
            # walking through the only unvisited continuation.
            candidates = [candidate for candidate in adjacency.get(current, ()) if candidate not in visited]
            if len(adjacency.get(current, ())) != 2 or not candidates:
                break
            edge_id = candidates[0]
        if not edge_ids or len(point_ids) < 2:
            return None
        closed = len(point_ids) > 2 and point_ids[0] == point_ids[-1]
        arc_count = sum(1 for edge_id in edge_ids if edge_id in sketch.arcs)
        circle_like = closed and arc_count and len(edge_ids) == 2 and any(
            getattr(sketch.lines.get(edge_id), "metadata", {}).get("generated_by") == "half_circle_diameter" for edge_id in edge_ids
        )
        return SketchPolyline(
            id=sketch.new_id("pl"),
            edge_ids=tuple(edge_ids),
            point_ids=tuple(point_ids),
            closed=closed,
            recognized_shape="half_circle" if circle_like else ("closed_loop" if closed else ("arc" if arc_count and len(edge_ids) == 1 else "free")),
            metadata={"curve_count": arc_count} if arc_count else {},
        )


    def _circle2_for(self, sketch, circle_id: str) -> Circle2 | None:
        circle = sketch.circles.get(circle_id)
        if circle is None:
            return None
        center = sketch.points.get(circle.center_point_id)
        radius_point = sketch.points.get(circle.radius_point_id)
        if center is None or radius_point is None:
            return None
        return circle_from_two_points(center.position, radius_point.position, min_radius=self.options.min_edge_length)

    def _arc2_for(self, sketch, arc_id: str) -> Arc2 | None:
        arc = sketch.arcs.get(arc_id)
        if arc is None:
            return None
        start = sketch.points.get(arc.start_point_id)
        end = sketch.points.get(arc.end_point_id)
        control = sketch.points.get(arc.control_point_id)
        if start is None or end is None or control is None:
            return None
        return arc_from_three_points(start.position, end.position, control.position, min_radius=self.options.min_edge_length)


# ----------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------


def _angle_for_point(center: Point2, point: Point2) -> float:
    value = atan2(float(point[1]) - float(center[1]), float(point[0]) - float(center[0]))
    if value < 0.0:
        value += 6.283185307179586
    return value


def _segment_intersection(a: Point2, b: Point2, c: Point2, d: Point2) -> tuple[Point2, float, float] | None:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    dx, dy = float(d[0]), float(d[1])
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    denom = rx * sy - ry * sx
    if abs(denom) <= 1.0e-12:
        return None
    qpx, qpy = cx - ax, cy - ay
    t = (qpx * sy - qpy * sx) / denom
    u = (qpx * ry - qpy * rx) / denom
    if t < -1.0e-9 or t > 1.0 + 1.0e-9 or u < -1.0e-9 or u > 1.0 + 1.0e-9:
        return None
    t = max(0.0, min(1.0, t))
    u = max(0.0, min(1.0, u))
    return (ax + rx * t, ay + ry * t), t, u


def _distance(a: Point2, b: Point2) -> float:
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _spatial_cell(point: Point2, cell_size: float) -> tuple[int, int]:
    size = max(float(cell_size), 1.0e-15)
    return (floor(float(point[0]) / size), floor(float(point[1]) / size))


def _project_point_on_segment(point: Point2, start: Point2, end: Point2) -> _Projection:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1.0e-16:
        return _Projection(0.0, _distance(point, start))
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    hx, hy = ax + dx * t, ay + dy * t
    return _Projection(t, hypot(px - hx, py - hy))


def _compile_timing_enabled() -> bool:
    try:
        from laserprog_studio.services.debug_mode import is_debug_mode_enabled
        return bool(is_debug_mode_enabled())
    except Exception:
        return False


def _record_compile_timing(name: str, elapsed_ms: float) -> None:
    """Publish phase timings without making the sketch kernel depend on the UI."""

    if not _compile_timing_enabled():
        return
    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.record_timing(f"sketch.compile.{name}", float(elapsed_ms))
    except Exception:
        pass


__all__ = ["SketchCompileOptions", "SketchCompileResult", "SketchCompiler"]
