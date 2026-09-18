# -*- coding: utf-8 -*-
"""Boolean-ready solid generation from planar regions.

This module is the topology boundary between 2D creator tools and the 3D
boolean kernel.  It deliberately does not depend on Qt, VTK, or a Creator
controller.

The preferred backend is Manifold's ``CrossSection.extrude`` constructor: the
same kernel used by LaserProg's boolean operations creates the solid, so a
Plan Tracer result cannot leave the tool in a topology that the boolean engine
rejects later.  A deterministic indexed fallback remains available for tests
and installations where the optional extension is temporarily unavailable.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any, Iterable, Sequence

from .manifold_contract import (
    construct_manifold,
    manifold_is_valid,
    manifold_status_text,
)

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
PlanarRegion = tuple[Sequence[Point2], Sequence[Sequence[Point2]]]


@dataclass(frozen=True, slots=True)
class BooleanReadySolidReport:
    backend: str
    input_regions: int
    polygon_components: int
    footprint_area: float
    vertices: int
    triangles: int
    boundary_edges: int
    nonmanifold_edges: int
    nonmanifold_vertices: int
    signed_volume: float
    precision_grid: float
    manifold_status: str = "not_checked"
    native_verified: bool = False


def _iter_polygons(geometry: Any) -> tuple[Any, ...]:
    if geometry is None or bool(getattr(geometry, "is_empty", True)):
        return ()
    kind = str(getattr(geometry, "geom_type", "") or "")
    if kind == "Polygon":
        return (geometry,)
    if kind == "MultiPolygon":
        return tuple(part for part in geometry.geoms if not part.is_empty)
    if hasattr(geometry, "geoms"):
        return tuple(poly for part in geometry.geoms for poly in _iter_polygons(part))
    return ()


def _clean_ring(points: Sequence[Point2], *, epsilon: float = 1.0e-10) -> tuple[Point2, ...]:
    cleaned: list[Point2] = []
    eps_sq = float(epsilon) ** 2
    for value in points or ():
        try:
            point = (float(value[0]), float(value[1]))
        except Exception:
            continue
        if not all(math.isfinite(component) for component in point):
            continue
        if cleaned and (cleaned[-1][0] - point[0]) ** 2 + (cleaned[-1][1] - point[1]) ** 2 <= eps_sq:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and (cleaned[0][0] - cleaned[-1][0]) ** 2 + (cleaned[0][1] - cleaned[-1][1]) ** 2 <= eps_sq:
        cleaned.pop()
    return tuple(cleaned) if len(cleaned) >= 3 else ()


def _geometry_extent(polygons: Sequence[Any]) -> float:
    if not polygons:
        return 1.0
    bounds = [poly.bounds for poly in polygons]
    xmin = min(float(item[0]) for item in bounds)
    ymin = min(float(item[1]) for item in bounds)
    xmax = max(float(item[2]) for item in bounds)
    ymax = max(float(item[3]) for item in bounds)
    extent = max(xmax - xmin, ymax - ymin, 1.0)
    return extent if math.isfinite(extent) else 1.0


def _has_zero_clearance_contacts(polygons: Sequence[Any], *, tolerance: float) -> bool:
    """Return True for point/edge contacts that extrude to non-manifold seams."""

    tol = max(float(tolerance), 0.0)
    for polygon in polygons:
        exterior = polygon.exterior
        interiors = tuple(polygon.interiors)
        for interior in interiors:
            try:
                if float(exterior.distance(interior)) <= tol:
                    return True
            except Exception:
                continue
        for index, first in enumerate(interiors):
            for second in interiors[index + 1 :]:
                try:
                    if float(first.distance(second)) <= tol:
                        return True
                except Exception:
                    continue
    for index, first in enumerate(polygons):
        for second in polygons[index + 1 :]:
            try:
                if float(first.distance(second)) <= tol:
                    return True
            except Exception:
                continue
    return False


def build_valid_planar_footprint(
    regions: Iterable[PlanarRegion],
    *,
    precision_grid: float | None = None,
) -> tuple[Any, int, float]:
    """Return one valid polygonal footprint and its normalization metadata.

    Invalid rings are repaired *before* extrusion.  Lower-dimensional remnants
    produced by ``make_valid`` are intentionally discarded: lines and points
    cannot define a solid.  A small precision grid nodes almost-coincident
    intersections consistently without visibly changing normal CAD dimensions.
    """

    try:
        import shapely
        from shapely.geometry import Polygon
    except Exception as exc:  # pragma: no cover - pinned production dependency
        raise RuntimeError("Planar solid generation requires Shapely.") from exc

    source_polygons: list[Any] = []
    region_count = 0
    for outer_raw, holes_raw in regions:
        region_count += 1
        outer = _clean_ring(tuple(outer_raw or ()))
        holes = tuple(
            hole
            for hole in (_clean_ring(tuple(values or ())) for values in tuple(holes_raw or ()))
            if len(hole) >= 3
        )
        if len(outer) < 3:
            continue
        try:
            candidate = Polygon(outer, holes)
        except Exception:
            continue
        if candidate.is_empty or float(getattr(candidate, "area", 0.0)) <= 1.0e-12:
            continue
        if not candidate.is_valid:
            try:
                candidate = shapely.make_valid(candidate, method="structure", keep_collapsed=False)
            except TypeError:  # Shapely 2.0 compatibility
                candidate = shapely.make_valid(candidate)
        source_polygons.extend(_iter_polygons(candidate))

    if not source_polygons:
        raise ValueError("No valid closed planar region can be extruded.")

    extent = _geometry_extent(source_polygons)
    grid = float(precision_grid) if precision_grid is not None else max(1.0e-9, extent * 1.0e-10)
    # A precision model makes union/intersection vertices deterministic.  The
    # default ``valid_output`` mode also removes collapsed polygon fragments.
    precise = [shapely.set_precision(poly, grid, mode="valid_output") for poly in source_polygons]
    unioned = shapely.unary_union(precise, grid_size=grid)
    if not bool(getattr(unioned, "is_valid", False)):
        try:
            unioned = shapely.make_valid(unioned, method="structure", keep_collapsed=False)
        except TypeError:
            unioned = shapely.make_valid(unioned)
    polygon_parts = _iter_polygons(unioned)
    if not polygon_parts:
        raise ValueError("The planar regions collapse to no manufacturable area.")
    # Re-union only polygonal parts so GeometryCollection line remnants never
    # reach the solid constructor.
    footprint = shapely.unary_union(polygon_parts, grid_size=grid)
    polygon_parts = _iter_polygons(footprint)
    if not polygon_parts:
        raise ValueError("The normalized planar footprint contains no polygon.")

    # A formally valid 2D polygon may still contain a hole tangent to its outer
    # ring, two tangent holes, or two components touching at one point.  Those
    # zero-clearance contacts extrude to bow-tie vertices/edges and are rejected
    # by an oriented 2-manifold kernel.  Open only those contacts by a
    # sub-micrometre morphology pass; normal separated boundaries are untouched.
    contact_tolerance = max(grid * 1.5, extent * 1.0e-12)
    if _has_zero_clearance_contacts(polygon_parts, tolerance=contact_tolerance):
        cleanup = max(grid * 4.0, extent * 1.0e-9)
        footprint = footprint.buffer(-cleanup, join_style="mitre").buffer(cleanup, join_style="mitre")
        footprint = shapely.set_precision(footprint, grid, mode="valid_output")
        polygon_parts = _iter_polygons(footprint)
        if not polygon_parts:
            raise ValueError("Zero-clearance planar contacts collapse the complete footprint.")

        # A symmetric close/open pass can recreate an *exact* point contact when
        # a polygonal hole has a vertex on a straight exterior segment.  Shapely
        # still reports that polygon as valid, but extrusion creates one vertical
        # edge shared by four wall triangles.  This is the failure seen on heavily
        # edited Plan Tracer sketches containing microscopic polygonized slivers.
        #
        # If the first regularisation did not actually create clearance, keep a
        # microscopic net erosion instead of restoring the boundary all the way
        # back to the singular point.  ``cleanup`` is scale-relative (typically
        # around 1e-7 mm for a 100-300 mm drawing), so the dimensional change is
        # far below CAD/display precision while the topology becomes a genuine
        # oriented 2-manifold.
        if _has_zero_clearance_contacts(polygon_parts, tolerance=contact_tolerance):
            footprint = footprint.buffer(-cleanup, join_style="mitre")
            footprint = shapely.set_precision(footprint, grid, mode="valid_output")
            polygon_parts = _iter_polygons(footprint)
            if not polygon_parts:
                raise ValueError("Zero-clearance planar contacts collapse the complete footprint.")
            if _has_zero_clearance_contacts(polygon_parts, tolerance=contact_tolerance):
                raise ValueError("Zero-clearance planar contacts could not be regularized safely.")

    area = float(sum(float(poly.area) for poly in polygon_parts))
    if not math.isfinite(area) or area <= max(1.0e-12, grid * grid):
        raise ValueError("The normalized planar footprint has zero area.")
    return footprint, int(region_count), float(grid)


def _ring_area(points: Sequence[Point2]) -> float:
    return 0.5 * sum(
        float(points[index][0]) * float(points[(index + 1) % len(points)][1])
        - float(points[(index + 1) % len(points)][0]) * float(points[index][1])
        for index in range(len(points))
    )


def _oriented_ring(points: Sequence[Point2], *, positive: bool) -> list[Point2]:
    ring = list(_clean_ring(tuple(points)))
    if len(ring) < 3:
        return []
    if (_ring_area(ring) > 0.0) != bool(positive):
        ring.reverse()
    return ring


def _to_world(plane: Any, u: float, v: float, z: float) -> Point3:
    from laserprog_studio.planar_tools import plane_to_world

    base = plane_to_world(plane, float(u), float(v))
    normal = tuple(float(value) for value in plane.normal)
    return (
        float(base[0]) + normal[0] * float(z),
        float(base[1]) + normal[1] * float(z),
        float(base[2]) + normal[2] * float(z),
    )


def _signed_volume(vertices: Sequence[Point3], triangles: Sequence[Triangle]) -> float:
    volume = 0.0
    for ia, ib, ic in triangles:
        a, b, c = vertices[int(ia)], vertices[int(ib)], vertices[int(ic)]
        cross = (
            b[1] * c[2] - b[2] * c[1],
            b[2] * c[0] - b[0] * c[2],
            b[0] * c[1] - b[1] * c[0],
        )
        volume += (a[0] * cross[0] + a[1] * cross[1] + a[2] * cross[2]) / 6.0
    return float(volume)


def _edge_report(vertex_count: int, triangles: Sequence[Triangle]) -> tuple[int, int]:
    edges: Counter[tuple[int, int]] = Counter()
    for triangle in triangles:
        a, b, c = (int(triangle[0]), int(triangle[1]), int(triangle[2]))
        if min(a, b, c) < 0 or max(a, b, c) >= int(vertex_count):
            return (1, 1)
        for x, y in ((a, b), (b, c), (c, a)):
            if x == y:
                continue
            edges[(x, y) if x < y else (y, x)] += 1
    return (
        sum(1 for count in edges.values() if count == 1),
        sum(1 for count in edges.values() if count > 2),
    )



def _nonmanifold_vertex_count(vertex_count: int, triangles: Sequence[Triangle]) -> int:
    """Count vertices whose triangle link is not one connected cycle.

    Edge-use checks alone miss two closed shells that touch at one vertex.  The
    boolean kernel correctly rejects that bow-tie vertex, so the generator must
    detect it before committing the mesh.
    """

    incident: list[list[tuple[int, int]]] = [[] for _ in range(int(vertex_count))]
    for a, b, c in triangles:
        a, b, c = int(a), int(b), int(c)
        if min(a, b, c) < 0 or max(a, b, c) >= int(vertex_count):
            return 1
        incident[a].append((b, c))
        incident[b].append((c, a))
        incident[c].append((a, b))

    invalid = 0
    for links in incident:
        if not links:
            continue
        adjacency: dict[int, set[int]] = {}
        for left, right in links:
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
        if any(len(neighbours) != 2 for neighbours in adjacency.values()):
            invalid += 1
            continue
        start = next(iter(adjacency))
        stack = [start]
        visited: set[int] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacency[current] - visited)
        if len(visited) != len(adjacency):
            invalid += 1
    return int(invalid)



def _extrude_with_manifold(footprint: Any, *, plane: Any, depth: float, module: Any) -> tuple[list[Point3], list[Triangle], str]:
    contours: list[list[Point2]] = []
    for polygon in _iter_polygons(footprint):
        exterior = _oriented_ring(tuple(polygon.exterior.coords), positive=True)
        if exterior:
            contours.append(exterior)
        for interior in tuple(polygon.interiors):
            hole = _oriented_ring(tuple(interior.coords), positive=False)
            if hole:
                contours.append(hole)
    if not contours:
        raise ValueError("The normalized footprint contains no contour.")

    cross_section = module.CrossSection(contours)
    try:
        empty = bool(cross_section.is_empty())
    except Exception:
        empty = False
    if empty:
        raise ValueError("Manifold rejected the planar cross-section.")
    height = abs(float(depth))
    solid = cross_section.extrude(height)
    status = manifold_status_text(solid)
    if not manifold_is_valid(solid, module):
        raise ValueError(f"Manifold extrusion failed with status {status}.")
    to_mesh64 = getattr(solid, "to_mesh64", None)
    output = to_mesh64() if callable(to_mesh64) else solid.to_mesh()

    try:
        import numpy as np

        local_vertices = np.asarray(output.vert_properties, dtype=float)
        triangles_array = np.asarray(output.tri_verts, dtype=int)
        if local_vertices.ndim == 1:
            local_vertices = local_vertices.reshape((-1, 3))
        if triangles_array.ndim == 1:
            triangles_array = triangles_array.reshape((-1, 3))
        sign = 1.0 if float(depth) >= 0.0 else -1.0
        vertices = [_to_world(plane, row[0], row[1], row[2] * sign) for row in local_vertices[:, :3]]
        triangles = [tuple(int(value) for value in row[:3]) for row in triangles_array]
        if sign < 0.0:
            triangles = [(a, c, b) for a, b, c in triangles]
        return vertices, triangles, status
    except Exception as exc:
        raise ValueError("Cannot convert the Manifold extrusion to a WorkMesh.") from exc


def _triangle_area2(a: Point2, b: Point2, c: Point2) -> float:
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _extrude_indexed_fallback(footprint: Any, *, plane: Any, depth: float, grid: float) -> tuple[list[Point3], list[Triangle]]:
    """Build a closed indexed solid from cap topology.

    Side walls are derived from the *actual cap boundary edges*, not from a
    second copy of the source rings.  This prevents the historical Plan Tracer
    defect where cap triangulation simplified or noded a curved boundary while
    the wall builder kept the old segmentation, leaving open or >2-use edges.
    """

    try:
        from shapely import constrained_delaunay_triangles
    except Exception as exc:  # pragma: no cover - pinned production dependency
        raise RuntimeError("Constrained polygon triangulation is unavailable.") from exc

    vertices: list[Point3] = []
    triangles: list[Triangle] = []
    height = float(depth)
    for polygon in _iter_polygons(footprint):
        collection = constrained_delaunay_triangles(polygon)
        parts = tuple(getattr(collection, "geoms", ()))
        if not parts:
            raise ValueError("Cannot triangulate a normalized planar component.")

        local_points: list[Point2] = []
        local_index: dict[tuple[int, int], int] = {}
        cap_cells: list[Triangle] = []
        seen_cells: set[tuple[int, int, int]] = set()
        quant = max(float(grid), 1.0e-12)

        def point_index(point: Point2) -> int:
            key = (round(float(point[0]) / quant), round(float(point[1]) / quant))
            existing = local_index.get(key)
            if existing is not None:
                return existing
            index = len(local_points)
            local_points.append((float(point[0]), float(point[1])))
            local_index[key] = index
            return index

        cap_area = 0.0
        for triangle in parts:
            coords = _clean_ring(tuple(triangle.exterior.coords))
            if len(coords) != 3:
                continue
            area = _triangle_area2(coords[0], coords[1], coords[2])
            if abs(area) <= max(1.0e-18, grid * grid * 1.0e-4):
                continue
            indices = tuple(point_index(point) for point in coords)
            if len(set(indices)) != 3:
                continue
            if area < 0.0:
                indices = (indices[0], indices[2], indices[1])
                area = -area
            canonical = tuple(sorted(indices))
            if canonical in seen_cells:
                continue
            seen_cells.add(canonical)
            cap_cells.append((int(indices[0]), int(indices[1]), int(indices[2])))
            cap_area += float(area)

        expected_area = float(polygon.area)
        area_tolerance = max(expected_area * 1.0e-8, grid * grid * 16.0, 1.0e-10)
        if not cap_cells or abs(cap_area - expected_area) > area_tolerance:
            raise ValueError(
                "The cap triangulation does not cover the normalized footprint "
                f"(expected={expected_area:g}, triangles={cap_area:g})."
            )

        component_offset = len(vertices)
        bottom = [component_offset + index for index in range(len(local_points))]
        top = [component_offset + len(local_points) + index for index in range(len(local_points))]
        vertices.extend(_to_world(plane, point[0], point[1], 0.0) for point in local_points)
        vertices.extend(_to_world(plane, point[0], point[1], height) for point in local_points)

        boundary_counts: Counter[tuple[int, int]] = Counter()
        boundary_direction: dict[tuple[int, int], tuple[int, int]] = {}
        for a, b, c in cap_cells:
            triangles.append((bottom[c], bottom[b], bottom[a]))
            triangles.append((top[a], top[b], top[c]))
            for x, y in ((a, b), (b, c), (c, a)):
                key = (x, y) if x < y else (y, x)
                boundary_counts[key] += 1
                boundary_direction.setdefault(key, (x, y))

        for edge, count in boundary_counts.items():
            if count != 1:
                continue
            a, b = boundary_direction[edge]
            triangles.append((bottom[a], bottom[b], top[b]))
            triangles.append((bottom[a], top[b], top[a]))

    return vertices, triangles



def validate_boolean_ready_mesh(
    vertices: Sequence[Point3],
    triangles: Sequence[Triangle],
    *,
    weld_tolerance: float,
) -> tuple[int, int, int, float]:
    if not vertices or not triangles:
        raise ValueError("Boolean-ready solid generation produced an empty mesh.")
    boundary, nonmanifold = _edge_report(len(vertices), triangles)
    nonmanifold_vertices = _nonmanifold_vertex_count(len(vertices), triangles)
    if boundary or nonmanifold or nonmanifold_vertices:
        raise ValueError(
            "Boolean-ready solid generation produced invalid indexed topology "
            f"(boundary_edges={boundary}, nonmanifold_edges={nonmanifold}, "
            f"nonmanifold_vertices={nonmanifold_vertices})."
        )
    quant = max(float(weld_tolerance), 1.0e-12)
    remap: list[int] = []
    welded_keys: dict[tuple[int, int, int], int] = {}
    for point in vertices:
        key = tuple(round(float(component) / quant) for component in point)
        remap.append(welded_keys.setdefault(key, len(welded_keys)))
    welded_triangles = [(remap[a], remap[b], remap[c]) for a, b, c in triangles]
    welded_boundary, welded_nonmanifold = _edge_report(len(welded_keys), welded_triangles)
    welded_nonmanifold_vertices = _nonmanifold_vertex_count(len(welded_keys), welded_triangles)
    if welded_boundary or welded_nonmanifold or welded_nonmanifold_vertices:
        raise ValueError(
            "Boolean-ready solid generation contains coincident seams that become "
            "non-manifold when the boolean kernel welds vertices "
            f"(boundary_edges={welded_boundary}, nonmanifold_edges={welded_nonmanifold}, "
            f"nonmanifold_vertices={welded_nonmanifold_vertices})."
        )
    volume = _signed_volume(vertices, triangles)
    if not math.isfinite(volume) or abs(volume) <= 1.0e-12:
        raise ValueError("Boolean-ready solid generation produced zero signed volume.")
    return boundary, nonmanifold, nonmanifold_vertices, float(volume)


def extrude_planar_regions_boolean_ready(
    regions: Iterable[PlanarRegion],
    *,
    plane: Any,
    depth: float,
    name: str = "Planar extrusion",
    color: str = "#8BC34A",
    precision_grid: float | None = None,
) -> tuple[Any, BooleanReadySolidReport]:
    """Create a WorkMesh accepted by LaserProg's manifold boolean contract."""

    from laserprog_studio.domain.work_model import WorkMesh

    depth_value = float(depth)
    if not math.isfinite(depth_value) or abs(depth_value) <= 1.0e-9:
        raise ValueError("Extrusion depth must be non-zero.")
    footprint, input_regions, grid = build_valid_planar_footprint(regions, precision_grid=precision_grid)
    polygons = _iter_polygons(footprint)
    area = float(sum(float(poly.area) for poly in polygons))

    backend = "indexed_cap_boundary"
    manifold_status = "unavailable"
    vertices: list[Point3]
    triangles: list[Triangle]
    manifold_module: Any | None = None
    try:
        import manifold3d as manifold_module  # type: ignore
    except Exception:
        manifold_module = None

    if manifold_module is not None and hasattr(manifold_module, "CrossSection"):
        try:
            vertices, triangles, manifold_status = _extrude_with_manifold(
                footprint,
                plane=plane,
                depth=depth_value,
                module=manifold_module,
            )
            backend = "manifold_cross_section"
        except Exception:
            # Keep a deterministic fallback, but validate it again through
            # manifold3d below before returning it to the document.
            vertices, triangles = _extrude_indexed_fallback(
                footprint,
                plane=plane,
                depth=depth_value,
                grid=grid,
            )
            backend = "indexed_cap_boundary_after_manifold_failure"
    else:
        vertices, triangles = _extrude_indexed_fallback(
            footprint,
            plane=plane,
            depth=depth_value,
            grid=grid,
        )

    weld_tolerance = max(grid * 2.0, _geometry_extent(polygons) * 1.0e-10, 1.0e-9)
    boundary, nonmanifold, nonmanifold_vertices, volume = validate_boolean_ready_mesh(
        vertices,
        triangles,
        weld_tolerance=weld_tolerance,
    )
    if volume < 0.0:
        triangles = [(a, c, b) for a, b, c in triangles]
        volume = -volume

    # ``manifold_cross_section`` is already a native Manifold result.  Re-importing
    # its exported vertices through ``Mesh`` is both redundant and lossy: the
    # production Mesh path uses float32 positions, so a perfectly valid native
    # extrusion can become invalid after world-space conversion.  This was the
    # v122 regression that made Apply/Add silently do nothing on Windows.
    #
    # The indexed fallback still needs a native verification when the extension
    # is available.  API/ABI compatibility failures are recorded as diagnostics
    # rather than blocking a topologically valid local solid; an explicit native
    # ``NotManifold`` status remains a hard failure.
    native_verified = backend == "manifold_cross_section"
    if manifold_module is not None and not native_verified:
        try:
            import numpy as np

            construction = construct_manifold(
                manifold_module,
                triangles=np.asarray(triangles, dtype=np.uint32),
                vertices=np.asarray(vertices, dtype=np.float64),
                merge=True,
                prefer_64bit=True,
            )
            candidate = construction.manifold
            manifold_status = str(construction.status)
            if not manifold_is_valid(candidate, manifold_module):
                raise ValueError(
                    "The generated Plan Tracer solid is closed but the boolean "
                    f"kernel rejected it with status {manifold_status}."
                )
            native_verified = True
            backend += "+manifold_verified"
            # Canonicalize through the accepted native result.  This guarantees
            # the committed topology is exactly the one accepted by booleans.
            output_method = getattr(candidate, "to_mesh64", None)
            output = output_method() if callable(output_method) else candidate.to_mesh()
            local_vertices = np.asarray(output.vert_properties, dtype=float)
            local_triangles = np.asarray(output.tri_verts, dtype=int)
            if local_vertices.ndim == 1:
                local_vertices = local_vertices.reshape((-1, 3))
            if local_triangles.ndim == 1:
                local_triangles = local_triangles.reshape((-1, 3))
            vertices = [tuple(float(value) for value in row[:3]) for row in local_vertices]
            triangles = [tuple(int(value) for value in row[:3]) for row in local_triangles]
            boundary, nonmanifold, nonmanifold_vertices, volume = validate_boolean_ready_mesh(
                vertices,
                triangles,
                weld_tolerance=weld_tolerance,
            )
            if volume < 0.0:
                triangles = [(a, c, b) for a, b, c in triangles]
                volume = -volume
        except ValueError:
            raise
        except Exception as exc:
            # Do not turn an optional extension/API mismatch into a dead Apply
            # button.  The deterministic indexed topology has already passed the
            # strict closed-edge, vertex-link and welded-seam checks above.
            manifold_status = f"verification_unavailable:{type(exc).__name__}"
            backend += "+local_topology_verified"

    mesh = WorkMesh(
        name=str(name),
        vertices=[tuple(float(value) for value in point) for point in vertices],
        triangles=[tuple(int(value) for value in triangle) for triangle in triangles],
        color=str(color),
    )
    report = BooleanReadySolidReport(
        backend=backend,
        input_regions=int(input_regions),
        polygon_components=len(polygons),
        footprint_area=area,
        vertices=len(vertices),
        triangles=len(triangles),
        boundary_edges=int(boundary),
        nonmanifold_edges=int(nonmanifold),
        nonmanifold_vertices=int(nonmanifold_vertices),
        signed_volume=float(volume),
        precision_grid=float(grid),
        manifold_status=str(manifold_status),
        native_verified=bool(native_verified),
    )
    return mesh, report


__all__ = [
    "BooleanReadySolidReport",
    "PlanarRegion",
    "build_valid_planar_footprint",
    "extrude_planar_regions_boolean_ready",
    "validate_boolean_ready_mesh",
]
