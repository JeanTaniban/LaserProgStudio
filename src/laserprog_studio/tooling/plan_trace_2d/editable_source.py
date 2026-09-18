# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import copy
import math
from typing import Any

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec, plane_to_world, world_to_plane
from laserprog_studio.tool_api.plan2d.dimensions import DimensionKind, DimensionReference, DimensionReferenceType, DimensionStyle
from laserprog_studio.tool_api.sketch import SketchArc, SketchBezier, SketchCircle, SketchDimension, SketchDocument, SketchLine, SketchPoint
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE

EDITABLE_SOURCE_KEY = "editable_source"
PLAN_TRACE_SOURCE_KIND = "plan_trace_2d_extrusion"
PLAN_TRACE_DRAFT_SOURCE_KIND = "plan_trace_2d_draft"
PLAN_TRACE_SUBTRACT_SOURCE_KIND = "plan_trace_2d_subtract"
PLAN_TRACE_SOURCE_SCHEMA = 1
PLAN_TRACE_MOTIF_SCHEMA = 1
PLACEMENT_REFERENCE_KEY = "placement_reference"
PLACEMENT_REFERENCE_SCHEMA = 1


def _plain(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_plain(v) for v in value]
    if hasattr(value, "value"):
        return _plain(value.value)
    if is_dataclass(value):
        return _plain(asdict(value))
    return str(value)


def _point2(value: Any) -> tuple[float, float]:
    return (float(value[0]), float(value[1]))


