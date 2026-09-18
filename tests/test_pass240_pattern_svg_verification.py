from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tooling.plan_trace_2d.patterns import PATTERN_KIND_CHOICES
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec


def _plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )


def _rectangle_sketch(width: float = 120.0, height: float = 80.0) -> SketchDocument:
    sketch = SketchDocument()
    point_ids = [sketch.add_point(point).id for point in ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))]
    for start, end in zip(point_ids, point_ids[1:] + point_ids[:1]):
        sketch.add_line(start, end)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    return sketch


@pytest.mark.parametrize("kind", [kind for kind, _label in PATTERN_KIND_CHOICES])
def test_pass240_zero_margin_pattern_openings_are_valid_and_bounded(kind: str) -> None:
    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch()
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    outer = Polygon(face.polygon_points)

    holes = tool._services.patterns._valid_hole_polygons_for_face(
        face,
        kind=kind,
        cell_size=14.0,
        wall=2.0,
        margin=0.0,
        angle=17.0,
        aspect=1.7,
        seed=3,
        max_segments=50000,
        ignore_existing_pattern_holes=True,
    )

    assert holes, f"motif {kind!r} produced no openings at zero margin"
    for ring in holes:
        poly = Polygon(ring)
        assert poly.is_valid, f"motif {kind!r} produced invalid opening {ring!r}"
        assert poly.area > 1.0e-8
        assert outer.covers(poly), f"motif {kind!r} escaped the selected face"


def test_pass240_legacy_keep_form_off_stays_face_owned_and_builds_exportable_mesh_after_compile() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _rectangle_sketch(120.0, 80.0)
    face_ids = tuple(tool._state.sketch.faces)

    ok = tool._services.patterns.apply_as_union_face_holes(
        ctx,
        face_ids,
        kind="honeycomb",
        cell_size=18.0,
        wall=3.0,
        margin=0.0,
        angle=11.0,
        aspect=1.0,
        seed=4,
        keep_form=False,
        max_segments=50000,
        persistent=True,
        render=False,
    )

    assert ok is True
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
    mesh = tool._build_apply_mesh()
    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0
    assert all(len(triangle) == 3 for triangle in mesh.triangles)
