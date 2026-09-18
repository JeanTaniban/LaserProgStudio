"""Detect closed 2D faces, including holes, from independent sketch entities."""
from __future__ import annotations

from dataclasses import dataclass

from .document import SketchDocument, face_signature_from_points
from ..geometry import (
    circle_from_two_points,
    distance_2d,
    line_circle_intersections,
    point_on_circle,
    polygon_area,
    remove_consecutive_duplicates,
    sample_circle,
    sample_circular_arc_through_points,
    sample_cubic_bezier,
)

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class FaceSolveOptions:
    join_tolerance: float = 0.25
    min_area: float = 1e-4
    circle_segments: int = 72
    arc_segments: int = 24
    bezier_segments: int = 48


@dataclass(slots=True)
class _NodeCluster:
    id: int
    position: Point2
    point_ids: list[str]


@dataclass(frozen=True, slots=True)
class _Edge:
    entity_id: str
    a: int
    b: int
    samples_ab: tuple[Point2, ...]

    def samples_from(self, node_id: int) -> tuple[Point2, ...]:
        if node_id == self.a:
            return self.samples_ab
        return tuple(reversed(self.samples_ab))


@dataclass(frozen=True, slots=True)
class _LoopCandidate:
    boundary_entity_ids: tuple[str, ...]
    polygon_points: tuple[Point2, ...]
    signed_area: float
    signature: str

    @property
    def abs_area(self) -> float:
        return abs(float(self.signed_area))


