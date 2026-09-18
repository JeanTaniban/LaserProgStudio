from __future__ import annotations

from types import SimpleNamespace
import sys

from shapely.geometry import Point, box

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.geometry_ops.planar_boolean_solid import (
    extrude_planar_regions_boolean_ready,
    validate_boolean_ready_mesh,
)
from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _coords(geometry):
    return tuple((float(x), float(y)) for x, y, *_rest in geometry.coords)


def test_dense_rounded_footprint_with_tangent_hole_is_boolean_ready() -> None:
    outer = Point(0.0, 0.0).buffer(50.0, quad_segs=64)
    holes = []
    for y in range(-40, 41, 10):
        for x in range(-40, 41, 10):
            hole = Point(float(x), float(y)).buffer(2.0, quad_segs=8)
            if outer.covers(hole):
                holes.append(_coords(hole.exterior))
    # A tangent hole is a valid Shapely polygon but extrudes to a bow-tie seam
    # unless the zero-clearance contact is regularized first.
    holes.append(_coords(Point(48.0, 0.0).buffer(2.0, quad_segs=8).exterior))

    mesh, report = extrude_planar_regions_boolean_ready(
        [(_coords(outer.exterior), holes)],
        plane=make_locked_plane("top"),
        depth=3.0,
    )

    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)
    assert report.nonmanifold_vertices == 0
    assert report.signed_volume > 0.0
    validate_boolean_ready_mesh(mesh.vertices, mesh.triangles, weld_tolerance=1.0e-7)


def test_polygonal_tangent_hole_vertex_is_regularized_before_extrusion() -> None:
    # A polygonal hole touching a straight exterior edge at exactly one vertex
    # survives a symmetric buffer(-d).buffer(+d) round-trip.  Extruding that
    # formally-valid 2D polygon creates a vertical edge with four incident wall
    # triangles.  Plan Tracer must keep a microscopic clearance instead.
    outer = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    tangent_hole = ((50.0, 0.0), (49.0, 10.0), (51.0, 10.0))

    mesh, report = extrude_planar_regions_boolean_ready(
        [(outer, (tangent_hole,))],
        plane=make_locked_plane("top"),
        depth=3.0,
    )

    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)
    assert report.nonmanifold_edges == 0
    assert report.nonmanifold_vertices == 0
    validate_boolean_ready_mesh(mesh.vertices, mesh.triangles, weld_tolerance=1.0e-7)


def test_adjacent_planar_regions_are_unioned_without_internal_wall() -> None:
    regions = [
        (((0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)), ()),
        (((20.0, 0.0), (40.0, 0.0), (40.0, 20.0), (20.0, 20.0)), ()),
    ]

    mesh, report = extrude_planar_regions_boolean_ready(
        regions,
        plane=make_locked_plane("top"),
        depth=4.0,
    )

    assert report.polygon_components == 1
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)
    internal_walls = 0
    for triangle in mesh.triangles:
        points = [mesh.vertices[index] for index in triangle]
        if all(abs(point[0] - 20.0) <= 1.0e-8 for point in points):
            if max(point[2] for point in points) - min(point[2] for point in points) > 1.0e-8:
                internal_walls += 1
    assert internal_walls == 0


def test_boolean_ready_validator_rejects_two_shells_touching_at_one_vertex() -> None:
    # Two tetrahedra are independently closed but share one geometric vertex.
    # A pure edge-count check misses this; the welded vertex link has two cycles.
    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, -1.0),
    ]
    triangles = [
        (0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3),
        (4, 5, 6), (4, 7, 5), (5, 7, 6), (6, 7, 4),
    ]

    try:
        validate_boolean_ready_mesh(vertices, triangles, weld_tolerance=1.0e-8)
    except ValueError as exc:
        assert "nonmanifold_vertices" in str(exc)
    else:  # pragma: no cover - explicit failure message
        raise AssertionError("a point-touching solid group must be rejected")


class _FakeMesh:
    def __init__(self, *, tri_verts, vert_properties):
        self.tri_verts = tri_verts
        self.vert_properties = vert_properties

    def merge(self):
        return False


class _FakeManifold:
    def __init__(self, _mesh=None):
        self._mesh = _mesh

    def status(self):
        return _FakeError.NoError

    def is_empty(self):
        return False


class _FakeSolid(_FakeManifold):
    def to_mesh(self):
        return SimpleNamespace(
            vert_properties=[
                (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0), (1.0, 0.0, 1.0),
                (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
            ],
            tri_verts=[
                (0, 2, 1), (0, 3, 2),
                (4, 5, 6), (4, 6, 7),
                (0, 1, 5), (0, 5, 4),
                (1, 2, 6), (1, 6, 5),
                (2, 3, 7), (2, 7, 6),
                (3, 0, 4), (3, 4, 7),
            ],
        )


class _FakeCrossSection:
    last_contours = None

    def __init__(self, contours):
        type(self).last_contours = contours

    def is_empty(self):
        return False

    def extrude(self, _height):
        return _FakeSolid()


class _FakeError:
    NoError = "NoError"


def test_generator_prefers_same_manifold_cross_section_kernel_as_booleans(monkeypatch) -> None:
    fake_module = SimpleNamespace(
        CrossSection=_FakeCrossSection,
        Mesh=_FakeMesh,
        Manifold=_FakeManifold,
        Error=_FakeError,
    )
    monkeypatch.setitem(sys.modules, "manifold3d", fake_module)

    mesh, report = extrude_planar_regions_boolean_ready(
        [(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), ())],
        plane=make_locked_plane("top"),
        depth=1.0,
    )

    assert report.backend.startswith("manifold_cross_section")
    assert _FakeCrossSection.last_contours
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)


def _rectangle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    points = [
        sketch.add_point((0.0, 0.0)).id,
        sketch.add_point((30.0, 0.0)).id,
        sketch.add_point((30.0, 20.0)).id,
        sketch.add_point((0.0, 20.0)).id,
    ]
    for first, second in zip(points, points[1:] + points[:1]):
        sketch.add_line(first, second)
    sketch.compile(SketchCompileOptions(solve_faces=True))
    return sketch


def test_plan_tracer_marks_committed_output_with_boolean_contract_metadata() -> None:
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = make_locked_plane("top")
    tool._state.sketch = _rectangle_sketch()
    tool._state.extrusion_depth = 3.0

    mesh = tool._build_apply_mesh()

    assert mesh.metadata["boolean_ready"] is True
    assert mesh.metadata["boolean_ready_boundary_edges"] == 0
    assert mesh.metadata["boolean_ready_nonmanifold_edges"] == 0
    assert mesh.metadata["boolean_ready_nonmanifold_vertices"] == 0
    assert mesh.metadata["boolean_ready_backend"]
