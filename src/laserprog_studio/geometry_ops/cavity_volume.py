# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Iterable

MM3_PER_LITER = 1_000_000.0
_EPS = 1.0e-9


@dataclass(frozen=True)
class SurfaceShell:
    """One connected triangle-surface component of a WorkMesh."""

    triangle_indices: tuple[int, ...]
    vertex_indices: tuple[int, ...]
    closed: bool
    volume_mm3: float
    surface_area_mm2: float
    centroid: tuple[float, float, float]
    open_edge_count: int = 0

    @property
    def volume_liters(self) -> float:
        return self.volume_mm3 / MM3_PER_LITER


@dataclass(frozen=True)
class CavityVolumeReport:
    """Volume diagnosis for a selected fused mesh.

    The intended workflow is a watertight fused part containing one or more
    enclosed voids. In that common CAD/boolean output, the external skin and the
    internal cavity skins are separate closed surface shells. The algorithm keeps
    the largest closed shell as the outside envelope and sums every other closed
    shell whose centroid is inside that outside shell.
    """

    mesh_name: str
    triangle_count: int
    vertex_count: int
    shell_count: int
    closed_shell_count: int
    cavity_count: int
    cavity_volume_mm3: float
    outer_volume_mm3: float
    warning: str | None = None
    shells: tuple[SurfaceShell, ...] = ()
    cavity_shell_indices: tuple[int, ...] = ()

    @property
    def cavity_volume_liters(self) -> float:
        return self.cavity_volume_mm3 / MM3_PER_LITER

    @property
    def outer_volume_liters(self) -> float:
        return self.outer_volume_mm3 / MM3_PER_LITER

    @property
    def solid_volume_liters_estimate(self) -> float:
        return max(self.outer_volume_mm3 - self.cavity_volume_mm3, 0.0) / MM3_PER_LITER


Vector3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


def _as_vertices(raw_vertices: Iterable[Any]) -> list[Vector3]:
    vertices: list[Vector3] = []
    for value in raw_vertices or []:
        if len(value) < 3:  # type: ignore[arg-type]
            continue
        vertices.append((float(value[0]), float(value[1]), float(value[2])))
    return vertices


def _as_triangles(raw_triangles: Iterable[Any], vertex_count: int) -> list[Triangle]:
    triangles: list[Triangle] = []
    for tri in raw_triangles or []:
        if len(tri) < 3:  # type: ignore[arg-type]
            continue
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        if a == b or b == c or c == a:
            continue
        if 0 <= a < vertex_count and 0 <= b < vertex_count and 0 <= c < vertex_count:
            triangles.append((a, b, c))
    return triangles


def _sub(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vector3, b: Vector3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Vector3) -> float:
    return sqrt(_dot(a, a))


def _triangle_area(a: Vector3, b: Vector3, c: Vector3) -> float:
    return 0.5 * _norm(_cross(_sub(b, a), _sub(c, a)))


def _signed_tetra_volume(a: Vector3, b: Vector3, c: Vector3) -> float:
    return _dot(a, _cross(b, c)) / 6.0


def _connected_triangle_components(triangles: list[Triangle]) -> list[list[int]]:
    if not triangles:
        return []
    by_vertex: dict[int, list[int]] = {}
    for tri_idx, tri in enumerate(triangles):
        for vertex_idx in tri:
            by_vertex.setdefault(vertex_idx, []).append(tri_idx)

    visited = [False] * len(triangles)
    components: list[list[int]] = []
    for seed in range(len(triangles)):
        if visited[seed]:
            continue
        stack = [seed]
        visited[seed] = True
        component: list[int] = []
        while stack:
            tri_idx = stack.pop()
            component.append(tri_idx)
            for vertex_idx in triangles[tri_idx]:
                for neighbour in by_vertex.get(vertex_idx, ()):  # connected through indexed vertices
                    if not visited[neighbour]:
                        visited[neighbour] = True
                        stack.append(neighbour)
        components.append(component)
    return components


