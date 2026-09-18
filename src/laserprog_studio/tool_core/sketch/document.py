"""Pure 2D sketch document. No UI, no renderer, no PyVista."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from laserprog_studio.tool_core.dimensions import DimensionKind, DimensionReference, DimensionReferenceType

from .entities import SketchArc, SketchBezier, SketchCircle, SketchDimension, SketchFace, SketchLine, SketchPoint, SketchPolyline

Point2 = tuple[float, float]


@dataclass(slots=True)
class SketchDocument:
    points: dict[str, SketchPoint] = field(default_factory=dict)
    lines: dict[str, SketchLine] = field(default_factory=dict)
    arcs: dict[str, SketchArc] = field(default_factory=dict)
    beziers: dict[str, SketchBezier] = field(default_factory=dict)
    circles: dict[str, SketchCircle] = field(default_factory=dict)
    faces: dict[str, SketchFace] = field(default_factory=dict)
    polylines: dict[str, SketchPolyline] = field(default_factory=dict)
    dimensions: dict[str, SketchDimension] = field(default_factory=dict)
    suppressed_face_signatures: set[str] = field(default_factory=set)
    # Generated face ids are stable per geometric signature.  The face solver
    # clears/rebuilds derived faces after topology edits; retaining this small
    # mapping prevents every unchanged face from receiving a new id and being
    # removed/recreated in Projected Drawing 2D on each compile.
    face_ids_by_signature: dict[str, str] = field(default_factory=dict)
    _next_id: int = 1

    def clone(self) -> "SketchDocument":
        """Return a detached snapshot-friendly copy of this sketch.

        The previous implementation used ``deepcopy(self)``.  That is convenient
        but extremely expensive for CAD-sized sketches because ``deepcopy`` walks
        every immutable coordinate/id tuple and repeatedly dispatches through the
        generic copy protocol.  Plan Tracer history takes snapshots on normal edit
        operations, so a dense sketch could spend hundreds of milliseconds copying
        data after a single Delete.

        Sketch geometry is mostly immutable scalar/tuple data.  Copy the mutable
        entity records and metadata dictionaries explicitly while sharing immutable
        tuples (coordinates, ids, polygon rings, dimension references).  The clone
        is still fully detached for every field that live editing can mutate.
        """

        def metadata_copy(value):
            return {} if not value else deepcopy(value)

        return SketchDocument(
            points={
                key: SketchPoint(item.id, item.position, metadata_copy(item.metadata))
                for key, item in self.points.items()
            },
            lines={
                key: SketchLine(item.id, item.start_point_id, item.end_point_id, metadata_copy(item.metadata))
                for key, item in self.lines.items()
            },
            arcs={
                key: SketchArc(
                    item.id,
                    item.start_point_id,
                    item.end_point_id,
                    item.control_point_id,
                    metadata_copy(item.metadata),
                )
                for key, item in self.arcs.items()
            },
            beziers={
                key: SketchBezier(
                    item.id,
                    item.start_point_id,
                    item.end_point_id,
                    item.control_1_point_id,
                    item.control_2_point_id,
                    metadata_copy(item.metadata),
                )
                for key, item in self.beziers.items()
            },
            circles={
                key: SketchCircle(
                    item.id,
                    item.center_point_id,
                    item.radius_point_id,
                    metadata_copy(item.metadata),
                )
                for key, item in self.circles.items()
            },
            faces={
                key: SketchFace(
                    item.id,
                    item.boundary_entity_ids,
                    item.polygon_points,
                    item.hole_polygons,
                    item.hole_boundary_entity_ids,
                    metadata_copy(item.metadata),
                )
                for key, item in self.faces.items()
            },
            polylines={
                key: SketchPolyline(
                    item.id,
                    item.edge_ids,
                    item.point_ids,
                    item.closed,
                    item.recognized_shape,
                    metadata_copy(item.metadata),
                )
                for key, item in self.polylines.items()
            },
            dimensions={
                key: SketchDimension(
                    item.id,
                    item.kind,
                    item.references,
                    offset=item.offset,
                    label_position=item.label_position,
                    driving=item.driving,
                    value_override=item.value_override,
                    style=type(item.style)(
                        color_role=item.style.color_role,
                        passive=item.style.passive,
                        text_size_px=item.style.text_size_px,
                        show_witness_lines=item.style.show_witness_lines,
                        show_arrow_ticks=item.style.show_arrow_ticks,
                    ),
                    metadata=metadata_copy(item.metadata),
                )
                for key, item in self.dimensions.items()
            },
            suppressed_face_signatures=set(self.suppressed_face_signatures),
            face_ids_by_signature=dict(self.face_ids_by_signature),
            _next_id=self._next_id,
        )

    def new_id(self, prefix: str) -> str:
        value = f"{prefix}{self._next_id}"
        self._next_id += 1
        return value

    def add_point(self, position: Point2, *, point_id: str | None = None) -> SketchPoint:
        item = SketchPoint(point_id or self.new_id("p"), (float(position[0]), float(position[1])))
        self.points[item.id] = item
        return item

    def move_point(self, point_id: str, position: Point2) -> bool:
        point = self.points.get(point_id)
        if point is None:
            return False
        point.position = (float(position[0]), float(position[1]))
        return True

    def add_line(self, start_point_id: str, end_point_id: str, *, line_id: str | None = None) -> SketchLine:
        if start_point_id not in self.points or end_point_id not in self.points:
            raise KeyError("Line endpoints must reference existing sketch points")
        item = SketchLine(line_id or self.new_id("l"), start_point_id, end_point_id)
        self.lines[item.id] = item
        self.faces.clear()
        self.polylines.clear()
        return item

    def add_arc(
        self,
        start_point_id: str,
        end_point_id: str,
        control_point_id: str,
        *,
        arc_id: str | None = None,
    ) -> SketchArc:
        for point_id in (start_point_id, end_point_id, control_point_id):
            if point_id not in self.points:
                raise KeyError("Arc points must reference existing sketch points")
        item = SketchArc(arc_id or self.new_id("a"), start_point_id, end_point_id, control_point_id)
        self.arcs[item.id] = item
        self.faces.clear()
        self.polylines.clear()
        return item

    def add_bezier(
        self,
        start_point_id: str,
        end_point_id: str,
        control_1_point_id: str,
        control_2_point_id: str,
        *,
        bezier_id: str | None = None,
        metadata: dict | None = None,
    ) -> SketchBezier:
        for point_id in (start_point_id, end_point_id, control_1_point_id, control_2_point_id):
            if point_id not in self.points:
                raise KeyError("Bezier points must reference existing sketch points")
        item = SketchBezier(
            bezier_id or self.new_id("b"),
            start_point_id,
            end_point_id,
            control_1_point_id,
            control_2_point_id,
            metadata=dict(metadata or {}),
        )
        self.beziers[item.id] = item
        self.faces.clear()
        self.polylines.clear()
        return item

    def add_circle(self, center_point_id: str, radius_point_id: str, *, circle_id: str | None = None) -> SketchCircle:
        if center_point_id not in self.points or radius_point_id not in self.points:
            raise KeyError("Circle points must reference existing sketch points")
        item = SketchCircle(circle_id or self.new_id("c"), center_point_id, radius_point_id)
        self.circles[item.id] = item
        self.faces.clear()
        self.polylines.clear()
        return item

    def add_face(
        self,
        boundary_entity_ids: tuple[str, ...],
        polygon_points: tuple[Point2, ...],
        *,
        signature: str | None = None,
        hole_polygons: tuple[tuple[Point2, ...], ...] = (),
        hole_boundary_entity_ids: tuple[tuple[str, ...], ...] = (),
    ) -> SketchFace | None:
        signature = signature or face_signature_from_points(polygon_points, hole_polygons=hole_polygons)
        if signature in self.suppressed_face_signatures:
            return None
        metadata = {
            "signature": signature,
            "outer_signature": face_signature_from_points(polygon_points),
            "hole_signatures": tuple(face_signature_from_points(points) for points in hole_polygons),
        }
        face_id = self.face_ids_by_signature.get(signature)
        if not face_id:
            face_id = self.new_id("f")
            self.face_ids_by_signature[signature] = face_id
        item = SketchFace(
            face_id,
            boundary_entity_ids,
            polygon_points,
            tuple(tuple(point for point in polygon) for polygon in hole_polygons),
            tuple(tuple(ids) for ids in hole_boundary_entity_ids),
            metadata=metadata,
        )
        self.faces[item.id] = item
        return item

    def add_dimension(
        self,
        kind: DimensionKind | str,
        references: tuple[DimensionReference, ...],
        *,
        dimension_id: str | None = None,
        offset: float = 10.0,
        driving: bool = False,
        value_override: float | None = None,
        metadata: dict | None = None,
    ) -> SketchDimension:
        item = SketchDimension(
            dimension_id or self.new_id("d"),
            kind,
            tuple(references),
            offset=float(offset),
            driving=bool(driving),
            value_override=value_override,
            metadata=dict(metadata or {}),
        )
        self.dimensions[item.id] = item
        return item

    def add_aligned_distance_dimension(
        self,
        point_a_id: str,
        point_b_id: str,
        *,
        dimension_id: str | None = None,
        offset: float = 10.0,
    ) -> SketchDimension:
        if point_a_id not in self.points or point_b_id not in self.points:
            raise KeyError("Distance dimension points must reference existing sketch points")
        return self.add_dimension(
            DimensionKind.ALIGNED_DISTANCE,
            (
                DimensionReference(DimensionReferenceType.POINT, point_a_id, "a"),
                DimensionReference(DimensionReferenceType.POINT, point_b_id, "b"),
            ),
            dimension_id=dimension_id,
            offset=offset,
        )

    def add_edge_length_dimension(self, line_id: str, *, dimension_id: str | None = None, offset: float = 10.0) -> SketchDimension:
        if line_id not in self.lines:
            raise KeyError("Edge-length dimension must reference an existing sketch line")
        return self.add_dimension(
            DimensionKind.EDGE_LENGTH,
            (DimensionReference(DimensionReferenceType.LINE, line_id, "edge"),),
            dimension_id=dimension_id,
            offset=offset,
        )

    def add_circle_dimension(
        self,
        circle_id: str,
        *,
        kind: DimensionKind | str = DimensionKind.DIAMETER,
        dimension_id: str | None = None,
        offset: float = 0.0,
    ) -> SketchDimension:
        if circle_id not in self.circles:
            raise KeyError("Circle dimension must reference an existing sketch circle")
        kind_value = kind.value if isinstance(kind, DimensionKind) else str(kind)
        if kind_value not in {DimensionKind.RADIUS.value, DimensionKind.DIAMETER.value}:
            raise ValueError("Circle dimension kind must be radius or diameter")
        return self.add_dimension(
            kind,
            (DimensionReference(DimensionReferenceType.CIRCLE, circle_id, "circle"),),
            dimension_id=dimension_id,
            offset=offset,
        )

    def add_angle_dimension(self, first_line_id: str, second_line_id: str, *, dimension_id: str | None = None, offset: float = 12.0) -> SketchDimension:
        if first_line_id not in self.lines or second_line_id not in self.lines:
            raise KeyError("Angle dimension must reference two existing sketch lines")
        if first_line_id == second_line_id:
            raise ValueError("Angle dimension requires two distinct sketch lines")
        return self.add_dimension(
            DimensionKind.ANGLE,
            (
                DimensionReference(DimensionReferenceType.LINE, first_line_id, "a"),
                DimensionReference(DimensionReferenceType.LINE, second_line_id, "b"),
            ),
            dimension_id=dimension_id,
            offset=offset,
        )

    def delete_dimension(self, dimension_id: str) -> bool:
        return self.dimensions.pop(str(dimension_id), None) is not None

    def remove_dimensions_referencing(self, entity_ids: set[str] | tuple[str, ...] | list[str]) -> int:
        ids = {str(value) for value in entity_ids}
        removed = 0
        for dimension_id, dimension in list(self.dimensions.items()):
            if any(str(ref.id) in ids for ref in dimension.references):
                self.dimensions.pop(dimension_id, None)
                removed += 1
        return removed

    def delete_face_only(self, face_id: str, *, compile_after: bool = True):
        """Hide/delete a generated face while keeping its boundary geometry.

        Faces are derived from closed loops.  Deleting one must therefore record a
        stable geometric signature; otherwise the next compile would recreate the
        exact same fill immediately.  Boundary points/edges stay intact so the
        user can keep editing the drawing topology.
        """

        face = self.faces.get(face_id)
        if face is None:
            return None
        signature = str(face.metadata.get("signature") or face_signature_from_points(face.polygon_points))
        self.suppressed_face_signatures.add(signature)
        self.faces.pop(face_id, None)
        return self.compile() if compile_after else None

    def restore_generated_faces(self, *, compile_after: bool = True):
        self.suppressed_face_signatures.clear()
        self.faces.clear()
        return self.compile() if compile_after else None

    def delete_entity(self, entity_id: str) -> bool:
        entity_id = str(entity_id)
        deleted = False
        if entity_id in self.lines or entity_id in self.arcs or entity_id in self.beziers or entity_id in self.circles or entity_id in self.points:
            self.remove_dimensions_referencing({entity_id})
        for mapping in (self.dimensions, self.lines, self.arcs, self.beziers, self.circles, self.faces, self.polylines, self.points):
            if entity_id in mapping:
                mapping.pop(entity_id, None)
                deleted = True
        if deleted:
            self.faces.clear()
            self.polylines.clear()
        return deleted

    def delete_point_cascade(self, point_id: str, *, compile_after: bool = True):
        """Delete a point and every geometric entity directly attached to it.

        This is the topology-safe path for Modify/Delete: removing a vertex from
        a chain invalidates its incident edges, then the compiler rebuilds the
        remaining polylines and faces.
        """

        if point_id not in self.points:
            return None
        self.points.pop(point_id, None)
        self.remove_dimensions_referencing({point_id})
        for line_id, line in list(self.lines.items()):
            if point_id in {line.start_point_id, line.end_point_id}:
                self.lines.pop(line_id, None)
        for arc_id, arc in list(self.arcs.items()):
            if point_id in {arc.start_point_id, arc.end_point_id, arc.control_point_id}:
                self.arcs.pop(arc_id, None)
        for bezier_id, bezier in list(self.beziers.items()):
            if point_id in {
                bezier.start_point_id,
                bezier.end_point_id,
                bezier.control_1_point_id,
                bezier.control_2_point_id,
            }:
                self.beziers.pop(bezier_id, None)
        for circle_id, circle in list(self.circles.items()):
            if point_id in {circle.center_point_id, circle.radius_point_id}:
                self.circles.pop(circle_id, None)
        self.faces.clear()
        self.polylines.clear()
        return self.compile() if compile_after else None

    def delete_line_cascade(self, line_id: str, *, compile_after: bool = True):
        if line_id not in self.lines:
            return None
        self.lines.pop(line_id, None)
        self.remove_dimensions_referencing({line_id})
        self.faces.clear()
        self.polylines.clear()
        return self.compile() if compile_after else None

    def delete_arc_cascade(self, arc_id: str, *, compile_after: bool = True):
        if arc_id not in self.arcs:
            return None
        self.arcs.pop(arc_id, None)
        removed_reference_ids = {arc_id}
        for line_id, line in list(self.lines.items()):
            if line.metadata.get("half_circle_arc_id") == arc_id or line.metadata.get("generated_for_arc_id") == arc_id:
                self.lines.pop(line_id, None)
                removed_reference_ids.add(line_id)
        self.remove_dimensions_referencing(removed_reference_ids)
        self.faces.clear()
        self.polylines.clear()
        return self.compile() if compile_after else None

    def delete_bezier_cascade(self, bezier_id: str, *, compile_after: bool = True):
        if bezier_id not in self.beziers:
            return None
        self.beziers.pop(bezier_id, None)
        self.remove_dimensions_referencing({bezier_id})
        self.faces.clear()
        self.polylines.clear()
        return self.compile() if compile_after else None

    def compile(self, options=None):
        """Normalize topology and rebuild polylines/faces.

        The import stays local to avoid making document construction depend on
        the heavier compiler/face-solver modules.
        """

        from .compiler import SketchCompiler

        return SketchCompiler(options).compile(self)

    def sketch_points_for_snap(self, z: float = 0.0) -> list[tuple[str, tuple[float, float, float]]]:
        return [(point.id, (point.position[0], point.position[1], z)) for point in self.points.values()]

    def sketch_segments_for_snap(self, z: float = 0.0) -> list[tuple[str, tuple[float, float, float], tuple[float, float, float]]]:
        segments = []
        for line in self.lines.values():
            start = self.points[line.start_point_id].position
            end = self.points[line.end_point_id].position
            segments.append((line.id, (start[0], start[1], z), (end[0], end[1], z)))
        return segments


def face_signature_from_points(
    points: tuple[Point2, ...] | list[Point2],
    *,
    hole_polygons: tuple[tuple[Point2, ...], ...] | list[tuple[Point2, ...]] = (),
    precision: int = 6,
) -> str:
    """Return an orientation/start-point independent signature for a face.

    A face may contain holes.  The outer loop and every hole loop are normalized
    independently; hole order is ignored so recompilation remains stable even if
    the solver visits inner loops in a different order.
    """

    outer = _loop_signature(points, precision=precision)
    if not hole_polygons:
        return outer
    holes = sorted(_loop_signature(tuple(poly), precision=precision) for poly in hole_polygons)
    return outer + "|holes:" + "|".join(holes)


def _normalize_signed_zero(value: float) -> float:
    # Python can format rounded negative zeros as "-0.000000", which breaks
    # orientation-independent face signatures for otherwise identical loops.
    return 0.0 if value == 0.0 else value


def _loop_signature(points: tuple[Point2, ...] | list[Point2], *, precision: int = 6) -> str:
    cleaned = []
    for point in points:
        x = _normalize_signed_zero(round(float(point[0]), precision))
        y = _normalize_signed_zero(round(float(point[1]), precision))
        key = (x, y)
        if not cleaned or cleaned[-1] != key:
            cleaned.append(key)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if not cleaned:
        return "face:"

    def rotations(values):
        return [tuple(values[index:] + values[:index]) for index in range(len(values))]

    forward = rotations(cleaned)
    reverse = rotations(list(reversed(cleaned)))
    canonical = min(forward + reverse)
    return "face:" + ";".join(f"{x:.{precision}f},{y:.{precision}f}" for x, y in canonical)
