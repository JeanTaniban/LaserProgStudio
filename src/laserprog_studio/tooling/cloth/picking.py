"""Small geometry/picking helpers for the Cloth Creator adapter."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from laserprog_studio.tool_api import snap as snap_api
from laserprog_studio.tool_api.tracing import point_plane_distance

from .models import ClothCurveKind, ClothDocument
from .topology import patch_frame, sample_curve, sample_patch_boundary

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


def face_vertices_for_pick(ctx: Any, pick: Any) -> tuple[Point3, ...]:
    try:
        raw = dict(getattr(pick, "metadata", {}) or {}).get("face_vertices")
        if raw:
            return tuple(tuple(float(value) for value in point) for point in raw)
    except Exception:
        pass
    index = getattr(pick, "element_index", None)
    if index is None:
        return ()
    obj = object_from_pick(ctx, pick)
    mesh = getattr(obj, "mesh", None) if obj is not None else None
    try:
        triangle = tuple(int(value) for value in mesh.triangles[int(index)])
        return tuple(tuple(float(value) for value in mesh.vertices[vertex_index]) for vertex_index in triangle)
    except Exception:
        return ()


def object_from_pick(ctx: Any, pick: Any) -> Any | None:
    try:
        if getattr(pick, "object_id", None) is not None:
            return ctx.document.get(str(pick.object_id))
    except Exception:
        pass
    try:
        if getattr(pick, "object_index", None) is not None:
            return ctx.document.objects()[int(pick.object_index)]
    except Exception:
        pass
    return None


def nearest_document_point(document: ClothDocument, screen_pos: Point2, world_to_screen, *, max_distance_px: float = 14.0) -> str | None:
    best: tuple[float, str] | None = None
    for point in document.points.values():
        distance = _distance2(world_to_screen(point.position), screen_pos)
        if distance <= max_distance_px and (best is None or distance < best[0]):
            best = (distance, point.id)
    return best[1] if best is not None else None


def nearest_document_curve(document: ClothDocument, screen_pos: Point2, world_to_screen, *, max_distance_px: float = 12.0) -> str | None:
    best: tuple[float, str] | None = None
    for curve in document.curves.values():
        points = tuple(sample_curve(document, curve, arc_segments=32))
        if len(points) < 2:
            continue
        projected = tuple(world_to_screen(point) for point in points)
        distance = min(_point_segment_distance(screen_pos, projected[index - 1], projected[index]) for index in range(1, len(projected)))
        if curve.kind is ClothCurveKind.POLYLINE and curve.closed:
            distance = min(distance, _point_segment_distance(screen_pos, projected[-1], projected[0]))
        if distance <= max_distance_px and (best is None or distance < best[0]):
            best = (distance, curve.id)
    return best[1] if best is not None else None


@dataclass(slots=True)
class ClothSnapTargetCache:
    """Revision keyed cache for live Cloth snap targets.

    Cursor moves are the hottest path in the tool. Building sampled edges and
    midpoint/intersection metadata on every mouse event made larger Cloth
    sketches progressively slower.
    """

    document_id: int | None = None
    revision: int = -1
    owner_tool: str = ""
    targets: tuple[Any, ...] = ()

    def reset(self) -> None:
        self.document_id = None
        self.revision = -1
        self.owner_tool = ""
        self.targets = ()

    def get(self, document: ClothDocument, *, owner_tool: str) -> tuple[Any, ...]:
        identity = id(document)
        revision = int(document.revision)
        owner = str(owner_tool)
        if self.document_id != identity or self.revision != revision or self.owner_tool != owner:
            self.document_id = identity
            self.revision = revision
            self.owner_tool = owner
            self.targets = _build_cloth_snap_targets(document, owner_tool=owner)
        return self.targets

    def near(
        self,
        ctx: Any,
        document: ClothDocument,
        screen_pos: Point2,
        *,
        owner_tool: str,
        max_distance_px: float,
        limit: int = 96,
    ) -> tuple[Any, ...]:
        """Return only Cloth targets that can affect the current cursor move.

        The generic snap engine computes semantic intersections between the
        targets it receives. Passing an entire large sketch would therefore be
        quadratic on every mouse move. A cheap projected proximity pass keeps
        that work local without changing snap semantics near the pointer.
        """

        targets = self.get(document, owner_tool=owner_tool)
        projector = getattr(getattr(ctx, "viewport", None), "world_to_screen", None)
        if not callable(projector):
            return targets[: max(1, int(limit))]
        radius = max(8.0, float(max_distance_px) * 2.25)
        ranked: list[tuple[float, Any]] = []
        for target in targets:
            distance = _target_screen_distance(target, screen_pos, projector)
            if distance <= radius:
                ranked.append((distance, target))
        ranked.sort(key=lambda item: (item[0], int(getattr(item[1], "priority", 100))))
        return tuple(target for _distance, target in ranked[: max(1, int(limit))])


def cloth_snap_targets(
    document: ClothDocument,
    *,
    owner_tool: str,
    plane: Any | None = None,
    plane_tolerance_mm: float = 0.5,
):
    """Return semantic Cloth snap targets.

    ``plane`` is kept for compatibility with older integrations. Free-3D Cloth
    normally requests the revision-cached unfiltered target set.
    """

    targets = _build_cloth_snap_targets(document, owner_tool=owner_tool)
    if plane is None:
        return targets
    filtered: list[Any] = []
    for target in targets:
        positions = [value for value in (getattr(target, "world_pos", None), getattr(target, "start", None), getattr(target, "end", None), getattr(target, "control", None), getattr(target, "center", None)) if value is not None]
        if positions and max(point_plane_distance(plane, position) for position in positions) <= plane_tolerance_mm:
            filtered.append(target)
    return tuple(filtered)


def _build_cloth_snap_targets(document: ClothDocument, *, owner_tool: str) -> tuple[Any, ...]:
    targets: list[Any] = []
    for point in document.points.values():
        targets.append(
            snap_api.tool_point(
                f"cloth:point:{point.id}",
                point.position,
                owner_tool=owner_tool,
                radius_px=9.0,
                priority=4,
                kind=snap_api.SnapKind.VERTEX,
                metadata={"cloth_point_id": point.id, "snap_label": "Vertex"},
            )
        )

    for curve in document.curves.values():
        points = tuple(sample_curve(document, curve, arc_segments=32))
        for index in range(1, len(points)):
            start, end = points[index - 1], points[index]
            targets.append(
                snap_api.tool_segment(
                    f"cloth:curve:{curve.id}:{index - 1}",
                    start,
                    end,
                    owner_tool=owner_tool,
                    radius_px=16.0,
                    priority=34,
                    kind=snap_api.SnapKind.EDGE,
                    metadata={
                        "cloth_curve_id": curve.id,
                        "snap_label": "Edge",
                        "include_midpoint_snap": True,
                        "include_intersection_snap": True,
                        "midpoint_radius_px": 14.0,
                        "intersection_radius_px": 13.0,
                    },
                )
            )
        if curve.kind is ClothCurveKind.POLYLINE and curve.closed and len(points) >= 3:
            targets.append(
                snap_api.tool_segment(
                    f"cloth:curve:{curve.id}:close",
                    points[-1],
                    points[0],
                    owner_tool=owner_tool,
                    radius_px=16.0,
                    priority=34,
                    kind=snap_api.SnapKind.EDGE,
                    metadata={
                        "cloth_curve_id": curve.id,
                        "snap_label": "Edge",
                        "include_midpoint_snap": True,
                        "include_intersection_snap": True,
                    },
                )
            )
        if curve.kind is ClothCurveKind.ARC and len(curve.point_ids) == 3:
            start_id, end_id, control_id = curve.point_ids
            center = _circumcenter_3d(
                document.points[start_id].position,
                document.points[end_id].position,
                document.points[control_id].position,
            )
            if center is not None:
                targets.append(
                    snap_api.tool_point(
                        f"cloth:curve:{curve.id}:center",
                        center,
                        owner_tool=owner_tool,
                        radius_px=10.0,
                        priority=8,
                        kind=snap_api.SnapKind.CENTER,
                        metadata={"cloth_curve_id": curve.id, "snap_label": "Arc center"},
                    )
                )
    return tuple(targets)


def _circumcenter_3d(a: Point3, b: Point3, c: Point3) -> Point3 | None:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    cross2 = sum(value * value for value in cross)
    if cross2 <= 1.0e-18:
        return None
    ab2 = sum(value * value for value in ab)
    ac2 = sum(value * value for value in ac)
    ac_cross = (
        ac[1] * cross[2] - ac[2] * cross[1],
        ac[2] * cross[0] - ac[0] * cross[2],
        ac[0] * cross[1] - ac[1] * cross[0],
    )
    cross_ab = (
        cross[1] * ab[2] - cross[2] * ab[1],
        cross[2] * ab[0] - cross[0] * ab[2],
        cross[0] * ab[1] - cross[1] * ab[0],
    )
    scale = 1.0 / (2.0 * cross2)
    offset = tuple((ab2 * ac_cross[index] + ac2 * cross_ab[index]) * scale for index in range(3))
    return (a[0] + offset[0], a[1] + offset[1], a[2] + offset[2])


def _target_screen_distance(target: Any, screen_pos: Point2, projector) -> float:
    try:
        if getattr(target, "world_pos", None) is not None:
            return _distance2(projector(target.world_pos), screen_pos)
        if getattr(target, "center", None) is not None:
            return _distance2(projector(target.center), screen_pos)
        start = getattr(target, "start", None)
        end = getattr(target, "end", None)
        if start is not None and end is not None:
            return _point_segment_distance(screen_pos, projector(start), projector(end))
    except Exception:
        return float("inf")
    return float("inf")


def point_id_from_snap_source(source_id: str | None, metadata: dict[str, Any] | None = None) -> str | None:
    data = dict(metadata or {})
    value = data.get("cloth_point_id")
    if value is not None:
        return str(value)
    raw = str(source_id or "")
    prefix = "cloth:point:"
    return raw[len(prefix):] if raw.startswith(prefix) else None


def _distance2(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay = tuple(a)[:2]
    bx, by = tuple(b)[:2]
    return math.hypot(float(ax) - float(bx), float(ay) - float(by))


def _point_segment_distance(point: Point2, start: Point2, end: Point2) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 <= 1.0e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


@dataclass(frozen=True, slots=True)
class ClothSurfaceRayHit:
    """Closest actual Cloth surface hit along one camera ray."""

    patch_id: str
    world_pos: Point3
    distance: float
    triangle_index: int
    normal: Point3


@dataclass(slots=True)
class ClothSurfaceRaycastCache:
    """Revision-keyed triangle cache for depth-correct Cloth picking.

    Cloth faces are projected overlays rather than normal scene objects.  A
    screen-polygon test cannot decide whether a Cloth face is in front of or
    behind a scene mesh.  This cache builds the canonical Cloth mid-surface once
    per document revision and performs a real ray/triangle query.
    """

    document_id: int | None = None
    revision: int = -1
    vertices: tuple[Point3, ...] = ()
    triangles: tuple[tuple[int, int, int], ...] = ()
    patch_by_triangle: tuple[str, ...] = ()
    build_mode: str = "empty"
    build_issues: tuple[str, ...] = ()

    def reset(self) -> None:
        self.document_id = None
        self.revision = -1
        self.vertices = ()
        self.triangles = ()
        self.patch_by_triangle = ()
        self.build_mode = "empty"
        self.build_issues = ()

    def _ensure(self, document: ClothDocument) -> bool:
        identity = id(document)
        revision = int(document.revision)
        if self.document_id == identity and self.revision == revision:
            return bool(self.triangles)
        self.reset()
        self.document_id = identity
        self.revision = revision
        try:
            from .mesh_builder import build_cloth_surface_mesh, triangulate_simple_polygon

            built = build_cloth_surface_mesh(document, name="Cloth picking surface", arc_segments=24)
            self.build_issues = tuple(str(issue) for issue in built.issues)
            if built.mesh is not None:
                self.vertices = tuple(tuple(float(value) for value in point) for point in built.mesh.vertices)
                self.triangles = tuple(tuple(int(value) for value in triangle) for triangle in built.mesh.triangles)
                owners = [""] * len(self.triangles)
                for patch_id, (start, end) in built.patch_triangle_ranges.items():
                    for index in range(max(0, int(start)), min(len(owners), int(end))):
                        owners[index] = str(patch_id)
                self.patch_by_triangle = tuple(owners)
                self.build_mode = "canonical"
                if self.triangles:
                    return True

            # A single invalid/ambiguous patch must not disable picking for the
            # entire Cloth document.  Rendering already shows each patch
            # independently, so build the same conservative per-patch fallback.
            # This is especially important for exact technical faces created by
            # Take face on curved source geometry.
            vertices: list[Point3] = []
            triangles: list[tuple[int, int, int]] = []
            owners: list[str] = []
            for patch_id, patch in document.patches.items():
                boundary = tuple(sample_patch_boundary(document, patch, arc_segments=24))
                frame = patch_frame(document, patch)
                if frame is None or len(boundary) < 3:
                    continue
                local = [frame.project(point) for point in boundary]
                local_triangles = tuple(triangulate_simple_polygon(local))
                if not local_triangles:
                    continue
                start = len(vertices)
                vertices.extend(tuple(float(value) for value in point) for point in boundary)
                for triangle in local_triangles:
                    try:
                        indices = tuple(start + int(index) for index in triangle)
                    except Exception:
                        continue
                    if len(set(indices)) != 3:
                        continue
                    triangles.append(indices)
                    owners.append(str(patch_id))
            self.vertices = tuple(vertices)
            self.triangles = tuple(triangles)
            self.patch_by_triangle = tuple(owners)
            self.build_mode = "per_patch_fallback" if self.triangles else "failed"
            return bool(self.triangles)
        except Exception as exc:
            self.vertices = ()
            self.triangles = ()
            self.patch_by_triangle = ()
            self.build_mode = "exception"
            self.build_issues = (*self.build_issues, f"{type(exc).__name__}: {exc}")
            return False

    def hit(self, ctx: Any, document: ClothDocument, screen_pos: Point2) -> ClothSurfaceRayHit | None:
        if not self._ensure(document):
            return None
        try:
            ray = ctx.pick.ray(screen_pos)
        except Exception:
            return None
        origin = _point3_or_none(getattr(ray, "world_pos", None))
        metadata = dict(getattr(ray, "metadata", {}) or {})
        direction = _point3_or_none(metadata.get("direction") or getattr(ray, "normal", None))
        direction = _unit3(direction) if direction is not None else None
        if origin is None or direction is None:
            return None
        best: tuple[float, int] | None = None
        for index, triangle in enumerate(self.triangles):
            try:
                a, b, c = (self.vertices[vertex] for vertex in triangle)
            except Exception:
                continue
            distance = _ray_triangle_distance(origin, direction, a, b, c)
            if distance is None:
                continue
            if best is None or distance < best[0]:
                best = (distance, index)
        if best is None:
            return None
        distance, triangle_index = best
        patch_id = self.patch_by_triangle[triangle_index] if triangle_index < len(self.patch_by_triangle) else ""
        if not patch_id or patch_id not in document.patches:
            return None
        world = tuple(origin[axis] + direction[axis] * distance for axis in range(3))
        triangle = self.triangles[triangle_index]
        a, b, c = (self.vertices[vertex] for vertex in triangle)
        normal = _triangle_unit_normal(a, b, c) or (0.0, 0.0, 1.0)
        return ClothSurfaceRayHit(patch_id, world, float(distance), int(triangle_index), normal)


def pick_ray_direction(ctx: Any, screen_pos: Point2) -> Point3 | None:
    """Return the normalized world-space camera ray direction."""

    try:
        ray = ctx.pick.ray(screen_pos)
    except Exception:
        return None
    metadata = dict(getattr(ray, "metadata", {}) or {})
    direction = _point3_or_none(metadata.get("direction") or getattr(ray, "normal", None))
    return _unit3(direction) if direction is not None else None


def pick_distance_along_ray(ctx: Any, screen_pos: Point2, world_pos: Any) -> float | None:
    """Return positive camera-ray distance for an existing scene pick."""

    try:
        ray = ctx.pick.ray(screen_pos)
    except Exception:
        return None
    origin = _point3_or_none(getattr(ray, "world_pos", None))
    metadata = dict(getattr(ray, "metadata", {}) or {})
    direction = _point3_or_none(metadata.get("direction") or getattr(ray, "normal", None))
    target = _point3_or_none(world_pos)
    direction = _unit3(direction) if direction is not None else None
    if origin is None or direction is None or target is None:
        return None
    distance = sum((target[index] - origin[index]) * direction[index] for index in range(3))
    return float(distance) if distance >= -1.0e-7 else None


def _point3_or_none(value: Any) -> Point3 | None:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return None


def _unit3(value: Point3) -> Point3 | None:
    length = math.sqrt(sum(component * component for component in value))
    if length <= 1.0e-12:
        return None
    return tuple(component / length for component in value)  # type: ignore[return-value]


def _triangle_unit_normal(a: Point3, b: Point3, c: Point3) -> Point3 | None:
    edge1 = tuple(b[index] - a[index] for index in range(3))
    edge2 = tuple(c[index] - a[index] for index in range(3))
    cross = (
        edge1[1] * edge2[2] - edge1[2] * edge2[1],
        edge1[2] * edge2[0] - edge1[0] * edge2[2],
        edge1[0] * edge2[1] - edge1[1] * edge2[0],
    )
    return _unit3(cross)


def _ray_triangle_distance(origin: Point3, direction: Point3, a: Point3, b: Point3, c: Point3) -> float | None:
    """Double-sided Möller–Trumbore intersection distance."""

    edge1 = tuple(b[index] - a[index] for index in range(3))
    edge2 = tuple(c[index] - a[index] for index in range(3))
    pvec = (
        direction[1] * edge2[2] - direction[2] * edge2[1],
        direction[2] * edge2[0] - direction[0] * edge2[2],
        direction[0] * edge2[1] - direction[1] * edge2[0],
    )
    determinant = sum(edge1[index] * pvec[index] for index in range(3))
    if abs(determinant) <= 1.0e-12:
        return None
    inverse = 1.0 / determinant
    tvec = tuple(origin[index] - a[index] for index in range(3))
    u = sum(tvec[index] * pvec[index] for index in range(3)) * inverse
    if u < -1.0e-9 or u > 1.0 + 1.0e-9:
        return None
    qvec = (
        tvec[1] * edge1[2] - tvec[2] * edge1[1],
        tvec[2] * edge1[0] - tvec[0] * edge1[2],
        tvec[0] * edge1[1] - tvec[1] * edge1[0],
    )
    v = sum(direction[index] * qvec[index] for index in range(3)) * inverse
    if v < -1.0e-9 or u + v > 1.0 + 1.0e-9:
        return None
    distance = sum(edge2[index] * qvec[index] for index in range(3)) * inverse
    return float(distance) if distance > 1.0e-7 else None


__all__ = [
    "ClothSnapTargetCache",
    "ClothSurfaceRayHit",
    "ClothSurfaceRaycastCache",
    "cloth_snap_targets",
    "face_vertices_for_pick",
    "nearest_document_curve",
    "nearest_document_point",
    "object_from_pick",
    "point_id_from_snap_source",
    "pick_distance_along_ray",
    "pick_ray_direction",
]