def _analyse_shell(vertices: list[Vector3], triangles: list[Triangle], component: list[int]) -> SurfaceShell:
    used_vertices: set[int] = set()
    edge_counts: dict[tuple[int, int], int] = {}
    signed_volume = 0.0
    surface_area = 0.0
    centroid_weighted = [0.0, 0.0, 0.0]
    weight_sum = 0.0

    for tri_idx in component:
        a_i, b_i, c_i = triangles[tri_idx]
        used_vertices.update((a_i, b_i, c_i))
        for e0, e1 in ((a_i, b_i), (b_i, c_i), (c_i, a_i)):
            edge = (e0, e1) if e0 < e1 else (e1, e0)
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
        a, b, c = vertices[a_i], vertices[b_i], vertices[c_i]
        area = _triangle_area(a, b, c)
        surface_area += area
        signed_volume += _signed_tetra_volume(a, b, c)
        tri_centroid = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0)
        centroid_weighted[0] += tri_centroid[0] * area
        centroid_weighted[1] += tri_centroid[1] * area
        centroid_weighted[2] += tri_centroid[2] * area
        weight_sum += area

    open_edge_count = sum(1 for count in edge_counts.values() if count != 2)
    if weight_sum > _EPS:
        centroid = (centroid_weighted[0] / weight_sum, centroid_weighted[1] / weight_sum, centroid_weighted[2] / weight_sum)
    elif used_vertices:
        pts = [vertices[i] for i in used_vertices]
        centroid = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
            sum(p[2] for p in pts) / len(pts),
        )
    else:
        centroid = (0.0, 0.0, 0.0)

    return SurfaceShell(
        triangle_indices=tuple(component),
        vertex_indices=tuple(sorted(used_vertices)),
        closed=(open_edge_count == 0),
        volume_mm3=abs(float(signed_volume)),
        surface_area_mm2=float(surface_area),
        centroid=centroid,
        open_edge_count=int(open_edge_count),
    )


def _ray_intersects_triangle(origin: Vector3, direction: Vector3, a: Vector3, b: Vector3, c: Vector3) -> bool:
    # Möller-Trumbore ray/triangle intersection. Used only as a classifier for
    # shell containment, so reject hits exactly behind/at the origin and rely on
    # several non-axis-aligned rays in _point_inside_shell.
    edge1 = _sub(b, a)
    edge2 = _sub(c, a)
    h = _cross(direction, edge2)
    det = _dot(edge1, h)
    if -_EPS < det < _EPS:
        return False
    inv_det = 1.0 / det
    s = _sub(origin, a)
    u = inv_det * _dot(s, h)
    if u < -_EPS or u > 1.0 + _EPS:
        return False
    q = _cross(s, edge1)
    v = inv_det * _dot(direction, q)
    if v < -_EPS or u + v > 1.0 + _EPS:
        return False
    t = inv_det * _dot(edge2, q)
    return t > 1.0e-7


def _point_inside_shell(point: Vector3, vertices: list[Vector3], triangles: list[Triangle], shell: SurfaceShell) -> bool:
    # Use an odd/even ray cast with several directions. The median vote makes the
    # classifier tolerant when one ray crosses exactly through a vertex/edge.
    directions: tuple[Vector3, ...] = (
        (1.0, 0.371390676, 0.113227703),
        (0.271247, 1.0, 0.48721),
        (0.391, 0.217, 1.0),
        (-1.0, 0.263, 0.419),
        (0.181, -1.0, 0.337),
    )
    inside_votes = 0
    valid_votes = 0
    for direction in directions:
        count = 0
        for tri_idx in shell.triangle_indices:
            a_i, b_i, c_i = triangles[tri_idx]
            if _ray_intersects_triangle(point, direction, vertices[a_i], vertices[b_i], vertices[c_i]):
                count += 1
        valid_votes += 1
        if count % 2 == 1:
            inside_votes += 1
    return inside_votes > valid_votes // 2



def _weld_vertex_key(vertex: Any, tolerance: float) -> tuple[int, int, int]:
    if tolerance <= 0.0:
        return (hash(float(vertex[0])), hash(float(vertex[1])), hash(float(vertex[2])))
    inv = 1.0 / float(tolerance)
    return (int(round(float(vertex[0]) * inv)), int(round(float(vertex[1]) * inv)), int(round(float(vertex[2]) * inv)))


