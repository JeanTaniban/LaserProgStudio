# -*- coding: utf-8 -*-
"""Headless intelligent surface-region selection.

The module works only with immutable mesh snapshots and contains no Qt/VTK
imports.  It is suitable for Cloth, engraving, material painting and future
surface-aware tools.  The first public consumer is the dedicated API test tool.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import heapq
import math
import struct
import time
from typing import Any, Callable, Iterable, Sequence

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
EdgeKey = tuple[int, int]
SurfaceSelectionDiagnosticSink = Callable[[str, dict[str, Any]], None]


def _emit_diagnostic(sink: SurfaceSelectionDiagnosticSink | None, stage: str, **payload: Any) -> None:
    if sink is None:
        return
    try:
        sink(str(stage), dict(payload))
    except Exception:
        pass


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


def _edge_key(a: int, b: int) -> EdgeKey:
    return (a, b) if a < b else (b, a)


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(value: Point3) -> float:
    return math.sqrt(max(0.0, _dot(value, value)))


def _normalized(value: Point3) -> Point3:
    length = _length(value)
    if length <= 1.0e-15:
        return (0.0, 0.0, 1.0)
    return (value[0] / length, value[1] / length, value[2] / length)


def _angle_degrees(a: Point3, b: Point3) -> float:
    # Snapshot normals are consistently oriented per connected manifold
    # component.  Do not use abs(dot): opposite sides of a rounded thin part
    # must remain 180 degrees apart instead of looking coplanar.
    cosine = max(-1.0, min(1.0, _dot(a, b)))
    return math.degrees(math.acos(cosine))


def _triangle_geometry(vertices: Sequence[Point3], triangle: Triangle) -> tuple[Point3, Point3, float]:
    a, b, c = (vertices[index] for index in triangle)
    cross = _cross(_sub(b, a), _sub(c, a))
    area = 0.5 * _length(cross)
    normal = _normalized(cross)
    centroid = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0)
    return normal, centroid, area


def _triangle_edge_direction(triangle: Triangle, edge: EdgeKey) -> int:
    for index in range(3):
        first = triangle[index]
        second = triangle[(index + 1) % 3]
        if (first, second) == edge:
            return 1
        if (second, first) == edge:
            return -1
    return 0


def _consistently_oriented_normals(
    triangles: Sequence[Triangle],
    raw_normals: Sequence[Point3],
    incidence: dict[EdgeKey, list[int]],
) -> tuple[Point3, ...]:
    """Repair inconsistent triangle winding without changing mesh topology."""

    links: list[list[tuple[int, int]]] = [[] for _ in triangles]
    for edge, faces in incidence.items():
        if len(faces) != 2:
            continue
        first, second = faces
        first_direction = _triangle_edge_direction(triangles[first], edge)
        second_direction = _triangle_edge_direction(triangles[second], edge)
        if not first_direction or not second_direction:
            continue
        relation = -first_direction * second_direction
        links[first].append((second, relation))
        links[second].append((first, relation))

    signs = [0] * len(triangles)
    for component_seed in range(len(triangles)):
        if signs[component_seed]:
            continue
        signs[component_seed] = 1
        stack = [component_seed]
        while stack:
            current = stack.pop()
            for neighbor, relation in links[current]:
                expected = signs[current] * relation
                if not signs[neighbor]:
                    signs[neighbor] = expected
                    stack.append(neighbor)
                # Conflicts can occur on non-orientable/non-manifold input.
                # Keep the first stable assignment rather than oscillating.

    return tuple(
        normal if signs[index] >= 0 else (-normal[0], -normal[1], -normal[2])
        for index, normal in enumerate(raw_normals)
    )


@dataclass(frozen=True, slots=True)
class SurfaceSelectionProfile:
    """Weights and hard barriers used by one semantic selection profile."""

    id: str = "cloth_support"
    local_angle_soft_degrees: float = 42.0
    seed_angle_soft_degrees: float = 96.0
    hard_dihedral_degrees: float = 82.0
    hard_seed_angle_degrees: float = 132.0
    distance_weight: float = 0.08
    local_angle_weight: float = 0.58
    seed_angle_weight: float = 0.26
    sliver_weight: float = 0.08
    allow_nonmanifold_crossing: bool = False

    @classmethod
    def cloth_support(cls) -> "SurfaceSelectionProfile":
        return cls()

    @classmethod
    def exact_face(cls) -> "SurfaceSelectionProfile":
        return cls(
            id="exact_face",
            local_angle_soft_degrees=12.0,
            seed_angle_soft_degrees=18.0,
            hard_dihedral_degrees=38.0,
            hard_seed_angle_degrees=58.0,
            distance_weight=0.03,
            local_angle_weight=0.68,
            seed_angle_weight=0.27,
            sliver_weight=0.02,
        )


@dataclass(frozen=True, slots=True)
class SurfaceMeshSnapshot:
    object_id: str
    name: str
    vertices: tuple[Point3, ...]
    triangles: tuple[Triangle, ...]
    normals: tuple[Point3, ...]
    centroids: tuple[Point3, ...]
    areas: tuple[float, ...]
    edge_faces: tuple[tuple[EdgeKey, tuple[int, ...]], ...]
    neighbors: tuple[tuple[int, ...], ...]
    neighbor_local_angles: tuple[tuple[float, ...], ...]
    shared_edges: tuple[tuple[tuple[int, int], EdgeKey], ...]
    diagonal: float
    total_area: float
    mean_area: float
    sliver_factors: tuple[float, ...]
    geometry_signature: str
    edge_face_lookup: dict[EdgeKey, tuple[int, ...]] = field(repr=False, compare=False)
    shared_edge_lookup: dict[tuple[int, int], EdgeKey] = field(repr=False, compare=False)
    revision_token: str = ""

    @classmethod
    def from_mesh(
        cls,
        mesh_or_object: Any,
        *,
        object_id: str | None = None,
        name: str | None = None,
        revision_token: str = "",
        diagnostics: SurfaceSelectionDiagnosticSink | None = None,
    ) -> "SurfaceMeshSnapshot":
        started_total = time.perf_counter()
        mesh = getattr(mesh_or_object, "mesh", None) or mesh_or_object
        started = time.perf_counter()
        vertices = tuple(_point3(value) for value in getattr(mesh, "vertices"))
        vertices_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        triangles = tuple(tuple(int(index) for index in value[:3]) for value in getattr(mesh, "triangles"))
        triangles_ms = (time.perf_counter() - started) * 1000.0
        if len(vertices) < 3 or not triangles:
            raise ValueError("Surface selection needs a non-empty triangular mesh.")
        if any(len(set(triangle)) != 3 or min(triangle) < 0 or max(triangle) >= len(vertices) for triangle in triangles):
            raise ValueError("Surface selection received invalid triangle indices.")
        started = time.perf_counter()
        geometry = tuple(_triangle_geometry(vertices, triangle) for triangle in triangles)
        geometry_ms = (time.perf_counter() - started) * 1000.0
        raw_normals = tuple(value[0] for value in geometry)
        centroids = tuple(value[1] for value in geometry)
        areas = tuple(value[2] for value in geometry)
        started = time.perf_counter()
        incidence: dict[EdgeKey, list[int]] = defaultdict(list)
        for face_index, triangle in enumerate(triangles):
            for index in range(3):
                incidence[_edge_key(triangle[index], triangle[(index + 1) % 3])].append(face_index)
        incidence_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        normals = _consistently_oriented_normals(triangles, raw_normals, incidence)
        orientation_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        neighbor_sets = [set() for _ in triangles]
        shared: list[tuple[tuple[int, int], EdgeKey]] = []
        for edge, faces in incidence.items():
            if len(faces) == 2:
                first, second = faces
                neighbor_sets[first].add(second)
                neighbor_sets[second].add(first)
                shared.append(((min(first, second), max(first, second)), edge))
        adjacency_ms = (time.perf_counter() - started) * 1000.0
        neighbors = tuple(tuple(sorted(values)) for values in neighbor_sets)
        started = time.perf_counter()
        neighbor_local_angles = tuple(
            tuple(_angle_degrees(normals[face_index], normals[neighbor]) for neighbor in face_neighbors)
            for face_index, face_neighbors in enumerate(neighbors)
        )
        local_angles_ms = (time.perf_counter() - started) * 1000.0
        xs, ys, zs = zip(*vertices)
        diagonal = max(1.0e-9, math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))))
        resolved_id = str(object_id or getattr(mesh, "mesh_id", "") or getattr(mesh_or_object, "id", "") or id(mesh))
        resolved_name = str(name or getattr(mesh_or_object, "name", "") or getattr(mesh, "name", "") or "Mesh")
        edge_faces = tuple(sorted((edge, tuple(faces)) for edge, faces in incidence.items()))
        shared_edges = tuple(sorted(shared))
        total_area = sum(areas)
        mean_area = total_area / max(1, len(areas))
        sliver_factors = tuple(max(0.0, min(1.0, 1.0 - area / max(1.0e-12, mean_area))) for area in areas)
        started = time.perf_counter()
        digest = hashlib.blake2b(digest_size=16)
        for vertex in vertices:
            digest.update(struct.pack("<3d", *vertex))
        for triangle in triangles:
            digest.update(struct.pack("<3q", *triangle))
        geometry_signature = digest.hexdigest()
        signature_ms = (time.perf_counter() - started) * 1000.0
        snapshot = cls(
            resolved_id,
            resolved_name,
            vertices,
            triangles,
            normals,
            centroids,
            areas,
            edge_faces,
            neighbors,
            neighbor_local_angles,
            shared_edges,
            diagonal,
            total_area,
            mean_area,
            sliver_factors,
            geometry_signature,
            dict(edge_faces),
            dict(shared_edges),
            str(revision_token),
        )
        _emit_diagnostic(
            diagnostics,
            "snapshot.build",
            elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
            vertices_ms=vertices_ms,
            triangles_ms=triangles_ms,
            geometry_ms=geometry_ms,
            incidence_ms=incidence_ms,
            orientation_ms=orientation_ms,
            adjacency_ms=adjacency_ms,
            local_angles_ms=local_angles_ms,
            signature_ms=signature_ms,
            object_id=resolved_id,
            object_name=resolved_name,
            mesh_vertices=len(vertices),
            mesh_faces=len(triangles),
            mesh_edges=len(edge_faces),
            revision=str(revision_token),
            geometry_signature=geometry_signature,
        )
        return snapshot

    @property
    def edge_face_map(self) -> dict[EdgeKey, tuple[int, ...]]:
        return self.edge_face_lookup

    @property
    def shared_edge_map(self) -> dict[tuple[int, int], EdgeKey]:
        return self.shared_edge_lookup


@dataclass(frozen=True, slots=True)
class SurfaceRegionMetrics:
    face_count: int
    area: float
    area_ratio: float
    boundary_edge_count: int
    boundary_length: float
    compactness: float
    mean_seed_angle_degrees: float
    maximum_seed_angle_degrees: float
    maximum_local_angle_degrees: float


@dataclass(frozen=True, slots=True)
class SurfaceRegionResult:
    object_id: str
    seed_face: int
    face_indices: tuple[int, ...]
    boundary_edges: tuple[EdgeKey, ...]
    boundary_loops: tuple[tuple[int, ...], ...]
    tolerance: float
    automatic: bool
    confidence: float
    metrics: SurfaceRegionMetrics
    alternatives: tuple[tuple[float, tuple[int, ...]], ...] = ()
    explanation: str = ""

    @property
    def empty(self) -> bool:
        return not self.face_indices


@dataclass(frozen=True, slots=True)
class SurfaceAccessibilityField:
    """Minimum continuity cost required to reach every face from one seed.

    The field is the expensive part of logical selection.  Once available,
    manual tolerances and the forty Auto samples are only threshold lookups.
    """

    object_id: str
    geometry_signature: str
    seed_face: int
    profile_id: str
    excluded_faces: tuple[int, ...]
    costs: tuple[float, ...]
    sorted_faces: tuple[int, ...]
    sorted_costs: tuple[float, ...]
    queue_pops: int
    neighbor_visits: int
    crossing_evaluations: int
    heap_pushes: int
    hard_barriers: int
    elapsed_ms: float

    def faces_at(self, tolerance: float) -> tuple[int, ...]:
        count = bisect_right(self.sorted_costs, _threshold(tolerance))
        return self.sorted_faces[:count]


def _profile_signature(profile: SurfaceSelectionProfile) -> tuple[Any, ...]:
    return (
        profile.id,
        profile.local_angle_soft_degrees,
        profile.seed_angle_soft_degrees,
        profile.hard_dihedral_degrees,
        profile.hard_seed_angle_degrees,
        profile.distance_weight,
        profile.local_angle_weight,
        profile.seed_angle_weight,
        profile.sliver_weight,
        profile.allow_nonmanifold_crossing,
    )


@dataclass(slots=True)
class SurfaceSelectionCache:
    """Bounded progressive cache shared by hover, click and slider updates."""

    max_fields: int = 192
    max_results: int = 384
    logical_reuse: bool = False
    _fields: OrderedDict[tuple[Any, ...], SurfaceAccessibilityField] = field(default_factory=OrderedDict, init=False, repr=False)
    _auto_results: OrderedDict[tuple[Any, ...], SurfaceRegionResult] = field(default_factory=OrderedDict, init=False, repr=False)
    _manual_results: OrderedDict[tuple[Any, ...], SurfaceRegionResult] = field(default_factory=OrderedDict, init=False, repr=False)
    _logical_regions: dict[tuple[Any, ...], SurfaceRegionResult] = field(default_factory=dict, init=False, repr=False)
    field_hits: int = 0
    field_misses: int = 0
    result_hits: int = 0
    logical_hits: int = 0

    @staticmethod
    def _mesh_key(snapshot: SurfaceMeshSnapshot) -> tuple[str, str, str]:
        return (snapshot.object_id, snapshot.revision_token, snapshot.geometry_signature)

    @staticmethod
    def _constraints(values: Iterable[int]) -> tuple[int, ...]:
        return tuple(sorted({int(value) for value in values}))

    def _field_key(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        profile: SurfaceSelectionProfile,
        excluded_faces: Iterable[int],
    ) -> tuple[Any, ...]:
        return (*self._mesh_key(snapshot), _profile_signature(profile), int(seed_face), self._constraints(excluded_faces))

    def _result_key(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        profile: SurfaceSelectionProfile,
        required_faces: Iterable[int],
        excluded_faces: Iterable[int],
    ) -> tuple[Any, ...]:
        return (
            *self._mesh_key(snapshot),
            _profile_signature(profile),
            int(seed_face),
            self._constraints(required_faces),
            self._constraints(excluded_faces),
        )

    @staticmethod
    def _put_bounded(store: OrderedDict, key: tuple[Any, ...], value: Any, limit: int) -> None:
        store[key] = value
        store.move_to_end(key)
        while len(store) > max(1, int(limit)):
            store.popitem(last=False)

    def clear(self) -> None:
        self._fields.clear()
        self._auto_results.clear()
        self._manual_results.clear()
        self._logical_regions.clear()
        self.field_hits = 0
        self.field_misses = 0
        self.result_hits = 0
        self.logical_hits = 0

    def invalidate_object(self, object_id: str) -> None:
        prefix = str(object_id)
        for store in (self._fields, self._auto_results, self._manual_results):
            for key in tuple(store):
                if key and key[0] == prefix:
                    store.pop(key, None)
        for key in tuple(self._logical_regions):
            if key and key[0] == prefix:
                self._logical_regions.pop(key, None)

    def get_field(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        profile: SurfaceSelectionProfile,
        excluded_faces: Iterable[int],
    ) -> SurfaceAccessibilityField | None:
        key = self._field_key(snapshot, seed_face, profile, excluded_faces)
        value = self._fields.get(key)
        if value is None:
            self.field_misses += 1
            return None
        self.field_hits += 1
        self._fields.move_to_end(key)
        return value

    def put_field(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        profile: SurfaceSelectionProfile,
        excluded_faces: Iterable[int],
        value: SurfaceAccessibilityField,
    ) -> None:
        self._put_bounded(self._fields, self._field_key(snapshot, seed_face, profile, excluded_faces), value, self.max_fields)

    def get_auto(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        profile: SurfaceSelectionProfile,
        required_faces: Iterable[int],
        excluded_faces: Iterable[int],
    ) -> tuple[SurfaceRegionResult | None, str]:
        key = self._result_key(snapshot, seed_face, profile, required_faces, excluded_faces)
        exact = self._auto_results.get(key)
        if exact is not None:
            self.result_hits += 1
            self._auto_results.move_to_end(key)
            return exact, "exact"
        if not self.logical_reuse or tuple(required_faces) or tuple(excluded_faces):
            return None, "miss"
        logical_key = (*self._mesh_key(snapshot), _profile_signature(profile), int(seed_face))
        logical = self._logical_regions.get(logical_key)
        if logical is None:
            return None, "miss"
        self.logical_hits += 1
        return _retarget_region_result(snapshot, logical, int(seed_face), automatic=True), "logical"

    def put_auto(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        profile: SurfaceSelectionProfile,
        required_faces: Iterable[int],
        excluded_faces: Iterable[int],
        value: SurfaceRegionResult,
    ) -> None:
        key = self._result_key(snapshot, seed_face, profile, required_faces, excluded_faces)
        self._put_bounded(self._auto_results, key, value, self.max_results)
        if not self.logical_reuse or tuple(required_faces) or tuple(excluded_faces):
            return
        total_faces = max(1, len(snapshot.triangles))
        if value.confidence < 0.58 or value.metrics.face_count <= 1 or value.metrics.face_count / total_faces > 0.96:
            return
        base = (*self._mesh_key(snapshot), _profile_signature(profile))
        if len(self._logical_regions) > 100_000:
            self._logical_regions.clear()

        # Never teach the cache that every triangle in a detected region is an
        # equivalent seed.  Auto is seed-relative, especially on curved meshes.
        # Only a conservative, flat interior core may reuse the region.
        boundary = set(value.boundary_edges)
        source_normal = snapshot.normals[int(value.seed_face)]
        maximum_reuse_angle = min(8.0, max(2.0, profile.local_angle_soft_degrees * 0.20))
        for face_index in value.face_indices:
            triangle = snapshot.triangles[int(face_index)]
            triangle_edges = {
                _edge_key(triangle[0], triangle[1]),
                _edge_key(triangle[1], triangle[2]),
                _edge_key(triangle[2], triangle[0]),
            }
            if triangle_edges & boundary:
                continue
            if _angle_degrees(source_normal, snapshot.normals[int(face_index)]) > maximum_reuse_angle:
                continue
            self._logical_regions[(base[0], base[1], base[2], base[3], int(face_index))] = value

    def get_manual(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        tolerance: float,
        profile: SurfaceSelectionProfile,
        required_faces: Iterable[int],
        excluded_faces: Iterable[int],
    ) -> SurfaceRegionResult | None:
        key = (*self._result_key(snapshot, seed_face, profile, required_faces, excluded_faces), round(float(tolerance), 4))
        value = self._manual_results.get(key)
        if value is not None:
            self.result_hits += 1
            self._manual_results.move_to_end(key)
        return value

    def put_manual(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        tolerance: float,
        profile: SurfaceSelectionProfile,
        required_faces: Iterable[int],
        excluded_faces: Iterable[int],
        value: SurfaceRegionResult,
    ) -> None:
        key = (*self._result_key(snapshot, seed_face, profile, required_faces, excluded_faces), round(float(tolerance), 4))
        self._put_bounded(self._manual_results, key, value, self.max_results)


class SurfaceSelectionPointerState(str, Enum):
    """Low-level pointer states shared by surface-selection tools."""

    READY = "ready"
    PRESSED = "pressed"
    DRAGGING = "dragging"
    DOUBLE_CLICK_GUARD = "double_click_guard"  # legacy explicit-event compatibility


class SurfaceSelectionPointerAction(str, Enum):
    """Gesture emitted by :class:`SurfaceSelectionPointerMachine`."""

    NONE = "none"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"


@dataclass(slots=True)
class SurfaceSelectionPointerMachine:
    """Deterministic click/drag/double-click state machine.

    Qt's platform double-click interval is intentionally not used: on several
    systems it is permissive enough that two visibly separate clicks are
    reported as a double-click.  This machine recognises the double-click from
    two completed click releases using its own shorter interval.

    Native ``MouseButtonDblClick`` events should be routed to :meth:`press` and
    the following release must still be routed to :meth:`release`.
    """

    drag_threshold_px: float = 6.0
    double_click_interval_ms: float = 260.0
    double_click_distance_px: float = 7.0
    state: SurfaceSelectionPointerState = SurfaceSelectionPointerState.READY
    press_screen: tuple[float, float] | None = None
    last_click_screen: tuple[float, float] | None = None
    last_click_time_s: float | None = None

    def reset(self, *, keep_click_history: bool = False) -> None:
        self.state = SurfaceSelectionPointerState.READY
        self.press_screen = None
        if not keep_click_history:
            self.last_click_screen = None
            self.last_click_time_s = None

    def press(self, screen_pos: tuple[float, float], *, now_s: float | None = None) -> None:  # noqa: ARG002
        self.state = SurfaceSelectionPointerState.PRESSED
        self.press_screen = (float(screen_pos[0]), float(screen_pos[1]))

    def move(self, screen_pos: tuple[float, float]) -> SurfaceSelectionPointerAction:
        if self.state is not SurfaceSelectionPointerState.PRESSED or self.press_screen is None:
            return SurfaceSelectionPointerAction.NONE
        if math.hypot(float(screen_pos[0]) - self.press_screen[0], float(screen_pos[1]) - self.press_screen[1]) > self.drag_threshold_px:
            self.state = SurfaceSelectionPointerState.DRAGGING
        return SurfaceSelectionPointerAction.NONE

    def begin_camera_drag(self) -> None:
        if self.state is SurfaceSelectionPointerState.PRESSED:
            self.state = SurfaceSelectionPointerState.DRAGGING

    def double_click(self, screen_pos: tuple[float, float]) -> SurfaceSelectionPointerAction:
        """Legacy explicit double-click hook.

        New tools should route the native event through :meth:`press` and let
        :meth:`release` apply ``double_click_interval_ms``.  This method remains
        for older consumers that already resolved timing upstream.
        """

        self.state = SurfaceSelectionPointerState.DOUBLE_CLICK_GUARD
        self.press_screen = (float(screen_pos[0]), float(screen_pos[1]))
        self.cancel_pending_click()
        return SurfaceSelectionPointerAction.DOUBLE_CLICK

    def cancel_pending_click(self) -> None:
        """Forget a possible first click without changing drag state."""

        self.last_click_screen = None
        self.last_click_time_s = None

    def release(
        self,
        screen_pos: tuple[float, float],
        *,
        now_s: float | None = None,
    ) -> SurfaceSelectionPointerAction:
        point = (float(screen_pos[0]), float(screen_pos[1]))
        if self.state is SurfaceSelectionPointerState.DOUBLE_CLICK_GUARD:
            self.reset()
            return SurfaceSelectionPointerAction.NONE
        if self.state is SurfaceSelectionPointerState.DRAGGING:
            self.reset(keep_click_history=True)
            return SurfaceSelectionPointerAction.NONE
        if self.state is not SurfaceSelectionPointerState.PRESSED or self.press_screen is None:
            self.reset(keep_click_history=True)
            return SurfaceSelectionPointerAction.NONE
        press = self.press_screen
        self.reset(keep_click_history=True)
        if math.hypot(point[0] - press[0], point[1] - press[1]) > self.drag_threshold_px:
            return SurfaceSelectionPointerAction.NONE

        current_time = time.monotonic() if now_s is None else float(now_s)
        previous_time = self.last_click_time_s
        previous_point = self.last_click_screen
        if (
            previous_time is not None
            and previous_point is not None
            and 0.0 <= (current_time - previous_time) * 1000.0 <= self.double_click_interval_ms
            and math.hypot(point[0] - previous_point[0], point[1] - previous_point[1]) <= self.double_click_distance_px
        ):
            self.last_click_time_s = None
            self.last_click_screen = None
            return SurfaceSelectionPointerAction.DOUBLE_CLICK

        self.last_click_time_s = current_time
        self.last_click_screen = point
        return SurfaceSelectionPointerAction.CLICK


class SurfaceSelectionMeshPolicy(str, Enum):
    """How a semantic selection behaves when another mesh is shift-clicked."""

    SINGLE_MESH = "single_mesh"
    MULTIPLE_MESHES = "multiple_meshes"


@dataclass(slots=True)
class _SurfaceSelectionMeshState:
    snapshot: SurfaceMeshSnapshot
    selected_regions: list[frozenset[int]]
    result: SurfaceRegionResult


@dataclass(slots=True)
class SurfaceSelectionSession:
    """Mutable semantic selection composed of algorithmic logical regions.

    ``mesh_policy`` is deliberately explicit.  Tools such as material painting
    can enforce a single source mesh, while Cloth can select supporting faces
    on several independent scene meshes in one operation.

    The legacy ``snapshot``/``result`` attributes always refer to the most
    recently touched mesh.  Multi-mesh consumers should use
    :attr:`selected_items` or :attr:`selected_faces_by_object`.
    """

    snapshot: SurfaceMeshSnapshot | None = None
    seed_face: int | None = None
    tolerance: float = 0.35
    automatic: bool = True
    mesh_policy: SurfaceSelectionMeshPolicy = SurfaceSelectionMeshPolicy.SINGLE_MESH
    region_merge_angle_degrees: float = 55.0
    required_faces: set[int] = field(default_factory=set)
    excluded_faces: set[int] = field(default_factory=set)
    explicit_faces: set[int] = field(default_factory=set)
    selected_regions: list[frozenset[int]] = field(default_factory=list)
    result: SurfaceRegionResult | None = None
    cache: SurfaceSelectionCache = field(default_factory=SurfaceSelectionCache)
    _mesh_states: "OrderedDict[str, _SurfaceSelectionMeshState]" = field(default_factory=OrderedDict, repr=False)

    @property
    def selection_mode(self) -> str:
        if not self._mesh_states and self.result is None:
            return "empty"
        if self.selected_region_count > 1 or self.selected_mesh_count > 1:
            return "multiple"
        return "automatic" if self.result is not None and self.result.automatic else "exact"

    @property
    def selected_region_count(self) -> int:
        if self._mesh_states:
            return sum(len(state.selected_regions) for state in self._mesh_states.values())
        return len(self.selected_regions)

    @property
    def selected_mesh_count(self) -> int:
        return len(self._mesh_states) if self._mesh_states else (1 if self.result is not None else 0)

    @property
    def selected_face_indices(self) -> tuple[int, ...]:
        """Faces on the active mesh, retained for single-mesh compatibility."""

        if self.result is not None:
            return self.result.face_indices
        return tuple(sorted(self.explicit_faces))

    @property
    def selected_items(self) -> tuple[tuple[SurfaceMeshSnapshot, SurfaceRegionResult], ...]:
        if self._mesh_states:
            return tuple((state.snapshot, state.result) for state in self._mesh_states.values())
        if self.snapshot is not None and self.result is not None:
            return ((self.snapshot, self.result),)
        return ()

    @property
    def selected_faces_by_object(self) -> dict[str, tuple[int, ...]]:
        return {snapshot.object_id: result.face_indices for snapshot, result in self.selected_items}

    def _same_mesh(self, snapshot: SurfaceMeshSnapshot) -> bool:
        return bool(
            self.snapshot is not None
            and self.snapshot.object_id == snapshot.object_id
            and self.snapshot.revision_token == snapshot.revision_token
            and self.snapshot.geometry_signature == snapshot.geometry_signature
        )

    @staticmethod
    def _state_matches(snapshot: SurfaceMeshSnapshot, state: _SurfaceSelectionMeshState) -> bool:
        return bool(
            state.snapshot.object_id == snapshot.object_id
            and state.snapshot.revision_token == snapshot.revision_token
            and state.snapshot.geometry_signature == snapshot.geometry_signature
        )

    def _bind_snapshot(self, snapshot: SurfaceMeshSnapshot, seed_face: int, *, preserve: bool) -> None:
        same_mesh = self._same_mesh(snapshot)
        self.snapshot = snapshot
        self.seed_face = int(seed_face)
        if not same_mesh or not preserve:
            self.required_faces.clear()
            self.excluded_faces.clear()
            if not preserve:
                self.explicit_faces.clear()
                self.selected_regions.clear()
        self.excluded_faces.discard(int(seed_face))

    def _activate_state(self, state: _SurfaceSelectionMeshState) -> None:
        self.snapshot = state.snapshot
        self.result = state.result
        self.selected_regions = list(state.selected_regions)
        self.explicit_faces = set(state.result.face_indices) if len(state.selected_regions) > 1 else set()
        self.seed_face = int(state.result.seed_face)
        self.required_faces.clear()
        self.excluded_faces.clear()
        if state.result.automatic:
            self.tolerance = state.result.tolerance

    def _store_active_state(self) -> None:
        if self.snapshot is None or self.result is None:
            return
        regions = list(self.selected_regions) or [frozenset(int(face) for face in self.result.face_indices)]
        regions = _merge_touching_surface_regions(
            self.snapshot, regions, max_dihedral_degrees=self.region_merge_angle_degrees
        )
        if regions:
            faces = set().union(*regions)
            seed = int(self.result.seed_face) if int(self.result.seed_face) in faces else min(faces)
            if tuple(sorted(faces)) != tuple(self.result.face_indices) or len(regions) != len(self.selected_regions):
                self.result = surface_region_from_faces(
                    self.snapshot,
                    faces,
                    seed_face=seed,
                    explanation=(
                        f"{len(regions)} cleaned logical region(s), "
                        f"{len(faces)} unique triangle(s) selected on {self.snapshot.name}."
                    ),
                )
            self.selected_regions = list(regions)
        self._mesh_states[self.snapshot.object_id] = _SurfaceSelectionMeshState(
            self.snapshot, list(self.selected_regions), self.result
        )
        self._mesh_states.move_to_end(self.snapshot.object_id)

    def bind(
        self,
        snapshot: SurfaceMeshSnapshot,
        seed_face: int,
        *,
        profile: SurfaceSelectionProfile | None = None,
        diagnostics: SurfaceSelectionDiagnosticSink | None = None,
    ) -> SurfaceRegionResult:
        """Solve and replace the complete selection with one logical region."""

        self.clear()
        self._bind_snapshot(snapshot, seed_face, preserve=False)
        return self.recompute(profile=profile, diagnostics=diagnostics)

    def select_face(self, snapshot: SurfaceMeshSnapshot, face_index: int) -> SurfaceRegionResult:
        """Replace the complete selection with one exact triangle."""

        index = int(face_index)
        if not 0 <= index < len(snapshot.triangles):
            raise ValueError("Face index is outside the mesh snapshot.")
        self.clear()
        self._bind_snapshot(snapshot, index, preserve=False)
        self.explicit_faces = {index}
        self.selected_regions = [frozenset({index})]
        self.result = surface_region_from_faces(snapshot, self.explicit_faces, seed_face=index)
        self._store_active_state()
        return self.result

    def add_region(self, snapshot: SurfaceMeshSnapshot, region: SurfaceRegionResult) -> SurfaceRegionResult:
        """Union one complete algorithmic region according to ``mesh_policy``."""

        if region.object_id != snapshot.object_id:
            raise ValueError("Cannot add a surface region whose result and snapshot disagree.")
        state = self._mesh_states.get(snapshot.object_id)
        if state is not None and not self._state_matches(snapshot, state):
            self._mesh_states.pop(snapshot.object_id, None)
            state = None

        if state is None and self._mesh_states and self.mesh_policy is SurfaceSelectionMeshPolicy.SINGLE_MESH:
            return self.adopt(snapshot, region)
        if state is None:
            new_state = _SurfaceSelectionMeshState(
                snapshot,
                [frozenset(int(face) for face in region.face_indices)],
                region,
            )
            self._mesh_states[snapshot.object_id] = new_state
            self._mesh_states.move_to_end(snapshot.object_id)
            self._activate_state(new_state)
            return region

        existing = list(state.selected_regions)
        candidate = frozenset(int(face) for face in region.face_indices)
        if not candidate:
            self._activate_state(state)
            return state.result
        previous_cleaned = _merge_touching_surface_regions(
            snapshot, existing, max_dihedral_degrees=self.region_merge_angle_degrees
        )
        cleaned = _merge_touching_surface_regions(
            snapshot, (*existing, candidate), max_dihedral_degrees=self.region_merge_angle_degrees
        )
        faces = set().union(*cleaned) if cleaned else set()
        if not faces:
            self._activate_state(state)
            return state.result
        if cleaned == previous_cleaned and tuple(sorted(faces)) == tuple(state.result.face_indices):
            self._activate_state(state)
            return state.result
        seed = int(state.result.seed_face) if int(state.result.seed_face) in faces else int(region.seed_face)
        combined = surface_region_from_faces(
            snapshot,
            faces,
            seed_face=seed,
            explanation=(
                f"{len(cleaned)} cleaned logical region(s), "
                f"{len(faces)} unique triangle(s) selected on {snapshot.name}."
            ),
        )
        new_state = _SurfaceSelectionMeshState(snapshot, list(cleaned), combined)
        self._mesh_states[snapshot.object_id] = new_state
        self._mesh_states.move_to_end(snapshot.object_id)
        self._activate_state(new_state)
        return combined

    def remove_region(self, snapshot: SurfaceMeshSnapshot, region: SurfaceRegionResult) -> SurfaceRegionResult | None:
        """Subtract a complete algorithmic region from one selected mesh."""

        state = self._mesh_states.get(snapshot.object_id)
        if state is None or not self._state_matches(snapshot, state):
            return self.result
        removal = set(int(face) for face in region.face_indices)
        remaining_regions: list[frozenset[int]] = []
        for selected in state.selected_regions:
            remainder = frozenset(set(selected).difference(removal))
            if remainder:
                remaining_regions.append(remainder)
        if not remaining_regions:
            self._mesh_states.pop(snapshot.object_id, None)
            if not self._mesh_states:
                self.clear()
                return None
            last_state = next(reversed(self._mesh_states.values()))
            self._activate_state(last_state)
            return self.result
        faces = set().union(*remaining_regions)
        seed = int(state.result.seed_face) if int(state.result.seed_face) in faces else min(faces)
        combined = surface_region_from_faces(
            snapshot,
            faces,
            seed_face=seed,
            explanation=f"{len(remaining_regions)} logical region(s), {len(faces)} triangle(s) remain on {snapshot.name}.",
        )
        new_state = _SurfaceSelectionMeshState(snapshot, remaining_regions, combined)
        self._mesh_states[snapshot.object_id] = new_state
        self._mesh_states.move_to_end(snapshot.object_id)
        self._activate_state(new_state)
        return combined

    def adopt(self, snapshot: SurfaceMeshSnapshot, result: SurfaceRegionResult) -> SurfaceRegionResult:
        """Replace the complete selection with an already solved logical region."""

        if result.object_id != snapshot.object_id:
            raise ValueError("Cannot adopt a surface result from another mesh.")
        self.clear()
        self._bind_snapshot(snapshot, result.seed_face, preserve=False)
        self.selected_regions = [frozenset(int(face) for face in result.face_indices)]
        self.result = result
        if result.automatic:
            self.tolerance = result.tolerance
        self._store_active_state()
        return result

    def set_tolerance(self, value: float, *, profile: SurfaceSelectionProfile | None = None, diagnostics: SurfaceSelectionDiagnosticSink | None = None) -> SurfaceRegionResult | None:
        self.tolerance = max(0.0, min(1.0, float(value)))
        self.automatic = False
        return self.recompute(profile=profile, diagnostics=diagnostics) if self.snapshot is not None and self.seed_face is not None else None

    def set_automatic(self, enabled: bool, *, profile: SurfaceSelectionProfile | None = None, diagnostics: SurfaceSelectionDiagnosticSink | None = None) -> SurfaceRegionResult | None:
        self.automatic = bool(enabled)
        return self.recompute(profile=profile, diagnostics=diagnostics) if self.snapshot is not None and self.seed_face is not None else None

    def require(self, face_index: int, *, profile: SurfaceSelectionProfile | None = None, diagnostics: SurfaceSelectionDiagnosticSink | None = None) -> SurfaceRegionResult | None:
        index = int(face_index)
        self.excluded_faces.discard(index)
        self.required_faces.add(index)
        return self.recompute(profile=profile, diagnostics=diagnostics) if self.snapshot is not None and self.seed_face is not None else None

    def exclude(self, face_index: int, *, profile: SurfaceSelectionProfile | None = None, diagnostics: SurfaceSelectionDiagnosticSink | None = None) -> SurfaceRegionResult | None:
        index = int(face_index)
        if index != self.seed_face:
            self.required_faces.discard(index)
            self.excluded_faces.add(index)
        return self.recompute(profile=profile, diagnostics=diagnostics) if self.snapshot is not None and self.seed_face is not None else None

    def reset_constraints(self, *, profile: SurfaceSelectionProfile | None = None, diagnostics: SurfaceSelectionDiagnosticSink | None = None) -> SurfaceRegionResult | None:
        self.required_faces.clear()
        self.excluded_faces.clear()
        if self.snapshot is None or self.seed_face is None or len(self.selected_regions) > 1:
            return self.result
        return self.recompute(profile=profile, diagnostics=diagnostics)

    def clear(self) -> None:
        self.snapshot = None
        self.seed_face = None
        self.required_faces.clear()
        self.excluded_faces.clear()
        self.explicit_faces.clear()
        self.selected_regions.clear()
        self.result = None
        self._mesh_states.clear()

    def recompute(
        self,
        *,
        profile: SurfaceSelectionProfile | None = None,
        diagnostics: SurfaceSelectionDiagnosticSink | None = None,
    ) -> SurfaceRegionResult:
        if self.snapshot is None or self.seed_face is None:
            raise ValueError("No surface mesh and seed face are bound.")
        if len(self.selected_regions) > 1 or self.explicit_faces:
            self.result = surface_region_from_faces(self.snapshot, self.explicit_faces or set().union(*self.selected_regions), seed_face=self.seed_face)
            self._store_active_state()
            return self.result
        if self.automatic:
            result = auto_surface_region(
                self.snapshot,
                self.seed_face,
                profile=profile,
                required_faces=self.required_faces,
                excluded_faces=self.excluded_faces,
                cache=self.cache,
                diagnostics=diagnostics,
            )
            self.tolerance = result.tolerance
        else:
            result = select_surface_region(
                self.snapshot,
                self.seed_face,
                self.tolerance,
                profile=profile,
                required_faces=self.required_faces,
                excluded_faces=self.excluded_faces,
                cache=self.cache,
                diagnostics=diagnostics,
            )
        self.selected_regions = [frozenset(int(face) for face in result.face_indices)]
        self.explicit_faces.clear()
        self.result = result
        self._store_active_state()
        return result

def _merge_touching_surface_regions(
    snapshot: SurfaceMeshSnapshot,
    regions: Iterable[Iterable[int]],
    *,
    max_dihedral_degrees: float = 55.0,
) -> list[frozenset[int]]:
    """Return disjoint semantic regions with overlap/smooth adjacency cleaned.

    Shift-clicked automatic regions often overlap heavily. Keeping both raw
    regions made downstream tools believe that two panels had been selected,
    even though the user saw one continuous surface. Regions are therefore
    unioned when they share triangles, or when they meet along a sufficiently
    smooth mesh edge. A sharp corner (for example two cube sides) remains two
    intentional logical regions.
    """

    pending = [
        set(int(face) for face in region if 0 <= int(face) < len(snapshot.triangles))
        for region in regions
    ]
    pending = [region for region in pending if region]
    angle_limit = max(0.0, min(180.0, float(max_dihedral_degrees)))

    def smooth_pair(first_face: int, second_face: int) -> bool:
        return _angle_degrees(snapshot.normals[int(first_face)], snapshot.normals[int(second_face)]) <= angle_limit

    def vertex_key(index: int, quantum: float) -> tuple[int, int, int]:
        point = snapshot.vertices[int(index)]
        return tuple(int(round(float(value) / quantum)) for value in point)  # type: ignore[return-value]

    def geometric_edge_faces(
        region: set[int], quantum: float
    ) -> dict[tuple[tuple[int, int, int], tuple[int, int, int]], set[int]]:
        edges: dict[tuple[tuple[int, int, int], tuple[int, int, int]], set[int]] = {}
        for face in region:
            triangle = snapshot.triangles[int(face)]
            keys = tuple(vertex_key(vertex, quantum) for vertex in triangle)
            for edge_index in range(3):
                a = keys[edge_index]
                b = keys[(edge_index + 1) % 3]
                edge = (a, b) if a <= b else (b, a)
                edges.setdefault(edge, set()).add(int(face))
        return edges

    merged: list[set[int]] = []
    for candidate in pending:
        index = 0
        while index < len(merged):
            existing = merged[index]
            touches = bool(existing & candidate)
            if not touches:
                smaller, other = (existing, candidate) if len(existing) <= len(candidate) else (candidate, existing)
                touches = any(
                    smooth_pair(int(face), int(neighbor))
                    for face in smaller
                    for neighbor in snapshot.neighbors[int(face)]
                    if int(neighbor) in other
                )
            if not touches:
                # Boolean/repaired meshes can contain coincident vertices with
                # different indices. Compare geometric edge identities too.
                scale = max(float(snapshot.diagonal), 1.0)
                quantum = max(1.0e-9, scale * 1.0e-8)
                first_edges = geometric_edge_faces(existing, quantum)
                second_edges = geometric_edge_faces(candidate, quantum)
                for edge in first_edges.keys() & second_edges.keys():
                    if any(
                        smooth_pair(first_face, second_face)
                        for first_face in first_edges[edge]
                        for second_face in second_edges[edge]
                    ):
                        touches = True
                        break
            if touches:
                candidate.update(existing)
                merged.pop(index)
                index = 0
                continue
            index += 1
        merged.append(candidate)
    return [frozenset(region) for region in sorted(merged, key=lambda value: (min(value), len(value)))]


def _crossing_score(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    current: int,
    candidate: int,
    profile: SurfaceSelectionProfile,
) -> tuple[float, float, float]:
    try:
        neighbor_position = snapshot.neighbors[current].index(candidate)
        local_angle = snapshot.neighbor_local_angles[current][neighbor_position]
    except (ValueError, IndexError):
        local_angle = _angle_degrees(snapshot.normals[current], snapshot.normals[candidate])
    seed_angle = _angle_degrees(snapshot.normals[seed_face], snapshot.normals[candidate])
    local_term = (local_angle / max(1.0, profile.local_angle_soft_degrees)) ** 1.35
    seed_term = (seed_angle / max(1.0, profile.seed_angle_soft_degrees)) ** 1.20
    distance = math.dist(snapshot.centroids[seed_face], snapshot.centroids[candidate]) / snapshot.diagonal
    # Mean triangle area is cached in the immutable snapshot.  v149 recomputed
    # sum(snapshot.areas) for every candidate crossing, making region growth
    # accidentally O(E*F) on dense meshes.
    sliver = snapshot.sliver_factors[candidate]
    score = (
        profile.local_angle_weight * local_term
        + profile.seed_angle_weight * seed_term
        + profile.distance_weight * distance
        + profile.sliver_weight * sliver
    )
    return score, local_angle, seed_angle


def _build_accessibility_field(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    profile: SurfaceSelectionProfile,
    excluded_faces: Iterable[int] = (),
) -> SurfaceAccessibilityField:
    """Solve the minimax reachability field once for all continuity levels."""

    started = time.perf_counter()
    seed_face = int(seed_face)
    excluded = {int(value) for value in excluded_faces}
    excluded.discard(seed_face)
    face_count = len(snapshot.triangles)
    if not 0 <= seed_face < face_count:
        inf = tuple(float("inf") for _ in range(face_count))
        return SurfaceAccessibilityField(
            snapshot.object_id,
            snapshot.geometry_signature,
            seed_face,
            profile.id,
            tuple(sorted(excluded)),
            inf,
            (),
            (),
            0,
            0,
            0,
            0,
            0,
            (time.perf_counter() - started) * 1000.0,
        )

    seed_normal = snapshot.normals[seed_face]
    seed_centroid = snapshot.centroids[seed_face]
    static_terms = [0.0] * face_count
    seed_angles = [0.0] * face_count
    for candidate in range(face_count):
        seed_angle = _angle_degrees(seed_normal, snapshot.normals[candidate])
        seed_angles[candidate] = seed_angle
        seed_term = (seed_angle / max(1.0, profile.seed_angle_soft_degrees)) ** 1.20
        distance = math.dist(seed_centroid, snapshot.centroids[candidate]) / snapshot.diagonal
        static_terms[candidate] = (
            profile.seed_angle_weight * seed_term
            + profile.distance_weight * distance
            + profile.sliver_weight * snapshot.sliver_factors[candidate]
        )

    costs = [float("inf")] * face_count
    costs[seed_face] = 0.0
    queue: list[tuple[float, int]] = [(0.0, seed_face)]
    queue_pops = 0
    neighbor_visits = 0
    crossing_evaluations = 0
    heap_pushes = 1
    hard_barriers = 0
    while queue:
        path_cost, current = heapq.heappop(queue)
        queue_pops += 1
        if path_cost > costs[current]:
            continue
        current_neighbors = snapshot.neighbors[current]
        current_angles = snapshot.neighbor_local_angles[current]
        for position, candidate in enumerate(current_neighbors):
            neighbor_visits += 1
            if candidate in excluded:
                continue
            local_angle = current_angles[position]
            if (
                local_angle > profile.hard_dihedral_degrees
                or seed_angles[candidate] > profile.hard_seed_angle_degrees
            ):
                hard_barriers += 1
                continue
            if local_angle <= 0.20 and seed_angles[candidate] <= 0.35:
                # A triangulation diagonal must never split one geometrically
                # coplanar logical face.  Collapse its crossing cost so Auto and
                # the manual slider operate on semantic surfaces rather than on
                # arbitrary triangle density or centroid distance.
                crossing = 0.0
            else:
                local_term = (local_angle / max(1.0, profile.local_angle_soft_degrees)) ** 1.35
                crossing = profile.local_angle_weight * local_term + static_terms[candidate]
            crossing_evaluations += 1
            candidate_cost = max(path_cost, crossing)
            if candidate_cost < costs[candidate]:
                costs[candidate] = candidate_cost
                heapq.heappush(queue, (candidate_cost, candidate))
                heap_pushes += 1

    ordered = tuple(sorted((cost, index) for index, cost in enumerate(costs) if math.isfinite(cost)))
    return SurfaceAccessibilityField(
        snapshot.object_id,
        snapshot.geometry_signature,
        seed_face,
        profile.id,
        tuple(sorted(excluded)),
        tuple(costs),
        tuple(index for _cost, index in ordered),
        tuple(cost for cost, _index in ordered),
        queue_pops,
        neighbor_visits,
        crossing_evaluations,
        heap_pushes,
        hard_barriers,
        (time.perf_counter() - started) * 1000.0,
    )


def _accessibility_field(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    profile: SurfaceSelectionProfile,
    excluded_faces: Iterable[int],
    cache: SurfaceSelectionCache | None,
) -> tuple[SurfaceAccessibilityField, bool]:
    if cache is not None:
        cached = cache.get_field(snapshot, seed_face, profile, excluded_faces)
        if cached is not None:
            return cached, True
    field_value = _build_accessibility_field(snapshot, seed_face, profile, excluded_faces)
    if cache is not None:
        cache.put_field(snapshot, seed_face, profile, excluded_faces, field_value)
    return field_value, False


def _threshold(tolerance: float) -> float:
    value = max(0.0, min(1.0, float(tolerance)))
    return 0.018 + 1.32 * (value ** 2.15)


def _region_faces(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    tolerance: float,
    profile: SurfaceSelectionProfile,
    required_faces: set[int],
    excluded_faces: set[int],
) -> tuple[set[int], dict[str, int | float]]:
    if not 0 <= int(seed_face) < len(snapshot.triangles):
        return set(), {"queue_pops": 0, "neighbor_visits": 0, "crossing_evaluations": 0, "heap_pushes": 0}
    threshold = _threshold(tolerance)
    selected = {int(seed_face)}
    costs = {int(seed_face): 0.0}
    queue: list[tuple[float, int]] = [(0.0, int(seed_face))]
    queue_pops = 0
    neighbor_visits = 0
    crossing_evaluations = 0
    heap_pushes = 1
    excluded_skips = 0
    hard_barriers = 0
    while queue:
        path_cost, current = heapq.heappop(queue)
        queue_pops += 1
        if path_cost > costs.get(current, float("inf")):
            continue
        for candidate in snapshot.neighbors[current]:
            neighbor_visits += 1
            if candidate in excluded_faces:
                excluded_skips += 1
                continue
            score, local_angle, seed_angle = _crossing_score(snapshot, seed_face, current, candidate, profile)
            crossing_evaluations += 1
            if (
                local_angle > profile.hard_dihedral_degrees
                or seed_angle > profile.hard_seed_angle_degrees
            ) and candidate not in required_faces:
                hard_barriers += 1
                continue
            candidate_cost = max(path_cost, score)
            if candidate_cost <= threshold or candidate in required_faces:
                if candidate_cost < costs.get(candidate, float("inf")):
                    costs[candidate] = candidate_cost
                    selected.add(candidate)
                    heapq.heappush(queue, (candidate_cost, candidate))
                    heap_pushes += 1
    required_connections = 0
    required_search_pops = 0
    for required in tuple(required_faces):
        if required in selected or not 0 <= required < len(snapshot.triangles) or required in excluded_faces:
            continue
        connection_stats = _connect_required_face(snapshot, seed_face, required, selected, excluded_faces, profile)
        required_connections += 1
        required_search_pops += int(connection_stats.get("queue_pops", 0))
    return selected, {
        "threshold": threshold,
        "queue_pops": queue_pops,
        "neighbor_visits": neighbor_visits,
        "crossing_evaluations": crossing_evaluations,
        "heap_pushes": heap_pushes,
        "excluded_skips": excluded_skips,
        "hard_barriers": hard_barriers,
        "required_connections": required_connections,
        "required_search_pops": required_search_pops,
    }


def _connect_required_face(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    target: int,
    selected: set[int],
    excluded: set[int],
    profile: SurfaceSelectionProfile,
) -> dict[str, int]:
    queue: list[tuple[float, int]] = [(0.0, target)]
    cost = {target: 0.0}
    previous: dict[int, int] = {}
    meeting: int | None = None
    queue_pops = 0
    crossing_evaluations = 0
    while queue:
        value, current = heapq.heappop(queue)
        queue_pops += 1
        if current in selected:
            meeting = current
            break
        if value > cost.get(current, float("inf")):
            continue
        for neighbor in snapshot.neighbors[current]:
            if neighbor in excluded:
                continue
            crossing, local_angle, seed_angle = _crossing_score(snapshot, seed_face, current, neighbor, profile)
            crossing_evaluations += 1
            if (
                local_angle > min(89.0, profile.hard_dihedral_degrees + 5.0)
                or seed_angle > min(175.0, profile.hard_seed_angle_degrees + 12.0)
            ):
                continue
            next_value = value + crossing + 1.0e-6
            if next_value < cost.get(neighbor, float("inf")):
                cost[neighbor] = next_value
                previous[neighbor] = current
                heapq.heappush(queue, (next_value, neighbor))
    if meeting is None:
        selected.add(target)
        return {"queue_pops": queue_pops, "crossing_evaluations": crossing_evaluations, "path_faces": 1}
    current = meeting
    path_faces = 0
    while current != target:
        current = previous[current]
        selected.add(current)
        path_faces += 1
    return {"queue_pops": queue_pops, "crossing_evaluations": crossing_evaluations, "path_faces": path_faces}


def _boundary(snapshot: SurfaceMeshSnapshot, faces: set[int]) -> tuple[tuple[EdgeKey, ...], tuple[tuple[int, ...], ...]]:
    incidence = snapshot.edge_face_map
    edges = tuple(sorted(edge for edge, touching in incidence.items() if sum(1 for face in touching if face in faces) == 1))
    adjacency: dict[int, list[int]] = defaultdict(list)
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    remaining = set(edges)
    loops: list[tuple[int, ...]] = []
    while remaining:
        start_edge = min(remaining)
        start, current = start_edge
        loop = [start, current]
        remaining.remove(start_edge)
        previous = start
        while True:
            options = [value for value in adjacency[current] if _edge_key(current, value) in remaining and value != previous]
            if not options:
                if current != start and _edge_key(current, start) in remaining:
                    remaining.remove(_edge_key(current, start))
                break
            following = min(options)
            remaining.remove(_edge_key(current, following))
            previous, current = current, following
            if current == start:
                break
            loop.append(current)
            if len(loop) > len(edges) + 2:
                break
        if len(loop) >= 3:
            loops.append(tuple(loop))
    loops.sort(key=lambda loop: -sum(math.dist(snapshot.vertices[loop[i - 1]], snapshot.vertices[loop[i]]) for i in range(len(loop))))
    return edges, tuple(loops)


def _metrics(snapshot: SurfaceMeshSnapshot, seed_face: int, faces: set[int], boundary_edges: Sequence[EdgeKey]) -> SurfaceRegionMetrics:
    area = sum(snapshot.areas[index] for index in faces)
    total_area = max(1.0e-12, snapshot.total_area)
    boundary_length = sum(math.dist(snapshot.vertices[a], snapshot.vertices[b]) for a, b in boundary_edges)
    compactness = 0.0 if boundary_length <= 1.0e-12 else max(0.0, min(1.0, 4.0 * math.pi * area / (boundary_length * boundary_length)))
    seed_angles = [_angle_degrees(snapshot.normals[seed_face], snapshot.normals[index]) for index in faces]
    local_angles: list[float] = []
    for face in faces:
        local_angles.extend(_angle_degrees(snapshot.normals[face], snapshot.normals[neighbor]) for neighbor in snapshot.neighbors[face] if neighbor in faces and neighbor > face)
    return SurfaceRegionMetrics(
        len(faces),
        area,
        area / total_area,
        len(boundary_edges),
        boundary_length,
        compactness,
        sum(seed_angles) / max(1, len(seed_angles)),
        max(seed_angles, default=0.0),
        max(local_angles, default=0.0),
    )


def _confidence(metrics: SurfaceRegionMetrics, *, has_loop: bool) -> float:
    coherence = max(0.0, 1.0 - metrics.mean_seed_angle_degrees / 110.0)
    return max(
        0.0,
        min(
            1.0,
            0.62 * coherence
            + 0.23 * min(1.0, metrics.compactness * 2.4)
            + 0.15 * (1.0 if has_loop else 0.0),
        ),
    )


def _result_from_faces(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    faces: Iterable[int],
    tolerance: float,
    *,
    automatic: bool,
    alternatives: tuple[tuple[float, tuple[int, ...]], ...] = (),
    explanation: str | None = None,
) -> SurfaceRegionResult:
    face_set = {int(value) for value in faces}
    edges, loops = _boundary(snapshot, face_set)
    metrics = _metrics(snapshot, int(seed_face), face_set, edges)
    resolved_explanation = explanation or (
        f"{metrics.face_count} triangle(s), max local bend {metrics.maximum_local_angle_degrees:.1f}°, "
        f"max drift {metrics.maximum_seed_angle_degrees:.1f}°."
    )
    return SurfaceRegionResult(
        snapshot.object_id,
        int(seed_face),
        tuple(sorted(face_set)),
        edges,
        loops,
        max(0.0, min(1.0, float(tolerance))),
        bool(automatic),
        _confidence(metrics, has_loop=bool(loops)),
        metrics,
        alternatives,
        resolved_explanation,
    )



def surface_region_from_faces(
    snapshot: SurfaceMeshSnapshot,
    face_indices: Iterable[int],
    *,
    seed_face: int | None = None,
    explanation: str | None = None,
) -> SurfaceRegionResult:
    """Build one explicit editable selection from arbitrary mesh faces.

    Unlike the semantic solver, this function never grows or connects the
    supplied faces.  It is intended for direct single/multi-selection and for
    custom edits made after accepting an automatic logical region.
    """

    faces = {int(value) for value in face_indices if 0 <= int(value) < len(snapshot.triangles)}
    if not faces:
        raise ValueError("An explicit surface selection needs at least one valid face.")
    resolved_seed = int(seed_face) if seed_face is not None and int(seed_face) in faces else min(faces)
    return _result_from_faces(
        snapshot,
        resolved_seed,
        faces,
        0.0,
        automatic=False,
        explanation=explanation or f"{len(faces)} explicitly selected face(s).",
    )

def _retarget_region_result(
    snapshot: SurfaceMeshSnapshot,
    source: SurfaceRegionResult,
    seed_face: int,
    *,
    automatic: bool,
) -> SurfaceRegionResult:
    """Reuse one stable logical region while refreshing seed-relative metrics."""

    face_set = set(source.face_indices)
    metrics = _metrics(snapshot, int(seed_face), face_set, source.boundary_edges)
    return SurfaceRegionResult(
        source.object_id,
        int(seed_face),
        source.face_indices,
        source.boundary_edges,
        source.boundary_loops,
        source.tolerance,
        bool(automatic),
        _confidence(metrics, has_loop=bool(source.boundary_loops)),
        metrics,
        (),
        (
            f"Reused a cached logical region with {metrics.face_count} triangle(s); "
            f"max local bend {metrics.maximum_local_angle_degrees:.1f}°."
        ),
    )


def _select_surface_region_internal(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    tolerance: float,
    *,
    profile: SurfaceSelectionProfile,
    required_faces: Iterable[int] = (),
    excluded_faces: Iterable[int] = (),
) -> tuple[SurfaceRegionResult, dict[str, Any]]:
    started_total = time.perf_counter()
    required = {int(value) for value in required_faces}
    excluded = {int(value) for value in excluded_faces}
    excluded.discard(int(seed_face))

    started = time.perf_counter()
    faces, growth_stats = _region_faces(snapshot, int(seed_face), float(tolerance), profile, required, excluded)
    region_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    edges, loops = _boundary(snapshot, faces)
    boundary_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    metrics = _metrics(snapshot, int(seed_face), faces, edges)
    metrics_ms = (time.perf_counter() - started) * 1000.0

    coherence = max(0.0, 1.0 - metrics.mean_seed_angle_degrees / 110.0)
    confidence = max(0.0, min(1.0, 0.62 * coherence + 0.23 * min(1.0, metrics.compactness * 2.4) + 0.15 * (1.0 if loops else 0.0)))
    explanation = f"{metrics.face_count} triangle(s), max local bend {metrics.maximum_local_angle_degrees:.1f}°, max drift {metrics.maximum_seed_angle_degrees:.1f}°."
    result = SurfaceRegionResult(
        snapshot.object_id,
        int(seed_face),
        tuple(sorted(faces)),
        edges,
        loops,
        max(0.0, min(1.0, float(tolerance))),
        False,
        confidence,
        metrics,
        (),
        explanation,
    )
    timing = {
        "elapsed_ms": (time.perf_counter() - started_total) * 1000.0,
        "region_ms": region_ms,
        "boundary_ms": boundary_ms,
        "metrics_ms": metrics_ms,
        "selected_faces": metrics.face_count,
        "boundary_edges": len(edges),
        "boundary_loops": len(loops),
        **growth_stats,
    }
    return result, timing


def select_surface_region(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    tolerance: float,
    *,
    profile: SurfaceSelectionProfile | None = None,
    required_faces: Iterable[int] = (),
    excluded_faces: Iterable[int] = (),
    cache: SurfaceSelectionCache | None = None,
    diagnostics: SurfaceSelectionDiagnosticSink | None = None,
) -> SurfaceRegionResult:
    profile = profile or SurfaceSelectionProfile.cloth_support()
    required = tuple(sorted({int(value) for value in required_faces}))
    excluded = tuple(sorted({int(value) for value in excluded_faces if int(value) != int(seed_face)}))
    if cache is not None:
        cached = cache.get_manual(snapshot, seed_face, tolerance, profile, required, excluded)
        if cached is not None:
            _emit_diagnostic(
                diagnostics,
                "select.solve",
                elapsed_ms=0.0,
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                mesh_vertices=len(snapshot.vertices),
                mesh_faces=len(snapshot.triangles),
                seed_face=int(seed_face),
                tolerance=float(tolerance),
                profile=profile.id,
                selected_faces=cached.metrics.face_count,
                boundary_edges=len(cached.boundary_edges),
                cache_kind="exact",
                field_cache_hit=True,
            )
            return cached

        started_total = time.perf_counter()
        field_value, field_hit = _accessibility_field(snapshot, seed_face, profile, excluded, cache)
        started = time.perf_counter()
        faces = set(field_value.faces_at(tolerance))
        required_connections = 0
        required_search_pops = 0
        for required_face in required:
            if required_face in faces or required_face in excluded or not 0 <= required_face < len(snapshot.triangles):
                continue
            stats = _connect_required_face(snapshot, int(seed_face), required_face, faces, set(excluded), profile)
            required_connections += 1
            required_search_pops += int(stats.get("queue_pops", 0))
        region_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        result = _result_from_faces(snapshot, seed_face, faces, tolerance, automatic=False)
        finalize_ms = (time.perf_counter() - started) * 1000.0
        cache.put_manual(snapshot, seed_face, tolerance, profile, required, excluded, result)
        _emit_diagnostic(
            diagnostics,
            "select.solve",
            elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
            field_ms=0.0 if field_hit else field_value.elapsed_ms,
            field_cache_hit=field_hit,
            region_ms=region_ms,
            boundary_ms=finalize_ms,
            metrics_ms=0.0,
            object_id=snapshot.object_id,
            object_name=snapshot.name,
            mesh_vertices=len(snapshot.vertices),
            mesh_faces=len(snapshot.triangles),
            seed_face=int(seed_face),
            tolerance=float(tolerance),
            profile=profile.id,
            selected_faces=result.metrics.face_count,
            boundary_edges=len(result.boundary_edges),
            required_connections=required_connections,
            required_search_pops=required_search_pops,
            cache_kind="miss",
        )
        return result

    result, timing = _select_surface_region_internal(
        snapshot,
        seed_face,
        tolerance,
        profile=profile,
        required_faces=required,
        excluded_faces=excluded,
    )
    _emit_diagnostic(
        diagnostics,
        "select.solve",
        object_id=snapshot.object_id,
        object_name=snapshot.name,
        mesh_vertices=len(snapshot.vertices),
        mesh_faces=len(snapshot.triangles),
        seed_face=int(seed_face),
        tolerance=float(tolerance),
        profile=profile.id,
        **timing,
    )
    return result


def _incremental_metrics_for_counts(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    ordered_faces: Sequence[int],
    counts: Iterable[int],
) -> dict[int, SurfaceRegionMetrics]:
    """Compute exact scalar metrics for many nested regions in one pass."""

    requested = sorted({max(0, int(value)) for value in counts})
    if not requested:
        return {}
    maximum = min(len(ordered_faces), requested[-1])
    requested_set = set(requested)
    selected: set[int] = set()
    edge_selected_counts: dict[EdgeKey, int] = defaultdict(int)
    boundary_edges: set[EdgeKey] = set()
    area = 0.0
    boundary_length = 0.0
    seed_angle_sum = 0.0
    seed_angle_max = 0.0
    local_angle_max = 0.0
    results: dict[int, SurfaceRegionMetrics] = {}

    for offset, face_index in enumerate(ordered_faces[:maximum], start=1):
        selected.add(face_index)
        area += snapshot.areas[face_index]
        seed_angle = _angle_degrees(snapshot.normals[seed_face], snapshot.normals[face_index])
        seed_angle_sum += seed_angle
        seed_angle_max = max(seed_angle_max, seed_angle)
        triangle = snapshot.triangles[face_index]
        for edge_offset in range(3):
            edge = _edge_key(triangle[edge_offset], triangle[(edge_offset + 1) % 3])
            previous = edge_selected_counts[edge]
            edge_selected_counts[edge] = previous + 1
            length = math.dist(snapshot.vertices[edge[0]], snapshot.vertices[edge[1]])
            if previous == 0:
                boundary_edges.add(edge)
                boundary_length += length
            elif previous == 1:
                boundary_edges.discard(edge)
                boundary_length -= length
        for position, neighbor in enumerate(snapshot.neighbors[face_index]):
            if neighbor in selected:
                local_angle_max = max(local_angle_max, snapshot.neighbor_local_angles[face_index][position])

        if offset in requested_set:
            compactness = (
                0.0
                if boundary_length <= 1.0e-12
                else max(0.0, min(1.0, 4.0 * math.pi * area / (boundary_length * boundary_length)))
            )
            results[offset] = SurfaceRegionMetrics(
                offset,
                area,
                area / max(1.0e-12, snapshot.total_area),
                len(boundary_edges),
                max(0.0, boundary_length),
                compactness,
                seed_angle_sum / max(1, offset),
                seed_angle_max,
                local_angle_max,
            )
    return results


def _auto_candidate_score(
    metrics: SurfaceRegionMetrics,
    *,
    stability: float,
    total_faces: int,
    has_loop_hint: bool,
    grouped_count: int,
) -> float:
    size_ratio = metrics.face_count / max(1, total_faces)
    useful_size = min(1.0, metrics.face_count / 8.0)
    whole_mesh_penalty = 0.36 if size_ratio > 0.94 and grouped_count > 1 else 0.0
    tiny_penalty = 0.20 if metrics.face_count == 1 and total_faces > 4 else 0.0
    return (
        0.43 * min(1.0, stability / 0.25)
        + 0.28 * _confidence(metrics, has_loop=has_loop_hint)
        + 0.16 * useful_size
        + 0.13 * min(1.0, metrics.compactness * 2.2)
        - whole_mesh_penalty
        - tiny_penalty
    )


def _auto_surface_region_legacy(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    *,
    profile: SurfaceSelectionProfile | None = None,
    required_faces: Iterable[int] = (),
    excluded_faces: Iterable[int] = (),
    diagnostics: SurfaceSelectionDiagnosticSink | None = None,
) -> SurfaceRegionResult:
    started_total = time.perf_counter()
    profile = profile or SurfaceSelectionProfile.cloth_support()
    levels = tuple(index / 40.0 for index in range(1, 41))
    candidates: list[SurfaceRegionResult] = []
    level_timings: list[dict[str, Any]] = []
    started_candidates = time.perf_counter()
    for level in levels:
        candidate, timing = _select_surface_region_internal(
            snapshot,
            seed_face,
            level,
            profile=profile,
            required_faces=required_faces,
            excluded_faces=excluded_faces,
        )
        candidates.append(candidate)
        level_timings.append({
            "tolerance": level,
            "faces": candidate.metrics.face_count,
            "elapsed_ms": timing["elapsed_ms"],
            "region_ms": timing["region_ms"],
            "boundary_ms": timing["boundary_ms"],
            "metrics_ms": timing["metrics_ms"],
            "queue_pops": timing.get("queue_pops", 0),
            "crossing_evaluations": timing.get("crossing_evaluations", 0),
        })
    candidates_ms = (time.perf_counter() - started_candidates) * 1000.0

    started_grouping = time.perf_counter()
    grouped: list[tuple[SurfaceRegionResult, float, float]] = []
    start = 0
    while start < len(candidates):
        end = start
        while end + 1 < len(candidates) and candidates[end + 1].face_indices == candidates[start].face_indices:
            end += 1
        grouped.append((candidates[(start + end) // 2], levels[start], levels[end]))
        start = end + 1
    grouping_ms = (time.perf_counter() - started_grouping) * 1000.0

    started_scoring = time.perf_counter()
    total_faces = max(1, len(snapshot.triangles))
    scored: list[tuple[float, SurfaceRegionResult, float, float]] = []
    for candidate, low, high in grouped:
        stability = max(0.025, high - low + 0.025)
        size_ratio = candidate.metrics.face_count / total_faces
        useful_size = min(1.0, candidate.metrics.face_count / 8.0)
        whole_mesh_penalty = 0.36 if size_ratio > 0.94 and len(grouped) > 1 else 0.0
        tiny_penalty = 0.20 if candidate.metrics.face_count == 1 and total_faces > 4 else 0.0
        score = (
            0.43 * min(1.0, stability / 0.25)
            + 0.28 * candidate.confidence
            + 0.16 * useful_size
            + 0.13 * min(1.0, candidate.metrics.compactness * 2.2)
            - whole_mesh_penalty
            - tiny_penalty
        )
        scored.append((score, candidate, low, high))
    scored.sort(key=lambda item: (item[0], item[1].metrics.face_count), reverse=True)
    _score, best, low, high = scored[0]
    alternatives = tuple((candidate.tolerance, candidate.face_indices) for _value, candidate, _lo, _hi in scored[1:4])
    confidence = max(0.0, min(1.0, best.confidence * 0.72 + min(1.0, (high - low + 0.025) / 0.25) * 0.28))
    scoring_ms = (time.perf_counter() - started_scoring) * 1000.0
    explanation = (
        f"Auto selected a stable region from tolerance {low:.2f} to {high:.2f}. "
        f"{best.metrics.face_count} triangle(s), max local bend {best.metrics.maximum_local_angle_degrees:.1f}°."
    )
    result = SurfaceRegionResult(
        best.object_id,
        best.seed_face,
        best.face_indices,
        best.boundary_edges,
        best.boundary_loops,
        best.tolerance,
        True,
        confidence,
        best.metrics,
        alternatives,
        explanation,
    )
    _emit_diagnostic(
        diagnostics,
        "auto.solve",
        elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
        candidates_ms=candidates_ms,
        grouping_ms=grouping_ms,
        scoring_ms=scoring_ms,
        object_id=snapshot.object_id,
        object_name=snapshot.name,
        mesh_vertices=len(snapshot.vertices),
        mesh_faces=len(snapshot.triangles),
        seed_face=int(seed_face),
        profile=profile.id,
        level_count=len(levels),
        stable_groups=len(grouped),
        chosen_tolerance=result.tolerance,
        chosen_faces=result.metrics.face_count,
        alternatives=len(alternatives),
        levels=level_timings,
    )
    return result


def auto_surface_region(
    snapshot: SurfaceMeshSnapshot,
    seed_face: int,
    *,
    profile: SurfaceSelectionProfile | None = None,
    required_faces: Iterable[int] = (),
    excluded_faces: Iterable[int] = (),
    cache: SurfaceSelectionCache | None = None,
    diagnostics: SurfaceSelectionDiagnosticSink | None = None,
) -> SurfaceRegionResult:
    """Select a stable logical region using one incremental graph solve.

    Auto still exposes forty semantic continuity samples, but they are derived
    from a single minimax accessibility field.  Repeated hover seeds are served
    from the progressive cache whenever possible.
    """

    started_total = time.perf_counter()
    profile = profile or SurfaceSelectionProfile.cloth_support()
    required = tuple(sorted({int(value) for value in required_faces}))
    excluded = tuple(sorted({int(value) for value in excluded_faces if int(value) != int(seed_face)}))

    if cache is not None:
        cached, cache_kind = cache.get_auto(snapshot, seed_face, profile, required, excluded)
        if cached is not None:
            _emit_diagnostic(
                diagnostics,
                "auto.solve",
                elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
                candidates_ms=0.0,
                grouping_ms=0.0,
                scoring_ms=0.0,
                field_ms=0.0,
                sweep_ms=0.0,
                finalize_ms=0.0,
                field_cache_hit=True,
                cache_kind=cache_kind,
                incremental=True,
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                mesh_vertices=len(snapshot.vertices),
                mesh_faces=len(snapshot.triangles),
                seed_face=int(seed_face),
                profile=profile.id,
                level_count=40,
                stable_groups=1,
                chosen_tolerance=cached.tolerance,
                chosen_faces=cached.metrics.face_count,
                alternatives=len(cached.alternatives),
                levels=(),
            )
            return cached

    # Manual inclusion paths are uncommon and semantically non-monotonic.
    # Preserve the proven solver for that interaction while still caching the
    # final result.  Exclusions remain compatible with the incremental field.
    if required:
        result = _auto_surface_region_legacy(
            snapshot,
            seed_face,
            profile=profile,
            required_faces=required,
            excluded_faces=excluded,
            diagnostics=diagnostics,
        )
        if cache is not None:
            cache.put_auto(snapshot, seed_face, profile, required, excluded, result)
        return result

    levels = tuple(index / 40.0 for index in range(1, 41))
    started_field = time.perf_counter()
    field_value, field_hit = _accessibility_field(snapshot, seed_face, profile, excluded, cache)
    field_phase_ms = (time.perf_counter() - started_field) * 1000.0

    started_sweep = time.perf_counter()
    level_counts = tuple(bisect_right(field_value.sorted_costs, _threshold(level)) for level in levels)
    grouped: list[tuple[int, float, float, float]] = []
    start = 0
    while start < len(levels):
        end = start
        while end + 1 < len(levels) and level_counts[end + 1] == level_counts[start]:
            end += 1
        grouped.append((level_counts[start], levels[start], levels[end], levels[(start + end) // 2]))
        start = end + 1

    metric_by_count = _incremental_metrics_for_counts(
        snapshot,
        int(seed_face),
        field_value.sorted_faces,
        (count for count, _low, _high, _mid in grouped),
    )
    total_faces = max(1, len(snapshot.triangles))
    approximate: list[tuple[float, int, float, float, float, SurfaceRegionMetrics]] = []
    for count, low, high, midpoint in grouped:
        metrics = metric_by_count.get(count)
        if metrics is None:
            continue
        stability = max(0.025, high - low + 0.025)
        score = _auto_candidate_score(
            metrics,
            stability=stability,
            total_faces=total_faces,
            has_loop_hint=metrics.boundary_edge_count > 0,
            grouped_count=len(grouped),
        )
        approximate.append((score, count, low, high, midpoint, metrics))
    approximate.sort(key=lambda item: (item[0], item[1]), reverse=True)
    sweep_ms = (time.perf_counter() - started_sweep) * 1000.0

    started_finalize = time.perf_counter()
    # Exact loop construction is intentionally limited to the candidates that
    # can become the winner or one of the three visible alternatives.
    exact_candidates: list[tuple[float, SurfaceRegionResult, float, float]] = []
    for _approx_score, count, low, high, midpoint, _metrics_value in approximate[:6]:
        faces = field_value.sorted_faces[:count]
        candidate = _result_from_faces(snapshot, seed_face, faces, midpoint, automatic=False)
        stability = max(0.025, high - low + 0.025)
        exact_score = _auto_candidate_score(
            candidate.metrics,
            stability=stability,
            total_faces=total_faces,
            has_loop_hint=bool(candidate.boundary_loops),
            grouped_count=len(grouped),
        )
        exact_candidates.append((exact_score, candidate, low, high))
    if not exact_candidates:
        fallback_faces = field_value.faces_at(0.025) or (int(seed_face),)
        fallback = _result_from_faces(snapshot, seed_face, fallback_faces, 0.025, automatic=False)
        exact_candidates.append((0.0, fallback, 0.025, 0.025))
    exact_candidates.sort(key=lambda item: (item[0], item[1].metrics.face_count), reverse=True)
    _score, best, low, high = exact_candidates[0]
    alternatives = tuple((candidate.tolerance, candidate.face_indices) for _value, candidate, _lo, _hi in exact_candidates[1:4])
    confidence = max(
        0.0,
        min(1.0, best.confidence * 0.72 + min(1.0, (high - low + 0.025) / 0.25) * 0.28),
    )
    explanation = (
        f"Auto selected a stable region from tolerance {low:.2f} to {high:.2f}. "
        f"{best.metrics.face_count} triangle(s), max local bend {best.metrics.maximum_local_angle_degrees:.1f}°."
    )
    result = SurfaceRegionResult(
        best.object_id,
        int(seed_face),
        best.face_indices,
        best.boundary_edges,
        best.boundary_loops,
        best.tolerance,
        True,
        confidence,
        best.metrics,
        alternatives,
        explanation,
    )
    finalize_ms = (time.perf_counter() - started_finalize) * 1000.0

    if cache is not None:
        cache.put_auto(snapshot, seed_face, profile, required, excluded, result)

    level_timings = tuple(
        {
            "tolerance": level,
            "faces": count,
            "elapsed_ms": 0.0,
            "region_ms": 0.0,
            "boundary_ms": 0.0,
            "metrics_ms": 0.0,
            "queue_pops": 0,
            "crossing_evaluations": 0,
        }
        for level, count in zip(levels, level_counts)
    )
    _emit_diagnostic(
        diagnostics,
        "auto.solve",
        elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
        candidates_ms=field_phase_ms + sweep_ms,
        grouping_ms=0.0,
        scoring_ms=finalize_ms,
        field_ms=field_phase_ms,
        raw_field_build_ms=0.0 if field_hit else field_value.elapsed_ms,
        sweep_ms=sweep_ms,
        finalize_ms=finalize_ms,
        field_cache_hit=field_hit,
        cache_kind="miss",
        incremental=True,
        object_id=snapshot.object_id,
        object_name=snapshot.name,
        mesh_vertices=len(snapshot.vertices),
        mesh_faces=len(snapshot.triangles),
        seed_face=int(seed_face),
        profile=profile.id,
        level_count=len(levels),
        stable_groups=len(grouped),
        chosen_tolerance=result.tolerance,
        chosen_faces=result.metrics.face_count,
        alternatives=len(alternatives),
        field_queue_pops=field_value.queue_pops,
        field_crossing_evaluations=field_value.crossing_evaluations,
        levels=level_timings,
    )
    return result


__all__ = [
    "EdgeKey",
    "Point3",
    "SurfaceMeshSnapshot",
    "SurfaceAccessibilityField",
    "SurfaceRegionMetrics",
    "SurfaceRegionResult",
    "SurfaceSelectionCache",
    "SurfaceSelectionDiagnosticSink",
    "SurfaceSelectionPointerAction",
    "SurfaceSelectionPointerMachine",
    "SurfaceSelectionPointerState",
    "SurfaceSelectionMeshPolicy",
    "SurfaceSelectionProfile",
    "SurfaceSelectionSession",
    "Triangle",
    "auto_surface_region",
    "select_surface_region",
    "surface_region_from_faces",
]