class FaceSolver:
    def __init__(self, options: FaceSolveOptions | None = None) -> None:
        self.options = options or FaceSolveOptions()

    def solve(self, sketch: SketchDocument) -> tuple[str, ...]:
        # First try the arrangement-based solver.  It nodes the complete 2D
        # linework before polygonizing, so combinations such as circle/line,
        # circle/rectangle-edge, line/circle and circle/circle are handled by one
        # path instead of by brittle one-off candidates.  The small candidate
        # walker below remains as an alternate path for environments without Shapely.
        arrangement_error: Exception | None = None
        try:
            from .arrangement_faces import ArrangementFaceOptions, solve_faces_from_arrangement

            return solve_faces_from_arrangement(
                sketch,
                ArrangementFaceOptions(
                    join_tolerance=self.options.join_tolerance,
                    min_area=self.options.min_area,
                    circle_segments=self.options.circle_segments,
                    arc_segments=self.options.arc_segments,
                ),
            )
        except Exception as exc:
            # Keep the dependency-free fallback available, but never make an
            # arrangement regression completely silent again.  The v86 build
            # had lost three timing helpers, so every solve raised NameError and
            # Plan Tracer quietly used the incomplete legacy candidate solver.
            arrangement_error = exc
            _record_arrangement_fallback(exc)
            sketch.faces.clear()
        candidates = self._collect_candidates(sketch)
        if not candidates:
            return ()
        created = tuple(self._build_faces_with_holes(sketch, candidates))
        if arrangement_error is not None:
            for face_id in created:
                face = sketch.faces.get(face_id)
                if face is not None:
                    face.metadata["arrangement_fallback_error"] = type(arrangement_error).__name__
        return created

    # ------------------------------------------------------------------
    # Candidate collection
    # ------------------------------------------------------------------
    def _collect_candidates(self, sketch: SketchDocument) -> list[_LoopCandidate]:
        candidates: list[_LoopCandidate] = []
        candidates.extend(self._circle_candidates(sketch))
        candidates.extend(self._edge_loop_candidates(sketch))
        candidates.extend(self._circle_chord_region_candidates(sketch))
        candidates = self._deduplicate_candidates(candidates)
        return self._remove_partition_container_candidates(candidates)

    def _circle_candidates(self, sketch: SketchDocument) -> list[_LoopCandidate]:
        candidates: list[_LoopCandidate] = []
        for circle in sketch.circles.values():
            center = sketch.points[circle.center_point_id].position
            radius_point = sketch.points[circle.radius_point_id].position
            radius = distance_2d(center, radius_point)
            points = tuple(sample_circle(center, radius, segments=self.options.circle_segments))
            area = polygon_area(list(points))
            if len(points) >= 3 and abs(area) >= self.options.min_area:
                candidates.append(_LoopCandidate((circle.id,), points, area, face_signature_from_points(points)))
        return candidates


    def _circle_chord_region_candidates(self, sketch: SketchDocument) -> list[_LoopCandidate]:
        """Return local regions made when straight edges traverse circles.

        Live Plan Tracer deliberately keeps authored circles intact while the user
        edits, so the compiler no longer destructively turns a circle into many
        arcs whenever a rectangle edge crosses it.  Face solving still needs the
        *topological* split though: a line crossing a circle creates two closed
        circle regions bounded by one circular arc and the chord segment between
        the two intersection points.  Build those regions virtually here, without
        mutating ``sketch.circles`` or ``sketch.lines``.
        """

        import math

        candidates: list[_LoopCandidate] = []
        tolerance = max(float(self.options.join_tolerance), 1.0e-7)
        for circle in sketch.circles.values():
            center = sketch.points.get(circle.center_point_id)
            radius_point = sketch.points.get(circle.radius_point_id)
            if center is None or radius_point is None:
                continue
            circle2 = circle_from_two_points(center.position, radius_point.position)
            if circle2 is None:
                continue
            for line in sketch.lines.values():
                start = sketch.points.get(line.start_point_id)
                end = sketch.points.get(line.end_point_id)
                if start is None or end is None:
                    continue
                hits = line_circle_intersections(start.position, end.position, circle2, tolerance=tolerance)
                # Tangency does not split a circular region.  Two distinct crossings
                # define a chord and therefore two selectable faces.
                hits = [(point, t) for point, t in hits if tolerance < t < 1.0 - tolerance]
                if len(hits) < 2:
                    continue
                hits.sort(key=lambda item: item[1])
                # A line can theoretically cross only twice, but keep the pairwise
                # logic defensive for future curve import paths.
                for (p0, _t0), (p1, _t1) in zip(hits, hits[1:]):
                    if distance_2d(p0, p1) <= tolerance:
                        continue
                    a0 = math.atan2(p0[1] - circle2.center[1], p0[0] - circle2.center[0])
                    a1 = math.atan2(p1[1] - circle2.center[1], p1[0] - circle2.center[0])
                    ccw = (a1 - a0) % math.tau
                    if ccw <= 1.0e-8 or abs(ccw - math.tau) <= 1.0e-8:
                        continue
                    for index, (start_angle, sweep, chord_start, chord_end) in enumerate(
                        (
                            (a0, ccw, p1, p0),
                            (a1, math.tau - ccw, p0, p1),
                        )
                    ):
                        segments = max(8, int(round(self.options.circle_segments * (sweep / math.tau))))
                        arc_points = [point_on_circle(circle2.center, circle2.radius, start_angle + sweep * (i / segments)) for i in range(segments + 1)]
                        polygon = [*arc_points, chord_start, chord_end]
                        polygon = remove_consecutive_duplicates(polygon, tolerance)
                        area = polygon_area(polygon)
                        if len(polygon) < 3 or abs(area) < self.options.min_area:
                            continue
                        points = tuple(polygon)
                        # Include the split side in the signature so the two halves
                        # of the same circle+line pair cannot collapse together.
                        signature = face_signature_from_points(points)
                        candidates.append(_LoopCandidate((circle.id, line.id), points, area, signature))
        return candidates

    def _edge_loop_candidates(self, sketch: SketchDocument) -> list[_LoopCandidate]:
        clusters = self._cluster_endpoints(sketch)
        point_to_cluster = {point_id: cluster.id for cluster in clusters for point_id in cluster.point_ids}
        edges = self._build_edges(sketch, point_to_cluster)
        candidates: list[_LoopCandidate] = []
        for loop_edges, polygon in self._directed_face_loops(edges):
            self._append_loop_candidate(candidates, loop_edges, polygon)
        for loop_edges, polygon in self._arc_chord_loop_candidates(sketch, edges):
            self._append_loop_candidate(candidates, loop_edges, polygon)
        return candidates

    def _append_loop_candidate(self, candidates: list[_LoopCandidate], loop_edges: list[str], polygon: list[Point2]) -> None:
        polygon = remove_consecutive_duplicates(polygon, self.options.join_tolerance)
        area = polygon_area(polygon)
        if len(loop_edges) >= 2 and len(set(loop_edges)) == len(loop_edges) and len(polygon) >= 3 and abs(area) >= self.options.min_area:
            points = tuple(polygon)
            candidates.append(_LoopCandidate(tuple(loop_edges), points, area, face_signature_from_points(points)))

    def _arc_chord_loop_candidates(self, sketch: SketchDocument, edges: list[_Edge]) -> list[tuple[list[str], list[Point2]]]:
        arc_edges = [edge for edge in edges if edge.entity_id in sketch.arcs]
        line_edges = [edge for edge in edges if edge.entity_id in sketch.lines]
        if not arc_edges or not line_edges:
            return []
        line_adjacency: dict[int, list[_Edge]] = {}
        for edge in line_edges:
            line_adjacency.setdefault(edge.a, []).append(edge)
            line_adjacency.setdefault(edge.b, []).append(edge)
        loops: list[tuple[list[str], list[Point2]]] = []
        for arc in arc_edges:
            path = self._line_path_between(line_adjacency, arc.b, arc.a)
            if not path:
                continue
            polygon = list(arc.samples_from(arc.a))
            loop_ids = [arc.entity_id]
            current = arc.b
            for line_edge in path:
                samples = list(line_edge.samples_from(current))
                if samples:
                    polygon.extend(samples[1:])
                loop_ids.append(line_edge.entity_id)
                current = line_edge.b if line_edge.a == current else line_edge.a
            if current == arc.a:
                loops.append((loop_ids, polygon))
        return loops

    def _line_path_between(self, adjacency: dict[int, list[_Edge]], start: int, goal: int) -> list[_Edge]:
        from collections import deque

        queue = deque([(start, [])])
        visited = {start}
        while queue:
            node, path = queue.popleft()
            if node == goal:
                return path
            for edge in adjacency.get(node, []):
                nxt = edge.b if edge.a == node else edge.a
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append((nxt, [*path, edge]))
        return []

    def _directed_face_loops(self, edges: list[_Edge]) -> list[tuple[list[str], list[Point2]]]:
        """Walk the planar graph by directed half-edges.

        Unlike the former one-pass walker, this can discover adjacent faces that
        share curve pieces, for example a circle split by a chord into two curved
        regions.  Each directed edge owns one side of a possible face.
        """

        import math

        adjacency: dict[int, list[tuple[str, int, float]]] = {}
        edge_by_directed: dict[tuple[str, int, int], _Edge] = {}
        for edge in edges:
            if edge.a == edge.b:
                continue
            pa = edge.samples_from(edge.a)[0]
            pb = edge.samples_from(edge.a)[-1]
            angle_ab = math.atan2(pb[1] - pa[1], pb[0] - pa[0])
            angle_ba = math.atan2(pa[1] - pb[1], pa[0] - pb[0])
            adjacency.setdefault(edge.a, []).append((edge.entity_id, edge.b, angle_ab))
            adjacency.setdefault(edge.b, []).append((edge.entity_id, edge.a, angle_ba))
            edge_by_directed[(edge.entity_id, edge.a, edge.b)] = edge
            edge_by_directed[(edge.entity_id, edge.b, edge.a)] = edge
        for outgoing in adjacency.values():
            outgoing.sort(key=lambda item: item[2])

        visited: set[tuple[str, int, int]] = set()
        loops: list[tuple[list[str], list[Point2]]] = []
        directed_edges = list(edge_by_directed.keys())
        for start_key in directed_edges:
            if start_key in visited:
                continue
            current_key = start_key
            loop_edge_ids: list[str] = []
            polygon: list[Point2] = []
            seen_in_loop: set[tuple[str, int, int]] = set()
            guard = 0
            while guard < 10000:
                guard += 1
                if current_key in seen_in_loop:
                    if current_key == start_key and len(loop_edge_ids) >= 2:
                        loops.append((loop_edge_ids, polygon))
                    break
                seen_in_loop.add(current_key)
                visited.add(current_key)
                edge_id, node_a, node_b = current_key
                edge = edge_by_directed.get(current_key)
                if edge is None:
                    break
                samples = list(edge.samples_from(node_a))
                if not polygon:
                    polygon.extend(samples)
                elif samples:
                    polygon.extend(samples[1:])
                loop_edge_ids.append(edge_id)
                outgoing = adjacency.get(node_b, [])
                if not outgoing:
                    break
                reverse_index = None
                for index, (candidate_edge_id, candidate_to, _angle) in enumerate(outgoing):
                    if candidate_edge_id == edge_id and candidate_to == node_a:
                        reverse_index = index
                        break
                if reverse_index is None:
                    break
                # Choose the previous edge in angular order. This traces the face
                # consistently on one side of the current half-edge.
                next_edge_id, next_to, _next_angle = outgoing[(reverse_index - 1) % len(outgoing)]
                current_key = (next_edge_id, node_b, next_to)
        return loops

    def _remove_partition_container_candidates(self, candidates: list[_LoopCandidate]) -> list[_LoopCandidate]:
        """Drop union loops when smaller loops share their boundary and partition it.

        A circle split by a chord produces three valid cycles: the full circle and
        the two chord-bounded regions.  The full circle is not a separate face in
        that topology; it is the union of its child regions.  True holes are not
        affected because their boundaries are disjoint from the outer loop.
        """

        remove_signatures: set[str] = set()
        for outer in candidates:
            outer_boundary = set(outer.boundary_entity_ids)
            if not outer_boundary:
                continue
            children = [
                candidate
                for candidate in candidates
                if candidate.signature != outer.signature
                and candidate.abs_area < outer.abs_area - self.options.min_area
                and outer_boundary.intersection(candidate.boundary_entity_ids)
                and _loop_contains_loop(outer.polygon_points, candidate.polygon_points)
            ]
            if len(children) < 2:
                continue
            child_area = sum(child.abs_area for child in children)
            if child_area >= outer.abs_area * 0.92:
                remove_signatures.add(outer.signature)
        return [candidate for candidate in candidates if candidate.signature not in remove_signatures]

    @staticmethod
    def _deduplicate_candidates(candidates: list[_LoopCandidate]) -> list[_LoopCandidate]:
        by_signature: dict[str, _LoopCandidate] = {}
        for candidate in candidates:
            existing = by_signature.get(candidate.signature)
            if existing is None or len(candidate.boundary_entity_ids) < len(existing.boundary_entity_ids):
                by_signature[candidate.signature] = candidate
        return list(by_signature.values())

    # ------------------------------------------------------------------
    # Hole-aware face building
    # ------------------------------------------------------------------
    def _build_faces_with_holes(self, sketch: SketchDocument, candidates: list[_LoopCandidate]) -> list[str]:
        """Build non-overlapping sketch regions from nested closed loops.

        A loop is not a single filled island by itself once another loop is
        drawn inside it.  In an interactive sketch editor, the user expects two
        selectable regions in the simple case ``outer rectangle + inner
        rectangle``: the outer ring and the inner island.  Deleting the inner
        island then leaves a true hole, and restoring generated faces can fill it
        again.  Therefore every loop becomes one region, clipped by only its
        immediate children.  This creates adjacent regions that share boundary
        edges instead of visually stacking full filled polygons on top of each
        other.
        """

        ordered = sorted(candidates, key=lambda item: item.abs_area, reverse=True)
        depth_for: dict[str, int] = {}
        parent_for: dict[str, str | None] = {}

        for candidate in ordered:
            containers = [
                other
                for other in ordered
                if other.signature != candidate.signature
                and other.abs_area > candidate.abs_area + self.options.min_area
                and _loop_contains_loop(other.polygon_points, candidate.polygon_points)
            ]
            containers.sort(key=lambda item: item.abs_area)
            parent = containers[0] if containers else None
            parent_for[candidate.signature] = parent.signature if parent is not None else None
            depth_for[candidate.signature] = len(containers)

        created: list[str] = []
        for region in ordered:
            children = [
                candidate
                for candidate in ordered
                if parent_for[candidate.signature] == region.signature
            ]
            children.sort(key=lambda item: item.abs_area, reverse=True)
            hole_polygons = tuple(candidate.polygon_points for candidate in children)
            hole_boundary_ids = tuple(candidate.boundary_entity_ids for candidate in children)
            signature = face_signature_from_points(region.polygon_points, hole_polygons=hole_polygons)
            face = sketch.add_face(
                region.boundary_entity_ids,
                region.polygon_points,
                signature=signature,
                hole_polygons=hole_polygons,
                hole_boundary_entity_ids=hole_boundary_ids,
            )
            if face is None:
                continue
            face.metadata["hole_count"] = len(hole_polygons)
            face.metadata["contains_holes"] = bool(hole_polygons)
            face.metadata["containment_depth"] = depth_for[region.signature]
            parent_signature = parent_for[region.signature]
            if parent_signature is not None:
                face.metadata["generated_from_hole"] = True
                face.metadata["hole_parent_signature"] = parent_signature
            created.append(face.id)
        return created

    def _cluster_endpoints(self, sketch: SketchDocument) -> list[_NodeCluster]:
        endpoint_ids: list[str] = []
        for line in sketch.lines.values():
            endpoint_ids.extend([line.start_point_id, line.end_point_id])
        for arc in sketch.arcs.values():
            endpoint_ids.extend([arc.start_point_id, arc.end_point_id])
        for bezier in getattr(sketch, "beziers", {}).values():
            endpoint_ids.extend([bezier.start_point_id, bezier.end_point_id])
        clusters: list[_NodeCluster] = []
        for point_id in endpoint_ids:
            pos = sketch.points[point_id].position
            found: _NodeCluster | None = None
            for cluster in clusters:
                if distance_2d(cluster.position, pos) <= self.options.join_tolerance:
                    found = cluster
                    break
            if found is None:
                clusters.append(_NodeCluster(len(clusters), pos, [point_id]))
            else:
                found.point_ids.append(point_id)
                count = len(found.point_ids)
                found.position = (
                    (found.position[0] * (count - 1) + pos[0]) / count,
                    (found.position[1] * (count - 1) + pos[1]) / count,
                )
        return clusters

    def _build_edges(self, sketch: SketchDocument, point_to_cluster: dict[str, int]) -> list[_Edge]:
        edges: list[_Edge] = []
        for line in sketch.lines.values():
            a = point_to_cluster[line.start_point_id]
            b = point_to_cluster[line.end_point_id]
            if a == b:
                continue
            start = sketch.points[line.start_point_id].position
            end = sketch.points[line.end_point_id].position
            edges.append(_Edge(line.id, a, b, (start, end)))
        for arc in sketch.arcs.values():
            a = point_to_cluster[arc.start_point_id]
            b = point_to_cluster[arc.end_point_id]
            if a == b:
                continue
            start = sketch.points[arc.start_point_id].position
            end = sketch.points[arc.end_point_id].position
            control = sketch.points[arc.control_point_id].position
            samples = tuple(sample_circular_arc_through_points(start, end, control, segments=self.options.arc_segments))
            edges.append(_Edge(arc.id, a, b, samples))
        for bezier in getattr(sketch, "beziers", {}).values():
            a = point_to_cluster[bezier.start_point_id]
            b = point_to_cluster[bezier.end_point_id]
            if a == b:
                continue
            start = sketch.points[bezier.start_point_id].position
            end = sketch.points[bezier.end_point_id].position
            control_1 = sketch.points[bezier.control_1_point_id].position
            control_2 = sketch.points[bezier.control_2_point_id].position
            samples = tuple(sample_cubic_bezier(start, control_1, control_2, end, segments=self.options.bezier_segments))
            edges.append(_Edge(bezier.id, a, b, samples))
        return edges

    def _walk_loop(
        self,
        start_edge: _Edge,
        adjacency: dict[int, list[_Edge]],
        visited: set[str],
    ) -> tuple[list[str], list[Point2]]:
        start_node = start_edge.a
        current_node = start_edge.b
        previous_edge_id = start_edge.entity_id
        loop_edges = [start_edge.entity_id]
        polygon = list(start_edge.samples_from(start_node))
        visited.add(start_edge.entity_id)
        guard = 0
        while guard < 10000:
            guard += 1
            if current_node == start_node:
                return loop_edges, polygon
            options = [edge for edge in adjacency.get(current_node, []) if edge.entity_id != previous_edge_id]
            unvisited = [edge for edge in options if edge.entity_id not in visited]
            if not unvisited:
                return [], []
            next_edge = unvisited[0]
            segment_samples = list(next_edge.samples_from(current_node))
            if segment_samples:
                polygon.extend(segment_samples[1:])
            visited.add(next_edge.entity_id)
            loop_edges.append(next_edge.entity_id)
            previous_edge_id = next_edge.entity_id
            current_node = next_edge.b if next_edge.a == current_node else next_edge.a
        return [], []