def combine_meshes_for_cavity_measurement(meshes: Iterable[Any], *, name: str = "selection", weld_tolerance: float = 1.0e-5) -> Any:
    """Combine several WorkMesh-like parts into one mesh for VOL analysis.

    The selected pieces may be separate panels that only become watertight when
    considered together.  Therefore the combiner welds coincident vertices
    across parts before measuring.  Without this weld, two panels sharing the
    same geometric edge still have different vertex indices, so the shell looks
    open to the edge-count based watertightness test.
    """
    from laserprog_studio.domain.work_model import WorkMesh

    vertices: list[Any] = []
    triangles: list[Triangle] = []
    vertex_lookup: dict[tuple[int, int, int], int] = {}
    count = 0
    for mesh in meshes:
        part_vertices = list(getattr(mesh, "vertices", []) or [])
        part_triangles = list(getattr(mesh, "triangles", []) or [])
        remap: list[int] = []
        for vertex in part_vertices:
            if len(vertex) < 3:  # type: ignore[arg-type]
                remap.append(-1)
                continue
            key = _weld_vertex_key(vertex, float(weld_tolerance))
            mapped = vertex_lookup.get(key)
            if mapped is None:
                mapped = len(vertices)
                vertex_lookup[key] = mapped
                vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
            remap.append(mapped)
        for tri in part_triangles:
            if len(tri) < 3:  # type: ignore[arg-type]
                continue
            try:
                a, b, c = remap[int(tri[0])], remap[int(tri[1])], remap[int(tri[2])]
            except Exception:
                continue
            if a < 0 or b < 0 or c < 0 or a == b or b == c or c == a:
                continue
            triangles.append((a, b, c))
        count += 1
    mesh_name = str(name or "selection")
    if count > 1 and mesh_name == "selection":
        mesh_name = f"selection ({count} parts)"
    return WorkMesh(name=mesh_name, vertices=vertices, triangles=triangles)


def measure_box_generator_selection(meshes: Iterable[Any], selected_indices: Iterable[int]) -> CavityVolumeReport | None:
    """Return an exact cavity report for a complete generated BOX selection.

    The BOX tool creates six separate solid boards.  That geometry is not a
    clean boolean union: boards touch/overlap and contain internal faces, so a
    pure edge-count watertightness test can legitimately reject the selection.
    BOX boards carry generation metadata with the exact outer dimensions and
    material thickness; when the selected parts are the complete generated group,
    use that exact workshop metadata to report the internal volume.
    """
    mesh_list = list(meshes)
    valid = [int(i) for i in selected_indices if 0 <= int(i) < len(mesh_list)]
    if not valid:
        return None
    try:
        from laserprog_studio.fabrication.box_generator import box_metadata
    except Exception:  # pragma: no cover
        try:
            from laserprog_studio.fabrication.box_generator import box_metadata
        except Exception:
            return None

    selected_metas: list[dict[str, Any]] = []
    for idx in valid:
        meta = box_metadata(mesh_list[idx])
        if not isinstance(meta, dict):
            return None
        selected_metas.append(meta)

    group_id = str(selected_metas[0].get("group_id") or "")
    if not group_id:
        return None
    if any(str(meta.get("group_id") or "") != group_id for meta in selected_metas):
        return None

    group_indices = [
        i for i, mesh in enumerate(mesh_list)
        if (box_metadata(mesh) or {}).get("group_id") == group_id
    ]
    triangle_count = sum(len(getattr(mesh_list[i], "triangles", []) or []) for i in valid)
    vertex_count = sum(len(getattr(mesh_list[i], "vertices", []) or []) for i in valid)
    if set(valid) != set(group_indices):
        return CavityVolumeReport(
            mesh_name=f"partial box ({len(valid)}/{len(group_indices)} parts)",
            triangle_count=triangle_count,
            vertex_count=vertex_count,
            shell_count=0,
            closed_shell_count=0,
            cavity_count=0,
            cavity_volume_mm3=0.0,
            outer_volume_mm3=0.0,
            warning="Select every panel of this BOX to measure its internal volume.",
        )

    meta = selected_metas[0]
    try:
        width = float(meta.get("outer_width_mm") or 0.0)
        depth = float(meta.get("outer_depth_mm") or 0.0)
        height = float(meta.get("outer_height_mm") or 0.0)
        thickness = float(meta.get("thickness_mm") or 0.0)
    except Exception:
        return None
    if width <= 0.0 or depth <= 0.0 or height <= 0.0 or thickness <= 0.0:
        return None

    inner_w = max(0.0, width - 2.0 * thickness)
    inner_d = max(0.0, depth - 2.0 * thickness)
    inner_h = max(0.0, height - 2.0 * thickness)
    outer_volume = width * depth * height
    inner_volume = inner_w * inner_d * inner_h
    return CavityVolumeReport(
        mesh_name=f"Generated BOX ({len(group_indices)} parts)",
        triangle_count=sum(len(getattr(mesh_list[i], "triangles", []) or []) for i in group_indices),
        vertex_count=sum(len(getattr(mesh_list[i], "vertices", []) or []) for i in group_indices),
        shell_count=1,
        closed_shell_count=1,
        cavity_count=1,
        cavity_volume_mm3=float(inner_volume),
        outer_volume_mm3=float(outer_volume),
        warning=None,
    )