def _point3(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def serialize_plane(plane: LockedPlaneSpec | None) -> dict[str, Any] | None:
    if plane is None:
        return None
    return {
        "view": plane.view.value if hasattr(plane.view, "value") else str(plane.view),
        "normal": tuple(float(v) for v in plane.normal),
        "u_axis": tuple(float(v) for v in plane.u_axis),
        "v_axis": tuple(float(v) for v in plane.v_axis),
        "depth": float(plane.depth),
    }


def deserialize_plane(data: Any) -> LockedPlaneSpec | None:
    if not isinstance(data, dict):
        return None
    try:
        view = FixedPlanarView(str(data.get("view") or FixedPlanarView.TOP.value))
    except Exception:
        view = FixedPlanarView.TOP
    try:
        return LockedPlaneSpec(
            view=view,
            normal=_point3(data.get("normal") or (0.0, 0.0, 1.0)),
            u_axis=_point3(data.get("u_axis") or (1.0, 0.0, 0.0)),
            v_axis=_point3(data.get("v_axis") or (0.0, 1.0, 0.0)),
            depth=float(data.get("depth") or 0.0),
        )
    except Exception:
        return None


def serialize_sketch(sketch: SketchDocument) -> dict[str, Any]:
    return {
        "next_id": int(getattr(sketch, "_next_id", 1) or 1),
        "points": [
            {"id": p.id, "position": tuple(float(v) for v in p.position), "metadata": _plain(p.metadata)}
            for p in sketch.points.values()
        ],
        "lines": [
            {"id": l.id, "start_point_id": l.start_point_id, "end_point_id": l.end_point_id, "metadata": _plain(l.metadata)}
            for l in sketch.lines.values()
        ],
        "arcs": [
            {"id": a.id, "start_point_id": a.start_point_id, "end_point_id": a.end_point_id, "control_point_id": a.control_point_id, "metadata": _plain(a.metadata)}
            for a in sketch.arcs.values()
        ],
        "beziers": [
            {
                "id": b.id,
                "start_point_id": b.start_point_id,
                "end_point_id": b.end_point_id,
                "control_1_point_id": b.control_1_point_id,
                "control_2_point_id": b.control_2_point_id,
                "metadata": _plain(b.metadata),
            }
            for b in getattr(sketch, "beziers", {}).values()
        ],
        "circles": [
            {"id": c.id, "center_point_id": c.center_point_id, "radius_point_id": c.radius_point_id, "metadata": _plain(c.metadata)}
            for c in sketch.circles.values()
        ],
        "dimensions": [serialize_dimension(d) for d in sketch.dimensions.values()],
        "suppressed_face_signatures": sorted(str(v) for v in getattr(sketch, "suppressed_face_signatures", set()) or set()),
    }


def serialize_dimension(dimension: SketchDimension) -> dict[str, Any]:
    return {
        "id": dimension.id,
        "kind": dimension.kind.value if hasattr(dimension.kind, "value") else str(dimension.kind),
        "references": [
            {
                "type": ref.type.value if hasattr(ref.type, "value") else str(ref.type),
                "id": ref.id,
                "role": ref.role,
            }
            for ref in dimension.references
        ],
        "offset": float(dimension.offset),
        "label_position": None if dimension.label_position is None else tuple(float(v) for v in dimension.label_position),
        "driving": bool(dimension.driving),
        "value_override": None if dimension.value_override is None else float(dimension.value_override),
        "style": _plain(dimension.style),
        "metadata": _plain(dimension.metadata),
    }


def deserialize_sketch(data: Any) -> SketchDocument:
    doc = SketchDocument()
    if not isinstance(data, dict):
        return doc
    for item in data.get("points") or ():
        if not isinstance(item, dict):
            continue
        try:
            point = SketchPoint(str(item["id"]), _point2(item.get("position") or (0.0, 0.0)), metadata=dict(item.get("metadata") or {}))
            doc.points[point.id] = point
        except Exception:
            continue
    for item in data.get("lines") or ():
        if not isinstance(item, dict):
            continue
        try:
            line = SketchLine(str(item["id"]), str(item["start_point_id"]), str(item["end_point_id"]), metadata=dict(item.get("metadata") or {}))
            if line.start_point_id in doc.points and line.end_point_id in doc.points:
                doc.lines[line.id] = line
        except Exception:
            continue
    for item in data.get("arcs") or ():
        if not isinstance(item, dict):
            continue
        try:
            arc = SketchArc(str(item["id"]), str(item["start_point_id"]), str(item["end_point_id"]), str(item["control_point_id"]), metadata=dict(item.get("metadata") or {}))
            if arc.start_point_id in doc.points and arc.end_point_id in doc.points and arc.control_point_id in doc.points:
                doc.arcs[arc.id] = arc
        except Exception:
            continue
    for item in data.get("beziers") or ():
        if not isinstance(item, dict):
            continue
        try:
            bezier = SketchBezier(
                str(item["id"]),
                str(item["start_point_id"]),
                str(item["end_point_id"]),
                str(item["control_1_point_id"]),
                str(item["control_2_point_id"]),
                metadata=dict(item.get("metadata") or {}),
            )
            point_ids = (bezier.start_point_id, bezier.end_point_id, bezier.control_1_point_id, bezier.control_2_point_id)
            if all(point_id in doc.points for point_id in point_ids):
                doc.beziers[bezier.id] = bezier
        except Exception:
            continue
    for item in data.get("circles") or ():
        if not isinstance(item, dict):
            continue
        try:
            circle = SketchCircle(str(item["id"]), str(item["center_point_id"]), str(item["radius_point_id"]), metadata=dict(item.get("metadata") or {}))
            if circle.center_point_id in doc.points and circle.radius_point_id in doc.points:
                doc.circles[circle.id] = circle
        except Exception:
            continue
    for item in data.get("dimensions") or ():
        dimension = deserialize_dimension(item)
        if dimension is not None:
            doc.dimensions[dimension.id] = dimension
    try:
        doc.suppressed_face_signatures = {str(v) for v in data.get("suppressed_face_signatures") or ()}
    except Exception:
        pass
    try:
        doc._next_id = max(int(data.get("next_id") or 1), _infer_next_id(doc))
    except Exception:
        doc._next_id = _infer_next_id(doc)
    # Deserialization must be topology-preserving.  In particular, do not call
    # ``SketchDocument.compile()`` here: its default options split curve
    # intersections and curves at vertices.  Reopening an editable Plan Tracer
    # source would therefore mutate the authored graph before the live tool had
    # a chance to apply its non-destructive compile policy, and Cancel would
    # persist the newly fragmented arcs/points.  The caller that needs generated
    # faces is responsible for compiling with the appropriate policy.
    return doc


def deserialize_dimension(data: Any) -> SketchDimension | None:
    if not isinstance(data, dict):
        return None
    refs: list[DimensionReference] = []
    for item in data.get("references") or ():
        if not isinstance(item, dict):
            continue
        try:
            ref_type = DimensionReferenceType(str(item.get("type") or DimensionReferenceType.POINT.value))
        except Exception:
            ref_type = str(item.get("type") or DimensionReferenceType.POINT.value)
        refs.append(DimensionReference(ref_type, str(item.get("id") or ""), str(item.get("role") or "")))
    try:
        kind = DimensionKind(str(data.get("kind") or DimensionKind.ALIGNED_DISTANCE.value))
    except Exception:
        kind = str(data.get("kind") or DimensionKind.ALIGNED_DISTANCE.value)
    style = DimensionStyle()
    style_data = data.get("style")
    if isinstance(style_data, dict):
        try:
            style = DimensionStyle(**{k: v for k, v in style_data.items() if k in DimensionStyle.__dataclass_fields__})
        except Exception:
            pass
    label_position = data.get("label_position")
    return SketchDimension(
        str(data.get("id") or "d1"),
        kind,
        tuple(refs),
        offset=float(data.get("offset") or 10.0),
        label_position=None if label_position is None else _point2(label_position),
        driving=bool(data.get("driving", False)),
        value_override=None if data.get("value_override") is None else float(data.get("value_override")),
        style=style,
        metadata=dict(data.get("metadata") or {}),
    )


def _infer_next_id(doc: SketchDocument) -> int:
    highest = 0
    for mapping in (doc.points, doc.lines, doc.arcs, doc.beziers, doc.circles, doc.faces, doc.dimensions):
        for entity_id in mapping:
            digits = "".join(ch for ch in str(entity_id) if ch.isdigit())
            if digits:
                highest = max(highest, int(digits))
    return highest + 1


def build_editable_source(
    *,
    sketch: SketchDocument,
    plane: LockedPlaneSpec,
    display_plane: LockedPlaneSpec | None,
    anchor_world: Any,
    extrusion_depth_mm: float,
    kind: str = PLAN_TRACE_SOURCE_KIND,
    extra_metadata: dict[str, Any] | None = None,
    motif_assignments: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source = {
        "schema_version": PLAN_TRACE_SOURCE_SCHEMA,
        "tool_id": TOOL_PLAN_TRACE,
        "kind": str(kind or PLAN_TRACE_SOURCE_KIND),
        "plane": serialize_plane(plane),
        "display_plane": serialize_plane(display_plane),
        "anchor_world": None if anchor_world is None else tuple(float(v) for v in anchor_world),
        "extrusion_depth_mm": float(extrusion_depth_mm),
        "sketch": serialize_sketch(sketch),
    }
    if extra_metadata:
        source["metadata"] = _plain(extra_metadata)
    if motif_assignments:
        source["motifs"] = {
            "schema_version": PLAN_TRACE_MOTIF_SCHEMA,
            "assignments": _plain({str(key): dict(value) for key, value in motif_assignments.items()}),
        }
    return source



def motif_assignments_from_source(source: Any) -> dict[str, dict[str, Any]]:
    """Return compact parametric Pattern assignments from an editable source.

    Pattern geometry is deliberately not stored as sketch points/lines.  The
    source owns one small assignment per host face; hole polygons are derived
    when the editable sketch is opened or compiled.
    """

    if not isinstance(source, dict):
        return {}
    payload = source.get("motifs")
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("assignments")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        outer_signature = str(key or "")
        if not outer_signature:
            continue
        item = dict(value)
        targets = item.get("target_outer_signatures")
        if isinstance(targets, (list, tuple)):
            item["target_outer_signatures"] = tuple(str(v) for v in targets if str(v))
        result[outer_signature] = item
    return result

def build_draft_source(
    *,
    sketch: SketchDocument,
    plane: LockedPlaneSpec,
    display_plane: LockedPlaneSpec | None,
    anchor_world: Any,
    extrusion_depth_mm: float,
    bounds_2d: tuple[float, float, float, float] | None = None,
    motif_assignments: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"draft": True}
    if bounds_2d is not None:
        metadata["bounds_2d"] = tuple(float(v) for v in bounds_2d)
    return build_editable_source(
        sketch=sketch,
        plane=plane,
        display_plane=display_plane,
        anchor_world=anchor_world,
        extrusion_depth_mm=extrusion_depth_mm,
        kind=PLAN_TRACE_DRAFT_SOURCE_KIND,
        extra_metadata=metadata,
        motif_assignments=motif_assignments,
    )



def mesh_bounds_3d(mesh: Any) -> tuple[float, float, float, float, float, float] | None:
    """Return finite world bounds for a WorkMesh-like object."""

    vertices = tuple(getattr(mesh, "vertices", ()) or ())
    values: list[tuple[float, float, float]] = []
    for point in vertices:
        try:
            p = (float(point[0]), float(point[1]), float(point[2]))
        except Exception:
            continue
        if all(math.isfinite(value) for value in p):
            values.append(p)
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    zs = [point[2] for point in values]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _placement_landmark_indices(vertices: tuple[Any, ...], *, limit: int = 24) -> tuple[int, ...]:
    count = len(vertices)
    if count <= 0:
        return ()
    if count <= limit:
        return tuple(range(count))
    selected: set[int] = {0, count - 1}
    try:
        import numpy as np

        points = np.asarray(vertices, dtype=float)[:, :3]
        directions = np.asarray(
            [
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, -1.0),
                (1.0, -1.0, 1.0),
                (-1.0, 1.0, 1.0),
            ],
            dtype=float,
        )
        for direction in directions:
            projection = points @ direction
            selected.add(int(np.argmin(projection)))
            selected.add(int(np.argmax(projection)))
    except Exception:
        for axis in range(3):
            valid = [(float(point[axis]), index) for index, point in enumerate(vertices)]
            selected.add(min(valid)[1])
            selected.add(max(valid)[1])
    remaining = max(int(limit) - len(selected), 0)
    if remaining:
        step = float(count - 1) / float(remaining + 1)
        for index in range(1, remaining + 1):
            selected.add(int(round(step * index)))
    return tuple(sorted(selected))[: max(int(limit), 4)]


def build_placement_reference(mesh: Any) -> dict[str, Any] | None:
    """Store a tiny set of indexed world landmarks for future edit rebasing.

    Transform tools bake translation/rotation/scale directly into mesh vertices.
    The editable sketch remains compact, so a handful of original indexed
    vertices is enough to recover that affine placement later without duplicating
    the complete mesh in project metadata.
    """

    vertices = tuple(getattr(mesh, "vertices", ()) or ())
    if not vertices:
        return None
    indices = _placement_landmark_indices(vertices)
    positions: list[tuple[float, float, float]] = []
    valid_indices: list[int] = []
    for index in indices:
        try:
            point = vertices[int(index)]
            position = (float(point[0]), float(point[1]), float(point[2]))
        except Exception:
            continue
        if not all(math.isfinite(value) for value in position):
            continue
        valid_indices.append(int(index))
        positions.append(position)
    if len(valid_indices) < 4:
        return None
    return {
        "schema_version": PLACEMENT_REFERENCE_SCHEMA,
        "vertex_count": len(vertices),
        "triangle_count": len(tuple(getattr(mesh, "triangles", ()) or ())),
        "indices": valid_indices,
        "positions": positions,
        "bounds": mesh_bounds_3d(mesh),
    }


def _mesh_from_serialized_reference(data: Any) -> Any | None:
    if not isinstance(data, dict):
        return None
    try:
        from laserprog_studio.domain.work_model import WorkMesh

        mesh = WorkMesh(
            name=str(data.get("name") or "Plan tracer placement reference"),
            vertices=[tuple(float(value) for value in point[:3]) for point in tuple(data.get("vertices") or ())],
            triangles=[tuple(int(value) for value in tri[:3]) for tri in tuple(data.get("triangles") or ())],
            color=str(data.get("color") or "#B8B8B8"),
        )
        return mesh
    except Exception:
        return None


def _reference_mesh_from_source(source: dict[str, Any]) -> Any | None:
    """Rebuild legacy v1 source geometry when no placement landmarks exist."""

    kind = str(source.get("kind") or "")
    if kind == PLAN_TRACE_DRAFT_SOURCE_KIND:
        try:
            return build_draft_placeholder_mesh(copy.deepcopy(source))
        except Exception:
            return None
    if kind == PLAN_TRACE_SUBTRACT_SOURCE_KIND:
        try:
            metadata = dict(source.get("metadata") or {})
            mesh = _mesh_from_serialized_reference(metadata.get("intact_target_mesh"))
            if mesh is not None:
                return mesh
        except Exception:
            pass
    plane = deserialize_plane(source.get("plane"))
    if plane is None:
        return None
    sketch = deserialize_sketch(source.get("sketch"))
    try:
        from laserprog_studio.tool_api.sketch import SketchCompileOptions

        sketch.compile(
            SketchCompileOptions(
                merge_tolerance=1.0e-5,
                split_tolerance=1.0e-5,
                solve_faces=True,
                split_curve_intersections=False,
                split_curves_at_vertices=False,
            )
        )
    except Exception:
        pass
    regions: list[tuple[tuple[tuple[float, float], ...], tuple[tuple[tuple[float, float], ...], ...]]] = []
    for face in tuple(getattr(sketch, "faces", {}).values()):
        outer = tuple((float(point[0]), float(point[1])) for point in tuple(getattr(face, "polygon_points", ()) or ()))
        holes = tuple(
            tuple((float(point[0]), float(point[1])) for point in tuple(hole or ()))
            for hole in tuple(getattr(face, "hole_polygons", ()) or ())
        )
        if len(outer) >= 3:
            regions.append((outer, holes))
    if not regions:
        return None
    try:
        from laserprog_studio.geometry_ops.planar_boolean_solid import extrude_planar_regions_boolean_ready

        depth = max(float(source.get("extrusion_depth_mm") or 0.001), 0.001)
        mesh, _report = extrude_planar_regions_boolean_ready(
            regions,
            plane=plane,
            depth=depth,
            name="Plan tracer placement reference",
            color="#8BC34A",
        )
        return mesh
    except Exception:
        return None


def _affine_from_pairs(reference_points: list[tuple[float, float, float]], current_points: list[tuple[float, float, float]]) -> tuple[Any | None, float, int]:
    if len(reference_points) < 4 or len(reference_points) != len(current_points):
        return None, float("inf"), 0
    try:
        import numpy as np

        reference = np.asarray(reference_points, dtype=float)
        current = np.asarray(current_points, dtype=float)
        design = np.column_stack((reference, np.ones(len(reference), dtype=float)))
        coefficients, _residuals, rank, _singular = np.linalg.lstsq(design, current, rcond=None)
        predicted = design @ coefficients
        error = predicted - current
        rms = float(np.sqrt(np.mean(np.sum(error * error, axis=1))))
        if int(rank) < 4 or not np.isfinite(rms):
            return None, rms, int(rank)
        linear = coefficients[:3, :]
        determinant = float(np.linalg.det(linear))
        if not np.isfinite(determinant) or abs(determinant) < 1.0e-12:
            return None, rms, int(rank)
        return coefficients, rms, int(rank)
    except Exception:
        return None, float("inf"), 0


def _affine_identity_error(coefficients: Any) -> float:
    """Return the largest coefficient delta from an exact identity transform."""

    try:
        import numpy as np

        value = np.asarray(coefficients, dtype=float)
        target = np.zeros((4, 3), dtype=float)
        target[:3, :] = np.eye(3, dtype=float)
        if value.shape != target.shape:
            return float("inf")
        error = float(np.max(np.abs(value - target)))
        return error if math.isfinite(error) else float("inf")
    except Exception:
        try:
            target = (
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
                (0.0, 0.0, 0.0),
            )
            return max(
                abs(float(coefficients[row][column]) - float(target[row][column]))
                for row in range(4)
                for column in range(3)
            )
        except Exception:
            return float("inf")


def _translation_affine(delta: tuple[float, float, float]) -> Any:
    try:
        import numpy as np

        coefficients = np.zeros((4, 3), dtype=float)
        coefficients[:3, :] = np.eye(3, dtype=float)
        coefficients[3, :] = np.asarray(delta, dtype=float)
        return coefficients
    except Exception:
        return (
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            tuple(float(value) for value in delta),
        )


def _affine_point(coefficients: Any, point: Any) -> tuple[float, float, float]:
    try:
        import numpy as np

        p = np.asarray((float(point[0]), float(point[1]), float(point[2])), dtype=float)
        result = p @ np.asarray(coefficients, dtype=float)[:3, :] + np.asarray(coefficients, dtype=float)[3, :]
        return (float(result[0]), float(result[1]), float(result[2]))
    except Exception:
        linear = coefficients[:3]
        translation = coefficients[3]
        return (
            float(point[0]) * float(linear[0][0]) + float(point[1]) * float(linear[1][0]) + float(point[2]) * float(linear[2][0]) + float(translation[0]),
            float(point[0]) * float(linear[0][1]) + float(point[1]) * float(linear[1][1]) + float(point[2]) * float(linear[2][1]) + float(translation[1]),
            float(point[0]) * float(linear[0][2]) + float(point[1]) * float(linear[1][2]) + float(point[2]) * float(linear[2][2]) + float(translation[2]),
        )


def _affine_vector(coefficients: Any, vector: Any) -> tuple[float, float, float]:
    origin = _affine_point(coefficients, (0.0, 0.0, 0.0))
    endpoint = _affine_point(coefficients, vector)
    return (endpoint[0] - origin[0], endpoint[1] - origin[1], endpoint[2] - origin[2])


def _dot3(a: Any, b: Any) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross3(a: Any, b: Any) -> tuple[float, float, float]:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _unit3(value: Any, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        vector = (float(value[0]), float(value[1]), float(value[2]))
        length = math.sqrt(max(_dot3(vector, vector), 0.0))
        if not math.isfinite(length) or length <= 1.0e-12:
            return fallback
        return (vector[0] / length, vector[1] / length, vector[2] / length)
    except Exception:
        return fallback


def _transform_plane(plane: LockedPlaneSpec, coefficients: Any) -> LockedPlaneSpec:
    origin = plane_to_world(plane, 0.0, 0.0)
    u_endpoint = plane_to_world(plane, 1.0, 0.0)
    v_endpoint = plane_to_world(plane, 0.0, 1.0)
    transformed_origin = _affine_point(coefficients, origin)
    transformed_u_endpoint = _affine_point(coefficients, u_endpoint)
    transformed_v_endpoint = _affine_point(coefficients, v_endpoint)
    transformed_u = (
        transformed_u_endpoint[0] - transformed_origin[0],
        transformed_u_endpoint[1] - transformed_origin[1],
        transformed_u_endpoint[2] - transformed_origin[2],
    )
    transformed_v = (
        transformed_v_endpoint[0] - transformed_origin[0],
        transformed_v_endpoint[1] - transformed_origin[1],
        transformed_v_endpoint[2] - transformed_origin[2],
    )
    u_axis = _unit3(transformed_u, tuple(float(value) for value in plane.u_axis))
    normal = _unit3(_cross3(transformed_u, transformed_v), tuple(float(value) for value in plane.normal))
    transformed_old_normal = _affine_vector(coefficients, plane.normal)
    if _dot3(normal, transformed_old_normal) < 0.0:
        normal = (-normal[0], -normal[1], -normal[2])
    v_axis = _unit3(_cross3(normal, u_axis), tuple(float(value) for value in plane.v_axis))
    if _dot3(v_axis, transformed_v) < 0.0:
        u_axis = (-u_axis[0], -u_axis[1], -u_axis[2])
        v_axis = (-v_axis[0], -v_axis[1], -v_axis[2])
    depth = _dot3(normal, transformed_origin)
    return LockedPlaneSpec(plane.view, normal, u_axis, v_axis, float(depth))


def _transform_serialized_mesh(data: Any, coefficients: Any) -> None:
    if not isinstance(data, dict):
        return
    transformed = []
    for point in tuple(data.get("vertices") or ()):
        try:
            transformed.append(_affine_point(coefficients, point))
        except Exception:
            transformed.append(point)
    if transformed:
        data["vertices"] = transformed


def _transform_source_geometry(source: dict[str, Any], coefficients: Any) -> dict[str, Any]:
    old_plane = deserialize_plane(source.get("plane"))
    if old_plane is None:
        return source
    new_plane = _transform_plane(old_plane, coefficients)
    old_display = deserialize_plane(source.get("display_plane"))
    new_display = _transform_plane(old_display, coefficients) if old_display is not None else None
    sketch_data = source.get("sketch")
    if isinstance(sketch_data, dict):
        for point in tuple(sketch_data.get("points") or ()):
            if not isinstance(point, dict):
                continue
            try:
                xy = point.get("position") or (0.0, 0.0)
                old_world = plane_to_world(old_plane, float(xy[0]), float(xy[1]))
                new_world = _affine_point(coefficients, old_world)
                point["position"] = world_to_plane(new_plane, new_world)
            except Exception:
                continue
        for dimension in tuple(sketch_data.get("dimensions") or ()):
            if not isinstance(dimension, dict) or dimension.get("label_position") is None:
                continue
            try:
                xy = dimension.get("label_position")
                old_world = plane_to_world(old_plane, float(xy[0]), float(xy[1]))
                new_world = _affine_point(coefficients, old_world)
                dimension["label_position"] = world_to_plane(new_plane, new_world)
            except Exception:
                continue
    anchor = source.get("anchor_world")
    if anchor is not None:
        try:
            source["anchor_world"] = _affine_point(coefficients, anchor)
        except Exception:
            pass
    try:
        old_depth = max(float(source.get("extrusion_depth_mm") or 0.001), 0.001)
        base = plane_to_world(old_plane, 0.0, 0.0)
        top = (
            base[0] + float(old_plane.normal[0]) * old_depth,
            base[1] + float(old_plane.normal[1]) * old_depth,
            base[2] + float(old_plane.normal[2]) * old_depth,
        )
        transformed_base = _affine_point(coefficients, base)
        transformed_top = _affine_point(coefficients, top)
        transformed_depth_vector = (
            transformed_top[0] - transformed_base[0],
            transformed_top[1] - transformed_base[1],
            transformed_top[2] - transformed_base[2],
        )
        transformed_depth = abs(_dot3(transformed_depth_vector, new_plane.normal))
        if transformed_depth <= 1.0e-9:
            transformed_depth = math.sqrt(max(_dot3(transformed_depth_vector, transformed_depth_vector), 0.0))
        source["extrusion_depth_mm"] = max(float(transformed_depth), 0.001)
    except Exception:
        pass
    source["plane"] = serialize_plane(new_plane)
    source["display_plane"] = serialize_plane(new_display)
    metadata = source.get("metadata")
    if isinstance(metadata, dict):
        intact = metadata.get("intact_target_mesh")
        _transform_serialized_mesh(intact, coefficients)
        if isinstance(intact, dict) and intact.get("vertices"):
            try:
                depths = [_dot3(new_plane.normal, point) for point in intact.get("vertices") or ()]
                metadata["depth_range"] = (min(depths), max(depths))
            except Exception:
                pass
        if isinstance(sketch_data, dict):
            positions = []
            for point in tuple(sketch_data.get("points") or ()):
                if isinstance(point, dict) and point.get("position") is not None:
                    try:
                        positions.append((float(point["position"][0]), float(point["position"][1])))
                    except Exception:
                        pass
            if positions and "bounds_2d" in metadata:
                xs = [point[0] for point in positions]
                ys = [point[1] for point in positions]
                metadata["bounds_2d"] = (min(xs), min(ys), max(xs), max(ys))
    source.pop(PLACEMENT_REFERENCE_KEY, None)
    return source


def resolve_editable_source_placement(source: dict[str, Any], mesh: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rebase an editable Plan Tracer source onto the mesh's current placement.

    Returns a transformed source copy and a small report.  New files use indexed
    placement landmarks.  Legacy sources are rebuilt once and matched by vertex
    index; if their topology cannot be reproduced, a conservative bounds-center
    translation still preserves the common moved-object case.
    """

    resolved = copy.deepcopy(source)
    current_vertices = tuple(getattr(mesh, "vertices", ()) or ())
    current_bounds = mesh_bounds_3d(mesh)
    reference_points: list[tuple[float, float, float]] = []
    current_points: list[tuple[float, float, float]] = []
    reference_bounds = None
    mode = "identity"
    reference_kind = "none"

    placement = source.get(PLACEMENT_REFERENCE_KEY)
    if isinstance(placement, dict) and int(placement.get("schema_version") or 0) == PLACEMENT_REFERENCE_SCHEMA:
        indices = tuple(int(index) for index in tuple(placement.get("indices") or ()))
        positions = tuple(placement.get("positions") or ())
        if int(placement.get("vertex_count") or -1) == len(current_vertices) and len(indices) == len(positions):
            for index, position in zip(indices, positions):
                if not (0 <= index < len(current_vertices)):
                    reference_points = []
                    current_points = []
                    break
                try:
                    reference_points.append((float(position[0]), float(position[1]), float(position[2])))
                    current = current_vertices[index]
                    current_points.append((float(current[0]), float(current[1]), float(current[2])))
                except Exception:
                    reference_points = []
                    current_points = []
                    break
            reference_bounds = placement.get("bounds")
            reference_kind = "stored_landmarks"

    reference_mesh = None
    if len(reference_points) < 4:
        reference_mesh = _reference_mesh_from_source(source)
        reference_vertices = tuple(getattr(reference_mesh, "vertices", ()) or ()) if reference_mesh is not None else ()
        if reference_vertices and len(reference_vertices) == len(current_vertices):
            indices = _placement_landmark_indices(reference_vertices)
            for index in indices:
                try:
                    reference = reference_vertices[index]
                    current = current_vertices[index]
                    reference_points.append((float(reference[0]), float(reference[1]), float(reference[2])))
                    current_points.append((float(current[0]), float(current[1]), float(current[2])))
                except Exception:
                    reference_points = []
                    current_points = []
                    break
            reference_kind = "legacy_rebuild"
        reference_bounds = mesh_bounds_3d(reference_mesh) if reference_mesh is not None else reference_bounds

    coefficients = None
    rms = float("inf")
    rank = 0
    if len(reference_points) >= 4:
        coefficients, rms, rank = _affine_from_pairs(reference_points, current_points)
        if coefficients is not None:
            diagonal = 1.0
            if current_bounds is not None:
                diagonal = math.sqrt(
                    max(
                        (current_bounds[1] - current_bounds[0]) ** 2
                        + (current_bounds[3] - current_bounds[2]) ** 2
                        + (current_bounds[5] - current_bounds[4]) ** 2,
                        1.0,
                    )
                )
            tolerance = max(1.0e-5, diagonal * 2.0e-6)
            if rms <= tolerance:
                # Least-squares recovery adds tiny floating noise even when the
                # mesh has never moved.  Keep the original source byte-for-byte
                # in that case so dimensions, depths and serialized subtraction
                # targets do not drift merely by opening the editor.
                identity_tolerance = max(1.0e-10, tolerance * 1.0e-5)
                if _affine_identity_error(coefficients) <= identity_tolerance:
                    coefficients = None
                    mode = "identity"
                else:
                    mode = "affine"
            else:
                coefficients = None

    if coefficients is None and current_bounds is not None and reference_bounds is not None:
        try:
            ref = tuple(float(value) for value in reference_bounds)
            cur = tuple(float(value) for value in current_bounds)
            ref_center = ((ref[0] + ref[1]) * 0.5, (ref[2] + ref[3]) * 0.5, (ref[4] + ref[5]) * 0.5)
            cur_center = ((cur[0] + cur[1]) * 0.5, (cur[2] + cur[3]) * 0.5, (cur[4] + cur[5]) * 0.5)
            delta = (cur_center[0] - ref_center[0], cur_center[1] - ref_center[1], cur_center[2] - ref_center[2])
            coefficients = _translation_affine(delta)
            mode = "translation"
            rms = 0.0
            rank = 4
        except Exception:
            coefficients = None

    if coefficients is not None:
        resolved = _transform_source_geometry(resolved, coefficients)
    return resolved, {
        "mode": mode,
        "reference": reference_kind,
        "rms": float(rms) if math.isfinite(rms) else None,
        "rank": int(rank),
        "focus_bounds": current_bounds,
    }


def attach_editable_source(mesh: Any, source: dict[str, Any]) -> Any:
    metadata = getattr(mesh, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        try:
            setattr(mesh, "metadata", metadata)
        except Exception:
            pass
    stored_source = _plain(source)
    if isinstance(stored_source, dict) and not isinstance(stored_source.get(PLACEMENT_REFERENCE_KEY), dict):
        placement_reference = build_placement_reference(mesh)
        if placement_reference is not None:
            stored_source[PLACEMENT_REFERENCE_KEY] = placement_reference
    metadata[EDITABLE_SOURCE_KEY] = stored_source
    metadata["source_tool"] = TOOL_PLAN_TRACE
    metadata["editable_tool_id"] = TOOL_PLAN_TRACE
    metadata["editable_kind"] = str(stored_source.get("kind") or PLAN_TRACE_SOURCE_KIND)
    metadata["plan_trace_draft"] = str(stored_source.get("kind") or "") == PLAN_TRACE_DRAFT_SOURCE_KIND
    metadata["plan_trace_subtract"] = str(stored_source.get("kind") or "") == PLAN_TRACE_SUBTRACT_SOURCE_KIND
    try:
        metadata["plan_trace_operation"] = str((stored_source.get("metadata") or {}).get("operation") or ("subtract" if str(stored_source.get("kind") or "") == PLAN_TRACE_SUBTRACT_SOURCE_KIND else "add"))
    except Exception:
        metadata["plan_trace_operation"] = "add"
    metadata["extrusion_depth_mm"] = float(stored_source.get("extrusion_depth_mm") or 0.0)
    return mesh


def editable_source_from_mesh(mesh: Any) -> dict[str, Any] | None:
    metadata = getattr(mesh, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    source = metadata.get(EDITABLE_SOURCE_KEY)
    if not isinstance(source, dict):
        return None
    if str(source.get("tool_id") or metadata.get("source_tool") or "") != TOOL_PLAN_TRACE:
        return None
    if str(source.get("kind") or "") not in {PLAN_TRACE_SOURCE_KIND, PLAN_TRACE_DRAFT_SOURCE_KIND, PLAN_TRACE_SUBTRACT_SOURCE_KIND}:
        return None
    if int(source.get("schema_version") or 0) != PLAN_TRACE_SOURCE_SCHEMA:
        return None
    if not isinstance(source.get("sketch"), dict):
        return None
    return source


def is_editable_plan_trace_mesh(mesh: Any) -> bool:
    return editable_source_from_mesh(mesh) is not None

def plan_trace_source_kind(source: dict[str, Any] | None) -> str:
    if not isinstance(source, dict):
        return ""
    return str(source.get("kind") or "")


def is_plan_trace_draft_source(source: dict[str, Any] | None) -> bool:
    return plan_trace_source_kind(source) == PLAN_TRACE_DRAFT_SOURCE_KIND


def is_plan_trace_subtract_source(source: dict[str, Any] | None) -> bool:
    return plan_trace_source_kind(source) == PLAN_TRACE_SUBTRACT_SOURCE_KIND


def sketch_bounds_2d(sketch: SketchDocument) -> tuple[float, float, float, float] | None:
    values: list[tuple[float, float]] = []
    try:
        values.extend((float(p.position[0]), float(p.position[1])) for p in sketch.points.values())
    except Exception:
        pass
    try:
        for face in sketch.faces.values():
            for x, y in tuple(getattr(face, "polygon_points", ()) or ()):
                values.append((float(x), float(y)))
            for hole in tuple(getattr(face, "hole_polygons", ()) or ()):
                for x, y in tuple(hole):
                    values.append((float(x), float(y)))
    except Exception:
        pass
    if not values:
        return None
    xs = [p[0] for p in values]
    ys = [p[1] for p in values]
    return (min(xs), min(ys), max(xs), max(ys))


def build_draft_placeholder_mesh(source: dict[str, Any], *, name: str = "Plan trace 2D draft") -> Any:
    from laserprog_studio.domain.work_model import WorkMesh
    from laserprog_studio.planar_tools import plane_to_world

    plane = deserialize_plane(source.get("plane"))
    sketch = deserialize_sketch(source.get("sketch"))
    if plane is None:
        raise ValueError("draft source has no plane")
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    raw_bounds = metadata.get("bounds_2d") if isinstance(metadata, dict) else None
    bounds = None
    if isinstance(raw_bounds, (tuple, list)) and len(raw_bounds) == 4:
        try:
            bounds = tuple(float(v) for v in raw_bounds)
        except Exception:
            bounds = None
    if bounds is None:
        bounds = sketch_bounds_2d(sketch)
    if bounds is None:
        raise ValueError("draft sketch has no bounds")
    min_u, min_v, max_u, max_v = bounds
    if abs(max_u - min_u) < 1.0:
        mid = (min_u + max_u) * 0.5
        min_u, max_u = mid - 0.5, mid + 0.5
    if abs(max_v - min_v) < 1.0:
        mid = (min_v + max_v) * 0.5
        min_v, max_v = mid - 0.5, mid + 0.5
    try:
        stored_depth = float(source.get("extrusion_depth_mm") or 10.0)
    except Exception:
        stored_depth = 10.0
    placeholder_depth = max(min(abs(stored_depth), 10.0), 2.0)
    offset = tuple(float(value) * placeholder_depth for value in plane.normal)

    def add3(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))

    base = [
        plane_to_world(plane, min_u, min_v),
        plane_to_world(plane, max_u, min_v),
        plane_to_world(plane, max_u, max_v),
        plane_to_world(plane, min_u, max_v),
    ]
    top = [add3(point, offset) for point in base]
    vertices = base + top
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    mesh = WorkMesh(name=name, vertices=vertices, triangles=triangles, color="#F44336")
    attach_editable_source(mesh, source)
    try:
        mesh.metadata.update({
            "plan_trace_placeholder": True,
            "plan_trace_placeholder_kind": "draft_bounds",
            "placeholder_bounds_2d": tuple(float(v) for v in (min_u, min_v, max_u, max_v)),
        })
    except Exception:
        pass
    return mesh



__all__ = [
    "EDITABLE_SOURCE_KEY",
    "PLAN_TRACE_SOURCE_KIND",
    "PLAN_TRACE_DRAFT_SOURCE_KIND",
    "PLAN_TRACE_SUBTRACT_SOURCE_KIND",
    "PLAN_TRACE_SOURCE_SCHEMA",
    "PLACEMENT_REFERENCE_KEY",
    "PLACEMENT_REFERENCE_SCHEMA",
    "attach_editable_source",
    "build_editable_source",
    "build_draft_source",
    "build_draft_placeholder_mesh",
    "build_placement_reference",
    "deserialize_plane",
    "deserialize_sketch",
    "editable_source_from_mesh",
    "is_editable_plan_trace_mesh",
    "is_plan_trace_draft_source",
    "is_plan_trace_subtract_source",
    "mesh_bounds_3d",
    "motif_assignments_from_source",
    "plan_trace_source_kind",
    "resolve_editable_source_placement",
    "sketch_bounds_2d",
    "serialize_plane",
    "serialize_sketch",
]