def _record_arrangement_fallback(exc: Exception) -> None:
    """Expose unexpected arrangement failures only while debug mode is active."""

    try:
        from laserprog_studio.services.debug_mode import is_debug_mode_enabled

        if not bool(is_debug_mode_enabled()):
            return
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.increment("sketch.face_solver.arrangement_fallback")
        audit.set_value("sketch.face_solver.arrangement_fallback.last_error", type(exc).__name__)
    except Exception:
        pass


def _loop_contains_loop(outer: tuple[Point2, ...], inner: tuple[Point2, ...]) -> bool:
    if len(outer) < 3 or len(inner) < 3:
        return False
    # The centroid can fall outside for concave loops.  Use the first non-boundary
    # sample that is inside.  Candidate loops in the Plan Tracer are simple closed
    # contours, so one interior sample is enough for containment classification.
    for point in inner:
        if _point_in_polygon(point, outer, boundary_counts=False):
            return True
    cx = sum(point[0] for point in inner) / len(inner)
    cy = sum(point[1] for point in inner) / len(inner)
    return _point_in_polygon((cx, cy), outer, boundary_counts=False)


def _point_in_polygon(point: Point2, polygon: tuple[Point2, ...] | list[Point2], *, boundary_counts: bool = True) -> bool:
    px, py = float(point[0]), float(point[1])
    inside = False
    pts = list(polygon)
    if len(pts) < 3:
        return False
    j = len(pts) - 1
    for i, current in enumerate(pts):
        xi, yi = float(current[0]), float(current[1])
        xj, yj = float(pts[j][0]), float(pts[j][1])
        if _distance_to_segment((px, py), (xi, yi), (xj, yj)) <= 1.0e-7:
            return boundary_counts
        intersects = (yi > py) != (yj > py)
        if intersects:
            x_cross = (xj - xi) * (py - yi) / ((yj - yi) or 1.0e-12) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def _distance_to_segment(p: Point2, a: Point2, b: Point2) -> float:
    import math

    px, py = float(p[0]), float(p[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1.0e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    hx, hy = ax + t * dx, ay + t * dy
    return math.hypot(px - hx, py - hy)
