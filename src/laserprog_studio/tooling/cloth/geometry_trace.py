"""Intelligent tracing of existing mesh faces and edges into Cloth geometry.

The controller is deliberately headless: it owns source-mesh snapshots,
selection toggles, topology predictions and document materialisation. The
Creator adapter only routes picks and overlay actions.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Literal, Sequence

from laserprog_studio.tool_api import surface_selection as smart_surface

from .drawing import ClothDrawingController, ClothDrawingOutcome
from .models import ClothDocument, Point3

EdgeKey = tuple[int, int]
PickKind = Literal["face", "edge"]


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
    return math.sqrt(_dot(value, value))


def _normalized(value: Point3) -> Point3 | None:
    length = _length(value)
    if length <= 1.0e-12:
        return None
    return (value[0] / length, value[1] / length, value[2] / length)


def _triangle_normal(vertices: Sequence[Point3], triangle: Sequence[int]) -> Point3 | None:
    try:
        a, b, c = (vertices[int(index)] for index in triangle[:3])
    except Exception:
        return None
    return _normalized(_cross(_sub(b, a), _sub(c, a)))


def _point_segment_distance(point: Point3, start: Point3, end: Point3) -> float:
    axis = _sub(end, start)
    denom = _dot(axis, axis)
    if denom <= 1.0e-20:
        return math.dist(point, start)
    t = max(0.0, min(1.0, _dot(_sub(point, start), axis) / denom))
    projected = (start[0] + axis[0] * t, start[1] + axis[1] * t, start[2] + axis[2] * t)
    return math.dist(point, projected)


def _snapshot_scale(snapshot: "SourceMeshSnapshot") -> float:
    xs = [value[0] for value in snapshot.vertices]
    ys = [value[1] for value in snapshot.vertices]
    zs = [value[2] for value in snapshot.vertices]
    return max(
        max(xs) - min(xs),
        max(ys) - min(ys),
        max(zs) - min(zs),
        1.0,
    )


def _triangle_matches_displayed_cell(
    snapshot: "SourceMeshSnapshot",
    face_index: int,
    displayed_vertices: Sequence[Point3],
) -> bool:
    triangle = snapshot.triangles[int(face_index)]
    source = tuple(snapshot.vertices[index] for index in triangle)
    tolerance = _snapshot_scale(snapshot) * 1.0e-6 + 1.0e-7
    # A displayed polygon can contain more than three points. Every source
    # triangle vertex must nevertheless be represented by that picked cell.
    return all(min(math.dist(vertex, displayed) for displayed in displayed_vertices) <= tolerance for vertex in source)


def _triangle_centroid(snapshot: "SourceMeshSnapshot", face_index: int) -> Point3:
    triangle = snapshot.triangles[int(face_index)]
    values = tuple(snapshot.vertices[index] for index in triangle)
    return (
        sum(value[0] for value in values) / 3.0,
        sum(value[1] for value in values) / 3.0,
        sum(value[2] for value in values) / 3.0,
    )


def _nearest_source_triangle(
    snapshot: "SourceMeshSnapshot",
    *,
    displayed_vertices: Sequence[Point3] = (),
    world_pos: Point3 | None = None,
    normal: Point3 | None = None,
) -> int | None:
    if not snapshot.triangles:
        return None
    normalized_normal = _normalized(normal) if normal is not None else None
    scale = _snapshot_scale(snapshot)

    def score(face_index: int) -> float:
        triangle = snapshot.triangles[face_index]
        source_vertices = tuple(snapshot.vertices[index] for index in triangle)
        value = 0.0
        if displayed_vertices:
            # Symmetric nearest-vertex score makes actor cell renumbering and
            # cleaned/LOD geometry deterministic without requiring VTK ids.
            value += sum(min(math.dist(source, displayed) for displayed in displayed_vertices) for source in source_vertices)
            value += 0.35 * sum(min(math.dist(displayed, source) for source in source_vertices) for displayed in displayed_vertices)
        if world_pos is not None:
            value += 0.5 * math.dist(_triangle_centroid(snapshot, face_index), world_pos)
        if normalized_normal is not None:
            candidate_normal = _triangle_normal(snapshot.vertices, triangle)
            if candidate_normal is not None:
                value += scale * 0.15 * (1.0 - abs(_dot(candidate_normal, normalized_normal)))
        return value

    return min(range(len(snapshot.triangles)), key=score)


@dataclass(frozen=True, slots=True)
class SourceMeshSnapshot:
    object_id: str
    object_index: int | None
    name: str
    vertices: tuple[Point3, ...]
    triangles: tuple[tuple[int, int, int], ...]

    @classmethod
    def from_object(cls, obj: Any, *, object_id: str, object_index: int | None = None) -> "SourceMeshSnapshot" | None:
        mesh = getattr(obj, "mesh", None)
        try:
            vertices = tuple(_point3(value) for value in mesh.vertices)
            triangles = tuple(tuple(int(index) for index in triangle[:3]) for triangle in mesh.triangles)
        except Exception:
            return None
        if len(vertices) < 2 or not triangles:
            return None
        return cls(
            str(object_id),
            None if object_index is None else int(object_index),
            str(getattr(obj, "name", "") or getattr(mesh, "name", "") or "Mesh"),
            vertices,
            triangles,
        )

    @property
    def edges(self) -> tuple[EdgeKey, ...]:
        values = {
            _edge_key(int(triangle[index]), int(triangle[(index + 1) % 3]))
            for triangle in self.triangles
            for index in range(3)
        }
        return tuple(sorted(values))

    def edge_vertices(self, edge: EdgeKey) -> tuple[Point3, Point3]:
        return (self.vertices[edge[0]], self.vertices[edge[1]])


@dataclass(frozen=True, slots=True)
class SourceFaceSelection:
    object_id: str
    face_index: int


@dataclass(frozen=True, slots=True)
class SourceEdgeSelection:
    object_id: str
    edge: EdgeKey


@dataclass(frozen=True, slots=True)
class SourceSurfaceRegion:
    """One source-mesh surface region after removing coplanar triangulation diagonals."""

    object_id: str
    face_indices: tuple[int, ...]
    boundary_edges: tuple[EdgeKey, ...]
    boundary_loops: tuple[tuple[int, ...], ...]

    @property
    def outer_loop(self) -> tuple[int, ...]:
        return self.boundary_loops[0] if self.boundary_loops else ()


@dataclass(frozen=True, slots=True)
class SourceFaceClosurePlan:
    """A source face whose boundary is complete or almost complete."""

    object_id: str
    face_indices: tuple[int, ...]
    boundary_edges: tuple[EdgeKey, ...]
    selected_edges: tuple[EdgeKey, ...]
    missing_edges: tuple[EdgeKey, ...]
    coverage: float

    @property
    def complete(self) -> bool:
        return not self.missing_edges


@dataclass(frozen=True, slots=True)
class GeometryTracePredictions:
    coplanar_faces: tuple[SourceFaceSelection, ...] = ()
    boundary_edges: tuple[SourceEdgeSelection, ...] = ()
    connected_edges: tuple[SourceEdgeSelection, ...] = ()
    directional_edges: tuple[SourceEdgeSelection, ...] = ()
    closure_edges: tuple[SourceEdgeSelection, ...] = ()
    closable_faces: tuple[SourceFaceClosurePlan, ...] = ()
    ruled_strip: "RuledStripPlan | None" = None

    @property
    def has_any(self) -> bool:
        return bool(
            self.coplanar_faces
            or self.boundary_edges
            or self.connected_edges
            or self.directional_edges
            or self.closure_edges
            or self.ruled_strip is not None
        )


@dataclass(frozen=True, slots=True)
class RuledStripPlan:
    """Two ordered source-edge rails paired into one regular Cloth strip."""

    rail_a: tuple[Point3, ...]
    rail_b: tuple[Point3, ...]
    source_components: tuple[tuple[SourceEdgeSelection, ...], tuple[SourceEdgeSelection, ...]]
    mean_width_mm: float
    minimum_width_mm: float
    maximum_width_mm: float

    @property
    def segment_count(self) -> int:
        return max(0, min(len(self.rail_a), len(self.rail_b)) - 1)

    @property
    def ribs(self) -> tuple[tuple[Point3, Point3], ...]:
        return tuple(zip(self.rail_a, self.rail_b))


@dataclass(frozen=True, slots=True)
class GeometryTraceOutcome:
    committed: bool
    created_patch_ids: tuple[str, ...] = ()
    created_curve_ids: tuple[str, ...] = ()
    message: str = ""
    created_patch_groups: tuple[tuple[str, ...], ...] = ()


def _selected_edge_components(
    snapshots: dict[str, SourceMeshSnapshot],
    selected_edges: Sequence[SourceEdgeSelection],
) -> tuple[tuple[SourceEdgeSelection, ...], ...]:
    """Split selected source edges into connected components per source mesh."""

    grouped: dict[str, set[EdgeKey]] = defaultdict(set)
    for item in selected_edges:
        if item.object_id in snapshots:
            grouped[item.object_id].add(item.edge)
    components: list[tuple[SourceEdgeSelection, ...]] = []
    for object_id, remaining_edges in grouped.items():
        vertex_edges: dict[int, set[EdgeKey]] = defaultdict(set)
        for edge in remaining_edges:
            vertex_edges[edge[0]].add(edge)
            vertex_edges[edge[1]].add(edge)
        remaining = set(remaining_edges)
        while remaining:
            seed = remaining.pop()
            component = {seed}
            queue = [seed]
            while queue:
                current = queue.pop()
                for vertex in current:
                    for neighbor in vertex_edges.get(vertex, ()):
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            component.add(neighbor)
                            queue.append(neighbor)
            components.append(
                tuple(SourceEdgeSelection(object_id, edge) for edge in sorted(component))
            )
    return tuple(components)


def _ordered_open_chain_vertices(
    snapshot: SourceMeshSnapshot,
    component: Sequence[SourceEdgeSelection],
) -> tuple[int, ...] | None:
    """Order one non-branching open edge component from endpoint to endpoint."""

    edges = {item.edge for item in component if item.object_id == snapshot.object_id}
    if not edges:
        return None
    adjacency: dict[int, list[int]] = defaultdict(list)
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    if any(len(neighbors) > 2 for neighbors in adjacency.values()):
        return None
    endpoints = sorted(vertex for vertex, neighbors in adjacency.items() if len(neighbors) == 1)
    if len(endpoints) != 2:
        return None
    start = endpoints[0]
    ordered = [start]
    previous: int | None = None
    current = start
    used: set[EdgeKey] = set()
    while True:
        candidates = [
            neighbor
            for neighbor in adjacency[current]
            if _edge_key(current, neighbor) not in used and neighbor != previous
        ]
        if not candidates:
            break
        # A valid non-branching chain has one candidate. Sorting keeps the
        # result deterministic for coincident/duplicate source data.
        next_vertex = min(candidates)
        used.add(_edge_key(current, next_vertex))
        ordered.append(next_vertex)
        previous, current = current, next_vertex
        if len(ordered) > len(edges) + 1:
            return None
    if len(used) != len(edges) or current != endpoints[1]:
        return None
    return tuple(ordered)


def _polyline_parameters(points: Sequence[Point3]) -> tuple[float, ...] | None:
    if len(points) < 2:
        return None
    lengths = [0.0]
    for index in range(1, len(points)):
        lengths.append(lengths[-1] + math.dist(points[index - 1], points[index]))
    total = lengths[-1]
    if total <= 1.0e-9:
        return None
    return tuple(value / total for value in lengths)


def _resample_polyline(
    points: Sequence[Point3],
    source_parameters: Sequence[float],
    target_parameters: Sequence[float],
) -> tuple[Point3, ...]:
    values: list[Point3] = []
    segment = 0
    for target in target_parameters:
        t = max(0.0, min(1.0, float(target)))
        while segment + 1 < len(source_parameters) - 1 and source_parameters[segment + 1] < t - 1.0e-12:
            segment += 1
        low_t = source_parameters[segment]
        high_t = source_parameters[segment + 1]
        if high_t - low_t <= 1.0e-15:
            values.append(points[segment])
            continue
        alpha = max(0.0, min(1.0, (t - low_t) / (high_t - low_t)))
        start, end = points[segment], points[segment + 1]
        values.append(
            (
                start[0] + (end[0] - start[0]) * alpha,
                start[1] + (end[1] - start[1]) * alpha,
                start[2] + (end[2] - start[2]) * alpha,
            )
        )
    return tuple(values)


def _deduplicate_parameters(values: Iterable[float], *, maximum_count: int = 513) -> tuple[float, ...]:
    ordered = sorted(max(0.0, min(1.0, float(value))) for value in values)
    unique: list[float] = []
    for value in ordered:
        if not unique or value - unique[-1] > 1.0e-9:
            unique.append(value)
    if not unique or unique[0] > 0.0:
        unique.insert(0, 0.0)
    if unique[-1] < 1.0:
        unique.append(1.0)
    if len(unique) <= maximum_count:
        return tuple(unique)
    # Preserve both endpoints and sample the combined knot vector uniformly.
    return tuple(unique[round(index * (len(unique) - 1) / (maximum_count - 1))] for index in range(maximum_count))


def plan_ruled_strip_from_selection(
    snapshots: dict[str, SourceMeshSnapshot],
    selected_edges: Sequence[SourceEdgeSelection],
) -> RuledStripPlan | None:
    """Detect exactly two open edge rails and pair them without twisting.

    This is the intended operation for covering two parallel Plan Tracer arcs:
    both rails are parameterised by normalised arc length, their original mesh
    knots are merged, and the second rail is reversed when that minimises the
    endpoint and interior bridge distances.
    """

    components = _selected_edge_components(snapshots, selected_edges)
    if len(components) != 2:
        return None
    world_chains: list[tuple[Point3, ...]] = []
    for component in components:
        snapshot = snapshots.get(component[0].object_id) if component else None
        if snapshot is None:
            return None
        ordered_vertices = _ordered_open_chain_vertices(snapshot, component)
        if ordered_vertices is None:
            return None
        chain = tuple(snapshot.vertices[index] for index in ordered_vertices)
        if len(chain) < 2:
            return None
        world_chains.append(chain)

    first, second = world_chains
    first_parameters = _polyline_parameters(first)
    second_parameters = _polyline_parameters(second)
    if first_parameters is None or second_parameters is None:
        return None
    parameters = _deduplicate_parameters((*first_parameters, *second_parameters))
    rail_a = _resample_polyline(first, first_parameters, parameters)
    forward = _resample_polyline(second, second_parameters, parameters)
    reversed_points = tuple(reversed(second))
    reversed_parameters = _polyline_parameters(reversed_points)
    if reversed_parameters is None:
        return None
    reverse = _resample_polyline(reversed_points, reversed_parameters, parameters)

    def pairing_score(candidate: Sequence[Point3]) -> float:
        distances = [math.dist(a, b) for a, b in zip(rail_a, candidate)]
        if not distances:
            return float("inf")
        endpoint_weight = distances[0] + distances[-1]
        smoothness = sum(abs(distances[index] - distances[index - 1]) for index in range(1, len(distances)))
        tangent_penalty = 0.0
        for index in range(1, len(rail_a)):
            first_tangent = _normalized(_sub(rail_a[index], rail_a[index - 1]))
            second_tangent = _normalized(_sub(candidate[index], candidate[index - 1]))
            if first_tangent is not None and second_tangent is not None:
                tangent_penalty += 1.0 - max(-1.0, min(1.0, _dot(first_tangent, second_tangent)))
        return (
            sum(distances) / len(distances)
            + endpoint_weight * 0.5
            + smoothness * 0.15
            + tangent_penalty * max(1.0, sum(distances) / len(distances)) * 0.25
        )

    rail_b = reverse if pairing_score(reverse) + 1.0e-9 < pairing_score(forward) else forward
    widths = tuple(math.dist(a, b) for a, b in zip(rail_a, rail_b))
    if not widths or min(widths) <= 1.0e-7:
        return None

    # Reject a clearly incoherent pairing, while allowing tapered strips. The
    # user explicitly selected both rails, so this guard only filters extreme
    # accidental selections rather than enforcing a strict 'parallel' test.
    mean_width = sum(widths) / len(widths)
    if max(widths) > mean_width * 20.0:
        return None
    # Reject a bow-tie pairing. Mildly non-planar cells are valid and will be
    # split locally by the drawing controller, but opposite triangle normals
    # indicate that the two rails have been matched across each other.
    for index in range(len(rail_a) - 1):
        first_normal = _normalized(
            _cross(_sub(rail_a[index + 1], rail_a[index]), _sub(rail_b[index + 1], rail_a[index]))
        )
        second_normal = _normalized(
            _cross(_sub(rail_b[index + 1], rail_a[index]), _sub(rail_b[index], rail_a[index]))
        )
        if first_normal is not None and second_normal is not None and _dot(first_normal, second_normal) < -0.15:
            return None
    return RuledStripPlan(
        rail_a,
        rail_b,
        (tuple(components[0]), tuple(components[1])),
        mean_width,
        min(widths),
        max(widths),
    )



def _snapshot_diagonal(snapshot: SourceMeshSnapshot) -> float:
    if not snapshot.vertices:
        return 1.0
    xs = [value[0] for value in snapshot.vertices]
    ys = [value[1] for value in snapshot.vertices]
    zs = [value[2] for value in snapshot.vertices]
    return max(math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))), 1.0)


def _coplanar_shared_edge(
    snapshot: SourceMeshSnapshot,
    edge: EdgeKey,
    incidence: dict[EdgeKey, tuple[int, ...]],
    *,
    angle_tolerance_degrees: float = 4.0,
) -> bool:
    faces = incidence.get(edge, ())
    if len(faces) != 2:
        return False
    first_triangle = snapshot.triangles[faces[0]]
    second_triangle = snapshot.triangles[faces[1]]
    first_normal = _triangle_normal(snapshot.vertices, first_triangle)
    second_normal = _triangle_normal(snapshot.vertices, second_triangle)
    if first_normal is None or second_normal is None:
        return False
    if abs(_dot(first_normal, second_normal)) < math.cos(math.radians(max(0.0, float(angle_tolerance_degrees)))):
        return False
    origin = snapshot.vertices[first_triangle[0]]
    plane_tolerance = max(1.0e-7, _snapshot_diagonal(snapshot) * 1.0e-6)
    return max(
        abs(_dot(_sub(snapshot.vertices[index], origin), first_normal))
        for index in second_triangle
    ) <= plane_tolerance


def structural_mesh_edges(
    snapshot: SourceMeshSnapshot,
    *,
    incidence: dict[EdgeKey, tuple[int, ...]] | None = None,
) -> frozenset[EdgeKey]:
    """Return semantic surface edges, excluding coplanar tessellation diagonals."""

    incidence = incidence or edge_face_incidence(snapshot)
    return frozenset(
        edge
        for edge in snapshot.edges
        if len(incidence.get(edge, ())) != 2 or not _coplanar_shared_edge(snapshot, edge, incidence)
    )


def _orient_loop_to_source(
    snapshot: SourceMeshSnapshot,
    loop: Sequence[int],
    face_indices: Sequence[int],
) -> tuple[int, ...]:
    values = tuple(int(value) for value in loop)
    if len(values) < 3:
        return values
    nx = ny = nz = 0.0
    for index, vertex_index in enumerate(values):
        current = snapshot.vertices[vertex_index]
        following = snapshot.vertices[values[(index + 1) % len(values)]]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    loop_normal = _normalized((nx, ny, nz))
    source_normal = _normalized(
        tuple(
            sum(((_triangle_normal(snapshot.vertices, snapshot.triangles[face_index]) or (0.0, 0.0, 0.0))[axis]) for face_index in face_indices)
            for axis in range(3)
        )
    )
    if loop_normal is not None and source_normal is not None and _dot(loop_normal, source_normal) < 0.0:
        return tuple(reversed(values))
    return values


def source_surface_regions(snapshot: SourceMeshSnapshot) -> tuple[SourceSurfaceRegion, ...]:
    """Merge source triangles across coplanar internal diagonals into real faces."""

    incidence = edge_face_incidence(snapshot)
    triangle_neighbors: dict[int, set[int]] = defaultdict(set)
    for edge, faces in incidence.items():
        if len(faces) == 2 and _coplanar_shared_edge(snapshot, edge, incidence):
            first, second = faces
            triangle_neighbors[first].add(second)
            triangle_neighbors[second].add(first)
    remaining = set(range(len(snapshot.triangles)))
    regions: list[SourceSurfaceRegion] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        component = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            for neighbor in triangle_neighbors.get(current, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        boundary = boundary_edges(snapshot, component)
        if not boundary or len(boundary) > _MAX_FACE_BOUNDARY_EDGES:
            continue
        loops = ordered_boundary_loops(boundary)
        if not loops:
            continue
        loops = tuple(
            _orient_loop_to_source(snapshot, loop, tuple(sorted(component)))
            for loop in sorted(loops, key=lambda value: loop_perimeter(snapshot, value), reverse=True)
        )
        regions.append(
            SourceSurfaceRegion(
                snapshot.object_id,
                tuple(sorted(component)),
                tuple(boundary),
                loops,
            )
        )
    return tuple(regions)


def source_surface_regions_near_edges(
    snapshot: SourceMeshSnapshot,
    seed_edges: Iterable[EdgeKey],
    *,
    incidence: dict[EdgeKey, tuple[int, ...]] | None = None,
    maximum_regions: int = _MAX_TRACE_REGIONS if "_MAX_TRACE_REGIONS" in globals() else 2000,
) -> tuple[SourceSurfaceRegion, ...]:
    """Discover only semantic source faces touching the selected edges.

    This avoids analysing every surface region of a very dense source mesh just
    because the user selected a few local edges. The edge incidence table is
    still linear to build once and is cached by the controller.
    """

    incidence_map = incidence or edge_face_incidence(snapshot)
    seeds = {
        face_index
        for edge in seed_edges
        for face_index in incidence_map.get(_edge_key(*edge), ())
    }
    if not seeds:
        return ()
    visited: set[int] = set()
    regions: list[SourceSurfaceRegion] = []
    for seed in sorted(seeds):
        if seed in visited:
            continue
        component = {seed}
        visited.add(seed)
        queue = [seed]
        while queue:
            current = queue.pop()
            triangle = snapshot.triangles[current]
            for index in range(3):
                edge = _edge_key(triangle[index], triangle[(index + 1) % 3])
                faces = incidence_map.get(edge, ())
                if len(faces) != 2 or not _coplanar_shared_edge(snapshot, edge, incidence_map):
                    continue
                neighbor = faces[1] if faces[0] == current else faces[0]
                if neighbor not in visited:
                    visited.add(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        boundary = boundary_edges(snapshot, component)
        if not boundary or len(boundary) > _MAX_FACE_BOUNDARY_EDGES:
            continue
        loops = ordered_boundary_loops(boundary)
        if not loops:
            continue
        loops = tuple(
            _orient_loop_to_source(snapshot, loop, tuple(sorted(component)))
            for loop in sorted(loops, key=lambda value: loop_perimeter(snapshot, value), reverse=True)
        )
        regions.append(
            SourceSurfaceRegion(snapshot.object_id, tuple(sorted(component)), tuple(boundary), loops)
        )
        if len(regions) >= max(1, int(maximum_regions)):
            break
    return tuple(regions)


def _edge_set_is_connected(edges: set[EdgeKey]) -> bool:
    if not edges:
        return False
    vertex_edges: dict[int, set[EdgeKey]] = defaultdict(set)
    for edge in edges:
        vertex_edges[edge[0]].add(edge)
        vertex_edges[edge[1]].add(edge)
    remaining = set(edges)
    seed = remaining.pop()
    queue = [seed]
    while queue:
        current = queue.pop()
        for vertex in current:
            for neighbor in vertex_edges.get(vertex, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
    return not remaining


def source_face_closure_plans(
    snapshot: SourceMeshSnapshot,
    selected_edges: set[EdgeKey],
    regions: Sequence[SourceSurfaceRegion] | None = None,
    *,
    semantic_edges: Iterable[EdgeKey] | None = None,
) -> tuple[SourceFaceClosurePlan, ...]:
    """Find complete and near-complete semantic source faces.

    Near completion is intentionally conservative: the selected boundary must be
    connected and only a small number/length of source edges may be missing.
    """

    semantic = set(semantic_edges) if semantic_edges is not None else set(structural_mesh_edges(snapshot))
    selected = set(selected_edges) & semantic
    if not selected:
        return ()
    plans: list[SourceFaceClosurePlan] = []
    for region in regions or source_surface_regions(snapshot):
        boundary = set(region.boundary_edges)
        if not boundary:
            continue
        matched = boundary & selected
        if len(matched) < 2 or not _edge_set_is_connected(matched):
            continue
        missing = boundary - selected
        coverage = len(matched) / len(boundary)
        perimeter = sum(math.dist(*snapshot.edge_vertices(edge)) for edge in boundary)
        missing_length = sum(math.dist(*snapshot.edge_vertices(edge)) for edge in missing)
        allowed_missing_count = 2 if len(boundary) <= 6 else max(2, int(math.ceil(len(boundary) * 0.12)))
        close_enough = (
            not missing
            or (
                len(missing) <= allowed_missing_count
                and coverage >= (0.5 if len(boundary) <= 6 else 0.65)
                and missing_length <= max(1.0e-9, perimeter * 0.35)
            )
        )
        if not close_enough:
            continue
        plans.append(
            SourceFaceClosurePlan(
                snapshot.object_id,
                region.face_indices,
                tuple(region.boundary_edges),
                tuple(sorted(matched)),
                tuple(sorted(missing)),
                coverage,
            )
        )
    plans.sort(key=lambda item: (bool(item.missing_edges), len(item.missing_edges), -item.coverage, len(item.boundary_edges), item.face_indices))
    return tuple(plans)


def _ordered_closed_component_vertices(
    snapshot: SourceMeshSnapshot,
    component: Sequence[SourceEdgeSelection],
) -> tuple[int, ...] | None:
    edges = {item.edge for item in component if item.object_id == snapshot.object_id}
    if len(edges) < 3:
        return None
    adjacency: dict[int, set[int]] = defaultdict(set)
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        return None
    start = min(adjacency)
    loop = [start]
    previous: int | None = None
    current = start
    used: set[EdgeKey] = set()
    for _ in range(len(edges) + 1):
        choices = sorted(
            neighbor
            for neighbor in adjacency[current]
            if _edge_key(current, neighbor) not in used and neighbor != previous
        )
        if not choices:
            break
        following = choices[0]
        used.add(_edge_key(current, following))
        if following == start:
            return tuple(loop) if len(used) == len(edges) else None
        loop.append(following)
        previous, current = current, following
    return None


def _validation_error_keys(document: ClothDocument) -> set[tuple[str, tuple[str, ...]]]:
    from .validation import validate_cloth_document

    return {(issue.code, tuple(issue.entity_ids)) for issue in validate_cloth_document(document).errors}


def _prune_new_fold_cycles(document: ClothDocument, existing_fold_ids: set[str]) -> int:
    """Keep new source-trace folds as a spanning forest and mark the rest as cuts."""

    parent: dict[str, str] = {patch_id: patch_id for patch_id in document.patches}

    def find(value: str) -> str:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            following = parent[value]
            parent[value] = root
            value = following
        return root

    def union(first: str, second: str) -> bool:
        a, b = find(first), find(second)
        if a == b:
            return False
        parent[a] = b
        return True

    for fold_id in sorted(existing_fold_ids):
        fold = document.folds.get(fold_id)
        if fold is not None and fold.patch_a_id in parent and fold.patch_b_id in parent:
            union(fold.patch_a_id, fold.patch_b_id)
    removed = 0
    for fold_id in sorted(set(document.folds) - existing_fold_ids):
        fold = document.folds.get(fold_id)
        if fold is None:
            continue
        if union(fold.patch_a_id, fold.patch_b_id):
            continue
        document.folds.pop(fold_id, None)
        curve = document.curves.get(fold.curve_id)
        if curve is not None:
            curve.metadata["cloth_auto_cut"] = True
            if not any(existing.curve_id == curve.id for existing in document.folds.values()):
                from .models import ClothCurveRole

                curve.role = ClothCurveRole.BOUNDARY
        removed += 1
    if removed:
        document.revision += 1
    return removed


def _faces_are_coplanar(snapshot: SourceMeshSnapshot, face_indices: Sequence[int]) -> bool:
    """Return whether a source component can be copied as one exact polygon."""

    values = tuple(int(value) for value in face_indices)
    if not values:
        return False
    first = snapshot.triangles[values[0]]
    normal = _triangle_normal(snapshot.vertices, first)
    if normal is None:
        return False
    origin = snapshot.vertices[first[0]]
    scale = _snapshot_scale(snapshot)
    distance_tolerance = max(1.0e-7, scale * 2.0e-6)
    normal_tolerance = math.cos(math.radians(0.05))
    vertices: set[int] = set()
    for face_index in values:
        triangle = snapshot.triangles[face_index]
        candidate = _triangle_normal(snapshot.vertices, triangle)
        if candidate is None or abs(_dot(normal, candidate)) < normal_tolerance:
            return False
        vertices.update(int(value) for value in triangle)
    return all(abs(_dot(_sub(snapshot.vertices[index], origin), normal)) <= distance_tolerance for index in vertices)


_MAX_TRACE_SELECTED_EDGES = 5000
_MAX_TRACE_SELECTED_FACES = 5000
_MAX_TRACE_REGIONS = 2000
_MAX_FACE_BOUNDARY_EDGES = 4096


@dataclass(slots=True)
class ClothGeometryTraceController:
    pick_kind: PickKind = "face"
    snapshots: dict[str, SourceMeshSnapshot] = field(default_factory=dict)
    smart_snapshots: dict[str, smart_surface.SurfaceMeshSnapshot] = field(default_factory=dict)
    smart_session: smart_surface.SurfaceSelectionSession = field(
        default_factory=lambda: smart_surface.SurfaceSelectionSession(
            tolerance=0.35,
            automatic=True,
            mesh_policy=smart_surface.SurfaceSelectionMeshPolicy.MULTIPLE_MESHES,
        )
    )
    smart_hover_snapshot: smart_surface.SurfaceMeshSnapshot | None = None
    smart_hover_result: smart_surface.SurfaceRegionResult | None = None
    smart_hover_face: int | None = None
    selected_faces: tuple[SourceFaceSelection, ...] = ()
    selected_edges: tuple[SourceEdgeSelection, ...] = ()
    hovered_face: SourceFaceSelection | None = None
    hovered_edge: SourceEdgeSelection | None = None
    face_pick_cache: dict[tuple[str, int], int] = field(default_factory=dict)
    structural_edge_cache: dict[str, frozenset[EdgeKey]] = field(default_factory=dict)
    edge_incidence_cache: dict[str, dict[EdgeKey, tuple[int, ...]]] = field(default_factory=dict)
    source_region_cache: dict[str, tuple[SourceSurfaceRegion, ...]] = field(default_factory=dict)
    revision: int = 0

    def clear(self) -> None:
        if not (self.snapshots or self.selected_faces or self.selected_edges or self.hovered_face or self.hovered_edge):
            return
        self.snapshots.clear()
        self.smart_snapshots.clear()
        self.smart_session.clear()
        self.smart_hover_snapshot = None
        self.smart_hover_result = None
        self.smart_hover_face = None
        self.selected_faces = ()
        self.selected_edges = ()
        self.hovered_face = None
        self.hovered_edge = None
        self.face_pick_cache.clear()
        self.structural_edge_cache.clear()
        self.edge_incidence_cache.clear()
        self.source_region_cache.clear()
        self.revision += 1

    def clear_selection(self) -> None:
        if not (self.selected_faces or self.selected_edges):
            return
        self.selected_faces = ()
        self.selected_edges = ()
        self.smart_session.clear()
        self.smart_hover_snapshot = None
        self.smart_hover_result = None
        self.smart_hover_face = None
        self.revision += 1

    def set_pick_kind(self, kind: str) -> None:
        normalized: PickKind = "edge" if str(kind).lower() == "edge" else "face"
        if normalized == self.pick_kind:
            return
        self.pick_kind = normalized
        self.hovered_face = None
        self.hovered_edge = None
        self.smart_hover_snapshot = None
        self.smart_hover_result = None
        self.smart_hover_face = None
        self.revision += 1

    @property
    def selection_count(self) -> int:
        return len(self.selected_faces) + len(self.selected_edges)

    @property
    def can_create(self) -> bool:
        return bool(self.selected_faces or self.selected_edges)

    def ruled_strip_plan(self) -> RuledStripPlan | None:
        if self.selected_faces:
            return None
        return plan_ruled_strip_from_selection(self.snapshots, self.selected_edges)

    def structural_edges_for(self, snapshot: SourceMeshSnapshot) -> frozenset[EdgeKey]:
        cached = self.structural_edge_cache.get(snapshot.object_id)
        if cached is None:
            cached = structural_mesh_edges(snapshot, incidence=self.edge_incidence_for(snapshot))
            self.structural_edge_cache[snapshot.object_id] = cached
        return cached

    def edge_incidence_for(self, snapshot: SourceMeshSnapshot) -> dict[EdgeKey, tuple[int, ...]]:
        cached = self.edge_incidence_cache.get(snapshot.object_id)
        if cached is None:
            cached = edge_face_incidence(snapshot)
            self.edge_incidence_cache[snapshot.object_id] = cached
        return cached

    def source_regions_for(
        self,
        snapshot: SourceMeshSnapshot,
        seed_edges: Iterable[EdgeKey] | None = None,
    ) -> tuple[SourceSurfaceRegion, ...]:
        if seed_edges is not None:
            return source_surface_regions_near_edges(
                snapshot,
                seed_edges,
                incidence=self.edge_incidence_for(snapshot),
                maximum_regions=_MAX_TRACE_REGIONS,
            )
        cached = self.source_region_cache.get(snapshot.object_id)
        if cached is None:
            cached = source_surface_regions(snapshot)
            self.source_region_cache[snapshot.object_id] = cached
        return cached

    def snapshot_for_pick(self, ctx: Any, pick: Any) -> SourceMeshSnapshot | None:
        object_id = str(getattr(pick, "object_id", "") or "")
        object_index = getattr(pick, "object_index", None)
        if not object_id and object_index is None:
            return None
        key = object_id or f"index:{int(object_index)}"
        existing = self.snapshots.get(key)
        if existing is not None:
            return existing
        obj = None
        try:
            if object_id:
                obj = ctx.document.get(object_id)
        except Exception:
            obj = None
        if obj is None:
            try:
                obj = ctx.document.objects()[int(object_index)]
            except Exception:
                return None
        snapshot = SourceMeshSnapshot.from_object(obj, object_id=key, object_index=object_index)
        if snapshot is not None:
            self.snapshots[key] = snapshot
            self.structural_edge_cache.pop(key, None)
            self.edge_incidence_cache.pop(key, None)
            self.source_region_cache.pop(key, None)
        return snapshot

    def set_smart_automatic(self, enabled: bool) -> None:
        self.smart_session.automatic = bool(enabled)
        self.smart_hover_result = None
        self.smart_hover_face = None
        self.revision += 1

    def set_smart_tolerance(self, value: float) -> None:
        self.smart_session.tolerance = max(0.0, min(1.0, float(value)))
        self.smart_session.automatic = False
        self.smart_hover_result = None
        self.smart_hover_face = None
        self.revision += 1

    def _smart_snapshot_for_pick(self, ctx: Any, pick: Any) -> smart_surface.SurfaceMeshSnapshot | None:
        source = self.snapshot_for_pick(ctx, pick)
        if source is None:
            return None
        cached = self.smart_snapshots.get(source.object_id)
        if cached is not None:
            return cached
        snapshot = smart_surface.snapshot_from_pick(ctx, pick)
        if snapshot is not None:
            self.smart_snapshots[source.object_id] = snapshot
        return snapshot

    def _smart_region_from_pick(
        self,
        ctx: Any,
        pick: Any,
    ) -> tuple[smart_surface.SurfaceMeshSnapshot, int, smart_surface.SurfaceRegionResult] | None:
        snapshot = self._smart_snapshot_for_pick(ctx, pick)
        if snapshot is None:
            return None
        face_index = smart_surface.face_index_from_pick(pick, snapshot)
        if face_index is None or not 0 <= int(face_index) < len(snapshot.triangles):
            return None
        face_index = int(face_index)
        if (
            self.smart_hover_snapshot is snapshot
            and self.smart_hover_face == face_index
            and self.smart_hover_result is not None
        ):
            return snapshot, face_index, self.smart_hover_result
        profile = smart_surface.SurfaceSelectionProfile.cloth_support()
        if self.smart_session.automatic:
            result = smart_surface.auto_surface_region(
                snapshot,
                face_index,
                profile=profile,
                cache=self.smart_session.cache,
            )
        else:
            result = smart_surface.select_surface_region(
                snapshot,
                face_index,
                self.smart_session.tolerance,
                profile=profile,
                cache=self.smart_session.cache,
            )
        return snapshot, face_index, result

    def _sync_smart_selected_faces(self) -> None:
        values: list[SourceFaceSelection] = []
        for smart_snapshot, result in self.smart_session.selected_items:
            source_snapshot = self.snapshots.get(smart_snapshot.object_id)
            face_indices = result.face_indices
            if source_snapshot is not None:
                face_indices = clean_selected_face_indices(source_snapshot, face_indices)
            values.extend(
                SourceFaceSelection(smart_snapshot.object_id, int(face))
                for face in face_indices
            )
        self.selected_faces = tuple(dict.fromkeys(values))

    def _face_from_pick(self, ctx: Any, pick: Any) -> SourceFaceSelection | None:
        snapshot = self.snapshot_for_pick(ctx, pick)
        if snapshot is None:
            return None
        raw_index = getattr(pick, "element_index", None)
        cache_key: tuple[str, int] | None = None
        if raw_index is not None:
            cache_key = (snapshot.object_id, int(raw_index))
            cached = self.face_pick_cache.get(cache_key)
            if cached is not None and 0 <= cached < len(snapshot.triangles):
                return SourceFaceSelection(snapshot.object_id, cached)

        metadata = dict(getattr(pick, "metadata", {}) or {})
        raw_vertices = metadata.get("face_vertices")
        picked_vertices: tuple[Point3, ...] = ()
        if raw_vertices:
            try:
                picked_vertices = tuple(_point3(value) for value in raw_vertices)
            except Exception:
                picked_vertices = ()

        # Most scene actors retain the source triangle order, so keep this
        # constant-time path for hover. Verify it when the displayed picker
        # supplied vertices because LOD/cleaning filters can renumber cells.
        face_index: int | None = None
        if raw_index is not None and 0 <= int(raw_index) < len(snapshot.triangles):
            candidate = int(raw_index)
            if not picked_vertices or _triangle_matches_displayed_cell(snapshot, candidate, picked_vertices):
                face_index = candidate

        if face_index is None:
            world = getattr(pick, "world_pos", None)
            normal = getattr(pick, "normal", None)
            try:
                world_point = _point3(world) if world is not None else None
            except Exception:
                world_point = None
            try:
                normal_vector = _point3(normal) if normal is not None else None
            except Exception:
                normal_vector = None
            face_index = _nearest_source_triangle(
                snapshot,
                displayed_vertices=picked_vertices,
                world_pos=world_point,
                normal=normal_vector,
            )
        if face_index is None:
            return None
        if cache_key is not None:
            self.face_pick_cache[cache_key] = face_index
        return SourceFaceSelection(snapshot.object_id, face_index)

    def _edge_from_pick(self, ctx: Any, pick: Any) -> SourceEdgeSelection | None:
        snapshot = self.snapshot_for_pick(ctx, pick)
        if snapshot is None:
            return None
        metadata = dict(getattr(pick, "metadata", {}) or {})
        raw_indices = metadata.get("edge_vertex_indices") or metadata.get("vertex_indices")
        if raw_indices is not None:
            try:
                a, b = tuple(int(value) for value in raw_indices[:2])
                edge = _edge_key(a, b)
                if edge in set(snapshot.edges):
                    return SourceEdgeSelection(snapshot.object_id, edge)
            except Exception:
                pass
        index = getattr(pick, "element_index", None)
        edges = snapshot.edges
        if index is not None and 0 <= int(index) < len(edges):
            return SourceEdgeSelection(snapshot.object_id, edges[int(index)])
        raw_vertices = metadata.get("edge_vertices")
        if raw_vertices:
            try:
                first, second = (_point3(value) for value in raw_vertices[:2])
                edge = min(
                    edges,
                    key=lambda item: math.dist(snapshot.vertices[item[0]], first) + math.dist(snapshot.vertices[item[1]], second),
                )
                return SourceEdgeSelection(snapshot.object_id, edge)
            except Exception:
                pass
        world = getattr(pick, "world_pos", None)
        if world is not None and edges:
            point = _point3(world)
            edge = min(edges, key=lambda item: _point_segment_distance(point, *snapshot.edge_vertices(item)))
            return SourceEdgeSelection(snapshot.object_id, edge)
        return None

    def set_hover_from_pick(self, ctx: Any, pick: Any | None) -> bool:
        previous = (self.hovered_face, self.hovered_edge, self.smart_hover_result)
        self.hovered_face = None
        self.hovered_edge = None
        self.smart_hover_snapshot = None
        self.smart_hover_result = None
        self.smart_hover_face = None
        if pick is not None and getattr(pick, "hit", False):
            if self.pick_kind == "face":
                resolved = self._smart_region_from_pick(ctx, pick)
                if resolved is not None:
                    snapshot, face_index, result = resolved
                    self.smart_hover_snapshot = snapshot
                    self.smart_hover_face = face_index
                    self.smart_hover_result = result
                    self.hovered_face = SourceFaceSelection(snapshot.object_id, face_index)
            else:
                self.hovered_edge = self._edge_from_pick(ctx, pick)
        changed = previous != (self.hovered_face, self.hovered_edge, self.smart_hover_result)
        if changed:
            self.revision += 1
        return changed

    def select_from_pick(self, ctx: Any, pick: Any, *, additive: bool = False) -> bool:
        """Select one complete smart region, optionally adding it with Shift."""

        if self.pick_kind == "face":
            resolved = self._smart_region_from_pick(ctx, pick)
            if resolved is None:
                return False
            snapshot, face_index, region = resolved
            if additive:
                self.smart_session.add_region(snapshot, region)
            else:
                self.smart_session.adopt(snapshot, region)
            self.smart_session.seed_face = face_index
            self._sync_smart_selected_faces()
            self.smart_hover_snapshot = None
            self.smart_hover_result = None
            self.smart_hover_face = None
            self.hovered_face = None
        else:
            value = self._edge_from_pick(ctx, pick)
            if value is None:
                return False
            values = list(self.selected_edges)
            if additive:
                if value not in values:
                    values.append(value)
            else:
                values.remove(value) if value in values else values.append(value)
            self.selected_edges = tuple(values)
        self.revision += 1
        return True

    def toggle_from_pick(self, ctx: Any, pick: Any) -> bool:
        """Backward-compatible single-click entry point."""

        return self.select_from_pick(ctx, pick, additive=False)

    def predictions(self) -> GeometryTracePredictions:
        coplanar: list[SourceFaceSelection] = []
        boundary: list[SourceEdgeSelection] = []
        connected: list[SourceEdgeSelection] = []
        directional: list[SourceEdgeSelection] = []
        closure: list[SourceEdgeSelection] = []
        closure_plans: list[SourceFaceClosurePlan] = []

        faces_by_object: dict[str, set[int]] = defaultdict(set)
        for item in self.selected_faces:
            faces_by_object[item.object_id].add(item.face_index)
        for object_id, selected in faces_by_object.items():
            snapshot = self.snapshots.get(object_id)
            if snapshot is None:
                continue
            # Logical face growth is now owned by the shared smart-selection
            # API.  Cloth only derives the useful outer boundary from the
            # already accepted region; it must not run a second coplanar solver.
            boundary.extend(SourceEdgeSelection(object_id, edge) for edge in boundary_edges(snapshot, selected))

        edges_by_object: dict[str, list[EdgeKey]] = defaultdict(list)
        for item in self.selected_edges:
            edges_by_object[item.object_id].append(item.edge)
        for object_id, selected_list in edges_by_object.items():
            snapshot = self.snapshots.get(object_id)
            if snapshot is None:
                continue
            selected_set = set(selected_list)
            structural = self.structural_edges_for(snapshot)
            connected.extend(
                SourceEdgeSelection(object_id, edge)
                for edge in connected_unselected_edges(snapshot, selected_set, eligible_edges=structural)
            )
            directional.extend(
                SourceEdgeSelection(object_id, edge)
                for edge in directional_edge_continuation(
                    snapshot, selected_list, eligible_edges=structural
                )
            )
            plans = source_face_closure_plans(
                snapshot,
                selected_set,
                self.source_regions_for(snapshot, selected_set),
                semantic_edges=structural,
            )
            closure_plans.extend(plans)
            closure.extend(
                SourceEdgeSelection(object_id, edge)
                for plan in plans
                for edge in plan.missing_edges
            )

        selected_edge_set = set(self.selected_edges)
        boundary = [item for item in boundary if item not in selected_edge_set]
        connected = [item for item in connected if item not in selected_edge_set]
        directional = [item for item in directional if item not in selected_edge_set]
        closure = [item for item in dict.fromkeys(closure) if item not in selected_edge_set]
        return GeometryTracePredictions(
            coplanar_faces=tuple(coplanar),
            boundary_edges=tuple(boundary),
            connected_edges=tuple(connected),
            directional_edges=tuple(directional),
            closure_edges=tuple(closure),
            closable_faces=tuple(closure_plans),
            ruled_strip=self.ruled_strip_plan(),
        )

    def apply_prediction(self, kind: str) -> int:
        predictions = self.predictions()
        key = str(kind)
        if key == "coplanar":
            incoming = predictions.coplanar_faces
            if not incoming:
                return 0
            self.selected_faces = tuple(dict.fromkeys((*self.selected_faces, *incoming)))
        else:
            incoming = {
                "boundary": predictions.boundary_edges,
                "connected": predictions.connected_edges,
                "direction": predictions.directional_edges,
                "close_face": predictions.closure_edges,
            }.get(key, ())
            if not incoming:
                return 0
            self.selected_edges = tuple(dict.fromkeys((*self.selected_edges, *incoming)))
        self.revision += 1
        return len(incoming)

    def selected_face_triangles(self) -> tuple[tuple[Point3, Point3, Point3], ...]:
        values: list[tuple[Point3, Point3, Point3]] = []
        for item in self.selected_faces:
            snapshot = self.snapshots.get(item.object_id)
            if snapshot is None:
                continue
            triangle = snapshot.triangles[item.face_index]
            values.append(tuple(snapshot.vertices[index] for index in triangle))  # type: ignore[arg-type]
        return tuple(values)

    def hovered_face_triangles(self) -> tuple[tuple[Point3, Point3, Point3], ...]:
        result = self.smart_hover_result
        snapshot = self.smart_hover_snapshot
        if result is None or snapshot is None:
            return ()
        return tuple(
            tuple(snapshot.vertices[index] for index in snapshot.triangles[int(face)])
            for face in result.face_indices
        )  # type: ignore[return-value]

    def hovered_face_triangle(self) -> tuple[Point3, Point3, Point3] | None:
        values = self.hovered_face_triangles()
        return values[0] if values else None

    def selected_edge_segments(self) -> tuple[tuple[Point3, Point3], ...]:
        values: list[tuple[Point3, Point3]] = []
        for item in self.selected_edges:
            snapshot = self.snapshots.get(item.object_id)
            if snapshot is not None:
                values.append(snapshot.edge_vertices(item.edge))
        return tuple(values)

    def hovered_edge_segment(self) -> tuple[Point3, Point3] | None:
        item = self.hovered_edge
        snapshot = self.snapshots.get(item.object_id) if item is not None else None
        return snapshot.edge_vertices(item.edge) if item is not None and snapshot is not None else None

    def create(self, document: ClothDocument, drawing: ClothDrawingController) -> GeometryTraceOutcome:
        """Materialise a source-aware, bounded and transactional mesh trace.

        Mesh edges are never committed one-by-one with automatic face search.
        The source topology is analysed first, coplanar tessellation diagonals
        are removed, semantic source faces are reconstructed, then all remaining
        lines are added in one batch. Any invalid result restores the document.
        """

        if len(self.selected_edges) > _MAX_TRACE_SELECTED_EDGES:
            return GeometryTraceOutcome(
                False,
                message=f"Mesh trace is limited to {_MAX_TRACE_SELECTED_EDGES} selected edges per operation. Reduce the selection or trace it in parts.",
            )
        if len(self.selected_faces) > _MAX_TRACE_SELECTED_FACES:
            return GeometryTraceOutcome(
                False,
                message=f"Mesh trace is limited to {_MAX_TRACE_SELECTED_FACES} selected face triangles per operation. Reduce the selection or use Coplanar/Boundary.",
            )

        original = document.clone()
        errors_before = _validation_error_keys(document)
        folds_before = set(document.folds)
        created_patches: list[str] = []
        created_curves: list[str] = []
        created_patch_groups: list[tuple[str, ...]] = []
        notes: list[str] = []
        traced_boundaries: set[tuple[str, frozenset[EdgeKey]]] = set()
        materialised_source_edges: set[tuple[str, EdgeKey]] = set()
        ignored_diagonals = 0

        def register_outcome(outcome: ClothDrawingOutcome, patches_before: set[str]) -> tuple[str, ...]:
            if not outcome.committed:
                return ()
            created_curves.extend(outcome.created_curve_ids)
            new_patches = tuple(patch_id for patch_id in document.patches if patch_id not in patches_before)
            created_patches.extend(new_patches)
            return new_patches

        def trace_surface_loops(
            snapshot: SourceMeshSnapshot,
            face_indices: Sequence[int],
            loops: Sequence[Sequence[int]],
            *,
            source_kind: str,
        ) -> tuple[str, ...]:
            if not loops:
                return ()
            ordered = tuple(
                _orient_loop_to_source(snapshot, loop, face_indices)
                for loop in sorted(loops, key=lambda value: loop_perimeter(snapshot, value), reverse=True)
            )
            outer = ordered[0]
            if len(outer) < 3 or len(outer) > _MAX_FACE_BOUNDARY_EDGES:
                notes.append(f"{snapshot.name}: the inferred face boundary is invalid or too large.")
                return ()
            boundary = tuple(_edge_key(outer[index], outer[(index + 1) % len(outer)]) for index in range(len(outer)))
            boundary_key = (snapshot.object_id, frozenset(boundary))
            if boundary_key in traced_boundaries:
                return ()
            patches_before = set(document.patches)
            outcome = drawing.create_surface_from_positions(
                tuple(snapshot.vertices[index] for index in outer),
                metadata={
                    "cloth_source_object_id": snapshot.object_id,
                    "cloth_source_faces": tuple(sorted(int(value) for value in face_indices)),
                    "cloth_source_kind": source_kind,
                },
            )
            new_patches = register_outcome(outcome, patches_before)
            if not new_patches:
                notes.append(f"{snapshot.name}: {outcome.message}")
                return ()
            traced_boundaries.add(boundary_key)
            materialised_source_edges.update((snapshot.object_id, edge) for edge in boundary)
            if len(ordered) > 1:
                for inner in ordered[1:]:
                    for index, start_vertex in enumerate(inner):
                        end_vertex = inner[(index + 1) % len(inner)]
                        edge = _edge_key(start_vertex, end_vertex)
                        line_outcome = drawing.create_line_from_positions(
                            snapshot.vertices[start_vertex],
                            snapshot.vertices[end_vertex],
                            metadata={
                                "cloth_source_object_id": snapshot.object_id,
                                "cloth_source_faces": tuple(sorted(int(value) for value in face_indices)),
                                "cloth_source_internal_boundary": True,
                            },
                            auto_faces=False,
                        )
                        if line_outcome.committed:
                            created_curves.extend(line_outcome.created_curve_ids)
                            materialised_source_edges.add((snapshot.object_id, edge))
                notes.append(
                    f"{snapshot.name}: {len(ordered) - 1} internal loop(s) were retained as cut lines; surface holes are not filled automatically."
                )
            return new_patches

        try:
            strip = self.ruled_strip_plan()
            if strip is not None:
                patches_before = set(document.patches)
                outcome = drawing.create_ruled_strip_from_positions(
                    strip.rail_a,
                    strip.rail_b,
                    metadata={
                        "cloth_source_kind": "mesh_edge_rails",
                        "cloth_source_rail_components": tuple(
                            tuple((item.object_id, item.edge) for item in component)
                            for component in strip.source_components
                        ),
                    },
                )
                if not register_outcome(outcome, patches_before):
                    drawing._restore_document(original)
                    return GeometryTraceOutcome(False, message=outcome.message)
            else:
                # Explicit face picks remain authoritative. Coplanar expansion is
                # optional, but every selected component is traced transactionally.
                faces_by_object: dict[str, set[int]] = defaultdict(set)
                for item in self.selected_faces:
                    faces_by_object[item.object_id].add(item.face_index)
                for object_id, face_indices in faces_by_object.items():
                    snapshot = self.snapshots.get(object_id)
                    if snapshot is None:
                        continue
                    cleaned_faces = clean_selected_face_indices(snapshot, face_indices)
                    components = geometric_face_components(snapshot, cleaned_faces)
                    removed = len(set(face_indices)) - len(cleaned_faces)
                    if removed > 0:
                        notes.append(
                            f"{snapshot.name}: {removed} duplicate selected triangle(s) were removed before Take face."
                        )
                    for component_index, component in enumerate(components):
                        ordered_component = tuple(sorted(int(value) for value in component))
                        boundary = geometric_boundary_edges(snapshot, component)
                        loops = ordered_boundary_loops(boundary)
                        group: list[str] = []
                        # A simply connected planar component is exactly
                        # represented by its outer polygon. Curved components or
                        # components with holes are copied triangle-for-triangle
                        # so Take face never fills, caps or bridges geometry the
                        # user did not select.
                        if len(loops) == 1 and _faces_are_coplanar(snapshot, ordered_component):
                            group.extend(trace_surface_loops(
                                snapshot, ordered_component, loops, source_kind="selected_mesh_faces"
                            ))
                        else:
                            component_token = f"{snapshot.object_id}:{component_index}"
                            for face_index in ordered_component:
                                triangle = snapshot.triangles[face_index]
                                patches_before = set(document.patches)
                                outcome = drawing.create_surface_from_positions(
                                    tuple(snapshot.vertices[index] for index in triangle),
                                    metadata={
                                        "cloth_source_object_id": snapshot.object_id,
                                        "cloth_source_faces": (int(face_index),),
                                        "cloth_source_kind": "selected_mesh_triangle",
                                        "cloth_source_component": component_token,
                                    },
                                )
                                group.extend(register_outcome(outcome, patches_before))
                                if not outcome.committed:
                                    notes.append(f"{snapshot.name}: {outcome.message}")
                                    break
                            if len(loops) > 1:
                                notes.append(f"{snapshot.name}: a selected component with openings was copied strictly without filling its holes.")
                            elif not _faces_are_coplanar(snapshot, ordered_component):
                                notes.append(f"{snapshot.name}: a curved selected component was copied as exact technical textile faces.")
                        if group:
                            created_patch_groups.append(tuple(dict.fromkeys(group)))

                # Edge picks are interpreted using the source surface. Internal
                # triangulation diagonals are ignored; complete semantic source
                # faces are created before any residual lines.
                edges_by_object: dict[str, set[EdgeKey]] = defaultdict(set)
                for item in self.selected_edges:
                    edges_by_object[item.object_id].add(item.edge)
                region_count = 0
                for object_id, raw_selected in edges_by_object.items():
                    snapshot = self.snapshots.get(object_id)
                    if snapshot is None:
                        continue
                    structural = set(self.structural_edges_for(snapshot))
                    selected = raw_selected & structural
                    ignored_diagonals += len(raw_selected - structural)
                    regions = self.source_regions_for(snapshot, selected)
                    region_count += len(regions)
                    if region_count > _MAX_TRACE_REGIONS:
                        raise ValueError(
                            f"The selected area spans more than {_MAX_TRACE_REGIONS} semantic surface regions. Trace a smaller area."
                        )
                    complete_plans = (
                        plan
                        for plan in source_face_closure_plans(
                            snapshot, selected, regions, semantic_edges=structural
                        )
                        if plan.complete
                    )
                    for plan in complete_plans:
                        region = next(
                            (
                                candidate
                                for candidate in regions
                                if candidate.face_indices == plan.face_indices
                                and frozenset(candidate.boundary_edges) == frozenset(plan.boundary_edges)
                            ),
                            None,
                        )
                        if region is None:
                            continue
                        trace_surface_loops(
                            snapshot,
                            region.face_indices,
                            region.boundary_loops,
                            source_kind="inferred_source_face",
                        )

                    # A closed non-branching edge component that does not map to
                    # one source face is still a valid explicit boundary loop.
                    residual_items = tuple(
                        SourceEdgeSelection(object_id, edge)
                        for edge in sorted(selected)
                        if (object_id, edge) not in materialised_source_edges
                    )
                    for component in _selected_edge_components({object_id: snapshot}, residual_items):
                        loop = _ordered_closed_component_vertices(snapshot, component)
                        if loop is None:
                            continue
                        trace_surface_loops(snapshot, (), (loop,), source_kind="closed_mesh_edge_loop")

                    # Add residual semantic edges without invoking automatic face
                    # discovery after every line. This removes the exponential
                    # path-search failure seen on connected cube selections.
                    for edge in sorted(selected):
                        key = (object_id, edge)
                        if key in materialised_source_edges:
                            continue
                        outcome = drawing.create_line_from_positions(
                            *snapshot.edge_vertices(edge),
                            metadata={"cloth_source_object_id": object_id, "cloth_source_edge": edge},
                            auto_faces=False,
                        )
                        if outcome.committed:
                            created_curves.extend(outcome.created_curve_ids)
                            materialised_source_edges.add(key)
                        elif outcome.message and "already" not in outcome.message.lower():
                            notes.append(f"{snapshot.name}: {outcome.message}")

            committed = bool(created_patches or created_curves)
            if not committed:
                drawing._restore_document(original)
                return GeometryTraceOutcome(
                    False,
                    message=notes[0] if notes else "The selected mesh elements could not be traced.",
                )

            cut_count = _prune_new_fold_cycles(document, folds_before)
            errors_after = _validation_error_keys(document)
            new_errors = errors_after - errors_before
            if new_errors:
                first_code = sorted(new_errors)[0][0]
                drawing._restore_document(original)
                return GeometryTraceOutcome(
                    False,
                    message=f"Mesh trace was cancelled because the inferred Cloth topology is unsafe ({first_code}). Refine the selection or use Close face.",
                )

            # On a previously valid/empty document, prove that Apply can build a
            # finite non-degenerate triangle surface before accepting Trace.
            serious_before = {value for value in errors_before if value[0] != "cloth.no_faces"}
            if created_patches and not serious_before:
                from .mesh_builder import build_cloth_surface_mesh

                built = build_cloth_surface_mesh(document)
                if not built.success or built.mesh is None:
                    reason = built.issues[0] if built.issues else "surface triangulation failed"
                    drawing._restore_document(original)
                    return GeometryTraceOutcome(False, message=f"Mesh trace was cancelled before Apply: {reason}")
                for triangle in built.mesh.triangles:
                    if len(set(int(value) for value in triangle)) != 3:
                        drawing._restore_document(original)
                        return GeometryTraceOutcome(False, message="Mesh trace was cancelled because it produced a degenerate triangle.")
                    a, b, c = (built.mesh.vertices[int(index)] for index in triangle)
                    if _length(_cross(_sub(b, a), _sub(c, a))) <= 1.0e-12:
                        drawing._restore_document(original)
                        return GeometryTraceOutcome(False, message="Mesh trace was cancelled because it produced a zero-area triangle.")

        except Exception as exc:
            drawing._restore_document(original)
            return GeometryTraceOutcome(False, message=f"Mesh trace stopped safely: {exc}")

        summary = f"Traced {len(set(created_patches))} face(s) and {len(set(created_curves))} boundary curve(s) from the source topology."
        if ignored_diagonals:
            summary += f" Ignored {ignored_diagonals} coplanar triangulation diagonal(s)."
        if cut_count:
            summary += f" Added {cut_count} automatic cut(s) so the folded surface remains unfoldable."
        if notes:
            summary += f" {notes[0]}"
        self.clear_selection()
        return GeometryTraceOutcome(
            True,
            tuple(dict.fromkeys(created_patches)),
            tuple(dict.fromkeys(created_curves)),
            summary,
            tuple(created_patch_groups),
        )


def edge_face_incidence(snapshot: SourceMeshSnapshot) -> dict[EdgeKey, tuple[int, ...]]:
    values: dict[EdgeKey, list[int]] = defaultdict(list)
    for face_index, triangle in enumerate(snapshot.triangles):
        for index in range(3):
            values[_edge_key(triangle[index], triangle[(index + 1) % 3])].append(face_index)
    return {edge: tuple(faces) for edge, faces in values.items()}


def coplanar_face_region(
    snapshot: SourceMeshSnapshot,
    seed_face: int,
    *,
    angle_tolerance_degrees: float = 4.0,
    plane_tolerance: float | None = None,
    incidence: dict[EdgeKey, tuple[int, ...]] | None = None,
) -> tuple[int, ...]:
    if not 0 <= int(seed_face) < len(snapshot.triangles):
        return ()
    seed_triangle = snapshot.triangles[int(seed_face)]
    seed_normal = _triangle_normal(snapshot.vertices, seed_triangle)
    if seed_normal is None:
        return (int(seed_face),)
    origin = snapshot.vertices[seed_triangle[0]]
    if plane_tolerance is None:
        xs = [value[0] for value in snapshot.vertices]
        ys = [value[1] for value in snapshot.vertices]
        zs = [value[2] for value in snapshot.vertices]
        diagonal = math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
        plane_tolerance = max(1.0e-6, diagonal * 1.0e-6)
    cosine = math.cos(math.radians(max(0.0, float(angle_tolerance_degrees))))
    incidence_map = incidence or edge_face_incidence(snapshot)
    neighbors: dict[int, set[int]] = defaultdict(set)
    for faces in incidence_map.values():
        for face in faces:
            neighbors[face].update(other for other in faces if other != face)
    visited = {int(seed_face)}
    queue = deque((int(seed_face),))
    while queue:
        current = queue.popleft()
        for candidate in neighbors.get(current, ()):
            if candidate in visited:
                continue
            triangle = snapshot.triangles[candidate]
            normal = _triangle_normal(snapshot.vertices, triangle)
            if normal is None or abs(_dot(seed_normal, normal)) < cosine:
                continue
            if max(abs(_dot(_sub(snapshot.vertices[index], origin), seed_normal)) for index in triangle) > float(plane_tolerance):
                continue
            visited.add(candidate)
            queue.append(candidate)
    return tuple(sorted(visited))


def _selection_quantum(snapshot: SourceMeshSnapshot) -> float:
    return max(1.0e-9, _snapshot_scale(snapshot) * 1.0e-8)


def _geometric_vertex_key(snapshot: SourceMeshSnapshot, vertex_index: int, *, quantum: float | None = None) -> tuple[int, int, int]:
    step = float(quantum if quantum is not None else _selection_quantum(snapshot))
    point = snapshot.vertices[int(vertex_index)]
    return tuple(int(round(float(value) / step)) for value in point)  # type: ignore[return-value]


def clean_selected_face_indices(
    snapshot: SourceMeshSnapshot,
    selected_faces: Iterable[int],
) -> tuple[int, ...]:
    """Remove invalid and geometrically duplicate source triangles.

    Repaired/boolean meshes can retain coincident triangles under different
    indices.  A Shift selection must still materialise only one textile cell.
    """

    quantum = _selection_quantum(snapshot)
    kept_by_triangle: dict[tuple[tuple[int, int, int], ...], int] = {}
    for raw in sorted(set(int(value) for value in selected_faces)):
        if not 0 <= raw < len(snapshot.triangles):
            continue
        triangle = snapshot.triangles[raw]
        key = tuple(sorted(_geometric_vertex_key(snapshot, vertex, quantum=quantum) for vertex in triangle))
        kept_by_triangle.setdefault(key, raw)
    return tuple(sorted(kept_by_triangle.values()))


def _geometric_edge_key(
    snapshot: SourceMeshSnapshot,
    first: int,
    second: int,
    *,
    quantum: float,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    a = _geometric_vertex_key(snapshot, first, quantum=quantum)
    b = _geometric_vertex_key(snapshot, second, quantum=quantum)
    return (a, b) if a <= b else (b, a)


def geometric_face_components(
    snapshot: SourceMeshSnapshot,
    selected_faces: Iterable[int],
) -> tuple[frozenset[int], ...]:
    """Connected selected components using geometric edges, not only ids."""

    selected = set(clean_selected_face_indices(snapshot, selected_faces))
    if not selected:
        return ()
    quantum = _selection_quantum(snapshot)
    edge_faces: dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]] = defaultdict(list)
    for face_index in selected:
        triangle = snapshot.triangles[face_index]
        for index in range(3):
            edge_faces[_geometric_edge_key(
                snapshot, triangle[index], triangle[(index + 1) % 3], quantum=quantum
            )].append(face_index)
    neighbors: dict[int, set[int]] = defaultdict(set)
    for faces in edge_faces.values():
        inside = tuple(dict.fromkeys(face for face in faces if face in selected))
        for face in inside:
            neighbors[face].update(other for other in inside if other != face)
    components: list[frozenset[int]] = []
    remaining = set(selected)
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        component = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            for neighbor in neighbors.get(current, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(frozenset(component))
    return tuple(components)


def geometric_boundary_edges(
    snapshot: SourceMeshSnapshot,
    face_indices: Iterable[int],
) -> tuple[EdgeKey, ...]:
    """Boundary edges after welding coincident source vertices logically."""

    selected = clean_selected_face_indices(snapshot, face_indices)
    if not selected:
        return ()
    quantum = _selection_quantum(snapshot)
    representative: dict[tuple[int, int, int], int] = {}
    counts: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = defaultdict(int)
    for face_index in selected:
        triangle = snapshot.triangles[face_index]
        for vertex in triangle:
            representative.setdefault(_geometric_vertex_key(snapshot, vertex, quantum=quantum), int(vertex))
        for index in range(3):
            counts[_geometric_edge_key(
                snapshot, triangle[index], triangle[(index + 1) % 3], quantum=quantum
            )] += 1
    edges: list[EdgeKey] = []
    for (first_key, second_key), count in counts.items():
        if count == 1:
            edges.append(_edge_key(representative[first_key], representative[second_key]))
    return tuple(sorted(set(edges)))


def face_components(
    snapshot: SourceMeshSnapshot,
    selected_faces: Iterable[int],
    *,
    incidence: dict[EdgeKey, tuple[int, ...]] | None = None,
) -> tuple[frozenset[int], ...]:
    selected = {int(value) for value in selected_faces if 0 <= int(value) < len(snapshot.triangles)}
    if not selected:
        return ()
    incidence_map = incidence or edge_face_incidence(snapshot)
    neighbors: dict[int, set[int]] = defaultdict(set)
    for faces in incidence_map.values():
        inside = [face for face in faces if face in selected]
        for face in inside:
            neighbors[face].update(other for other in inside if other != face)
    components: list[frozenset[int]] = []
    remaining = set(selected)
    while remaining:
        seed = remaining.pop()
        component = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            for neighbor in neighbors.get(current, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(frozenset(component))
    return tuple(components)


def boundary_edges(snapshot: SourceMeshSnapshot, face_indices: Iterable[int]) -> tuple[EdgeKey, ...]:
    counts: dict[EdgeKey, int] = defaultdict(int)
    for face_index in face_indices:
        if not 0 <= int(face_index) < len(snapshot.triangles):
            continue
        triangle = snapshot.triangles[int(face_index)]
        for index in range(3):
            counts[_edge_key(triangle[index], triangle[(index + 1) % 3])] += 1
    return tuple(sorted(edge for edge, count in counts.items() if count == 1))


def ordered_boundary_loops(edges: Iterable[EdgeKey]) -> tuple[tuple[int, ...], ...]:
    """Return only genuinely closed, non-branching boundary loops.

    The previous walker could accept an open chain when its final edge happened
    to have been removed from the shared ``remaining`` set. That made incomplete
    mesh selections look like faces and later corrupted triangulation.
    """

    all_edges = {_edge_key(int(a), int(b)) for a, b in edges if int(a) != int(b)}
    if not all_edges:
        return ()
    vertex_edges: dict[int, set[EdgeKey]] = defaultdict(set)
    for edge in all_edges:
        vertex_edges[edge[0]].add(edge)
        vertex_edges[edge[1]].add(edge)

    remaining = set(all_edges)
    loops: list[tuple[int, ...]] = []
    while remaining:
        seed = min(remaining)
        component = {seed}
        queue = [seed]
        remaining.remove(seed)
        while queue:
            current = queue.pop()
            for vertex in current:
                for neighbor in vertex_edges.get(vertex, ()):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)
        adjacency: dict[int, set[int]] = defaultdict(set)
        for a, b in component:
            adjacency[a].add(b)
            adjacency[b].add(a)
        if len(component) < 3 or any(len(neighbors) != 2 for neighbors in adjacency.values()):
            continue
        start = min(adjacency)
        loop = [start]
        previous: int | None = None
        current = start
        used: set[EdgeKey] = set()
        for _ in range(len(component) + 1):
            candidates = sorted(
                neighbor
                for neighbor in adjacency[current]
                if _edge_key(current, neighbor) not in used and neighbor != previous
            )
            if not candidates:
                break
            following = candidates[0]
            used.add(_edge_key(current, following))
            if following == start:
                if len(used) == len(component) and len(loop) >= 3:
                    loops.append(tuple(loop))
                break
            loop.append(following)
            previous, current = current, following
    return tuple(loops)


def loop_perimeter(snapshot: SourceMeshSnapshot, loop: Sequence[int]) -> float:
    return sum(math.dist(snapshot.vertices[loop[index]], snapshot.vertices[loop[(index + 1) % len(loop)]]) for index in range(len(loop)))


def connected_unselected_edges(
    snapshot: SourceMeshSnapshot,
    selected_edges: set[EdgeKey],
    *,
    eligible_edges: Iterable[EdgeKey] | None = None,
) -> tuple[EdgeKey, ...]:
    """Return one-ring connected semantic edges, excluding mesh diagonals."""

    vertices = {vertex for edge in selected_edges for vertex in edge}
    candidates = tuple(eligible_edges) if eligible_edges is not None else tuple(structural_mesh_edges(snapshot))
    return tuple(
        edge
        for edge in sorted(candidates)
        if edge not in selected_edges and (edge[0] in vertices or edge[1] in vertices)
    )


def directional_edge_continuation(
    snapshot: SourceMeshSnapshot,
    selected_edges: Sequence[EdgeKey],
    *,
    maximum_turn_degrees: float = 48.0,
    max_steps_per_end: int = 256,
    eligible_edges: Iterable[EdgeKey] | None = None,
) -> tuple[EdgeKey, ...]:
    selected = set(selected_edges)
    if not selected:
        return ()
    adjacency: dict[int, list[EdgeKey]] = defaultdict(list)
    selected_degree: dict[int, int] = defaultdict(int)
    candidates = tuple(eligible_edges) if eligible_edges is not None else snapshot.edges
    for edge in candidates:
        adjacency[edge[0]].append(edge)
        adjacency[edge[1]].append(edge)
    for edge in selected:
        selected_degree[edge[0]] += 1
        selected_degree[edge[1]] += 1
    endpoints = [vertex for vertex, degree in selected_degree.items() if degree == 1]
    if not endpoints and len(selected) == 1:
        endpoints = list(next(iter(selected)))
    cosine = math.cos(math.radians(maximum_turn_degrees))
    predicted: list[EdgeKey] = []
    used = set(selected)
    for endpoint in sorted(endpoints):
        touching = [edge for edge in selected if endpoint in edge]
        if not touching:
            continue
        current_edge = touching[-1]
        previous = current_edge[0] if current_edge[1] == endpoint else current_edge[1]
        current = endpoint
        for _ in range(max_steps_per_end):
            incoming = _normalized(_sub(snapshot.vertices[current], snapshot.vertices[previous]))
            if incoming is None:
                break
            ranked: list[tuple[float, EdgeKey, int]] = []
            for candidate in adjacency.get(current, ()):
                if candidate in used:
                    continue
                other = candidate[1] if candidate[0] == current else candidate[0]
                outgoing = _normalized(_sub(snapshot.vertices[other], snapshot.vertices[current]))
                if outgoing is None:
                    continue
                alignment = _dot(incoming, outgoing)
                if alignment >= cosine:
                    ranked.append((alignment, candidate, other))
            if not ranked:
                break
            ranked.sort(key=lambda item: (-item[0], item[1]))
            _alignment, chosen, other = ranked[0]
            predicted.append(chosen)
            used.add(chosen)
            previous, current = current, other
    return tuple(predicted)


__all__ = [
    "ClothGeometryTraceController",
    "GeometryTraceOutcome",
    "GeometryTracePredictions",
    "SourceFaceClosurePlan",
    "SourceSurfaceRegion",
    "RuledStripPlan",
    "SourceEdgeSelection",
    "SourceFaceSelection",
    "SourceMeshSnapshot",
    "boundary_edges",
    "clean_selected_face_indices",
    "geometric_boundary_edges",
    "geometric_face_components",
    "connected_unselected_edges",
    "coplanar_face_region",
    "directional_edge_continuation",
    "face_components",
    "ordered_boundary_loops",
    "plan_ruled_strip_from_selection",
    "source_face_closure_plans",
    "source_surface_regions",
    "source_surface_regions_near_edges",
    "structural_mesh_edges",
]