def measure_cavity_volume(mesh: Any, *, single_closed_shell_as_cavity: bool = False) -> CavityVolumeReport:
    """Measure enclosed internal cavity volume for a selected WorkMesh.

    Limitations are explicit and deliberate: this measures closed internal voids
    represented as closed inner shells. Open pockets / through-holes are not
    counted because their volume is not a well-defined sealed cavity.
    """

    mesh_name = str(getattr(mesh, "name", "selected mesh") or "selected mesh")
    vertices = _as_vertices(getattr(mesh, "vertices", []))
    triangles = _as_triangles(getattr(mesh, "triangles", []), len(vertices))
    if not vertices or not triangles:
        return CavityVolumeReport(
            mesh_name=mesh_name,
            triangle_count=len(triangles),
            vertex_count=len(vertices),
            shell_count=0,
            closed_shell_count=0,
            cavity_count=0,
            cavity_volume_mm3=0.0,
            outer_volume_mm3=0.0,
            warning="The selected part has no usable triangles.",
        )

    components = _connected_triangle_components(triangles)
    shells = tuple(_analyse_shell(vertices, triangles, component) for component in components)
    closed_shells = [(idx, shell) for idx, shell in enumerate(shells) if shell.closed and shell.volume_mm3 > _EPS]
    if not closed_shells:
        return CavityVolumeReport(
            mesh_name=mesh_name,
            triangle_count=len(triangles),
            vertex_count=len(vertices),
            shell_count=len(shells),
            closed_shell_count=0,
            cavity_count=0,
            cavity_volume_mm3=0.0,
            outer_volume_mm3=0.0,
            warning="No closed volume detected. Repair/close the mesh before measuring.",
            shells=shells,
        )
    if len(closed_shells) == 1:
        outer_idx, outer = closed_shells[0]
        if single_closed_shell_as_cavity:
            return CavityVolumeReport(
                mesh_name=mesh_name,
                triangle_count=len(triangles),
                vertex_count=len(vertices),
                shell_count=len(shells),
                closed_shell_count=1,
                cavity_count=1,
                cavity_volume_mm3=outer.volume_mm3,
                outer_volume_mm3=outer.volume_mm3,
                warning=None,
                shells=shells,
                cavity_shell_indices=(outer_idx,),
            )
        return CavityVolumeReport(
            mesh_name=mesh_name,
            triangle_count=len(triangles),
            vertex_count=len(vertices),
            shell_count=len(shells),
            closed_shell_count=1,
            cavity_count=0,
            cavity_volume_mm3=0.0,
            outer_volume_mm3=outer.volume_mm3,
            warning="Only one closed shell detected: no separate internal cavity to measure.",
            shells=shells,
            cavity_shell_indices=(),
        )

    outer_idx, outer = max(closed_shells, key=lambda item: item[1].volume_mm3)
    cavity_indices: list[int] = []
    cavity_volume = 0.0
    for idx, shell in closed_shells:
        if idx == outer_idx:
            continue
        if _point_inside_shell(shell.centroid, vertices, triangles, outer):
            cavity_indices.append(idx)
            cavity_volume += shell.volume_mm3

    warning: str | None = None
    if not cavity_indices:
        warning = "Several closed volumes exist, but none is inside the main shell. Nothing was counted as a cavity."

    return CavityVolumeReport(
        mesh_name=mesh_name,
        triangle_count=len(triangles),
        vertex_count=len(vertices),
        shell_count=len(shells),
        closed_shell_count=len(closed_shells),
        cavity_count=len(cavity_indices),
        cavity_volume_mm3=float(cavity_volume),
        outer_volume_mm3=float(outer.volume_mm3),
        warning=warning,
        shells=shells,
        cavity_shell_indices=tuple(cavity_indices),
    )


__all__ = [
    "MM3_PER_LITER",
    "SurfaceShell",
    "CavityVolumeReport",
    "combine_meshes_for_cavity_measurement",
    "measure_box_generator_selection",
    "measure_cavity_volume",
]
