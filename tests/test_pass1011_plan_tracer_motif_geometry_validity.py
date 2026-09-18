# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from _path_setup import ROOT  # noqa: F401
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


BROKEN_BY_REPORT = [
    "triangle",
    "brick",
    "rings",
    "grid",
    "wave",
    "hinge_straight",
    "hinge_lattice",
    "hinge_wave",
]


def _right_triangle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 120.0)).id
    p2 = sketch.add_point((120.0, 120.0)).id
    p3 = sketch.add_point((120.0, 0.0)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p1)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    return sketch


@pytest.mark.parametrize("kind", BROKEN_BY_REPORT)
def test_pass1011_reported_motifs_generate_valid_closed_interior_holes(kind: str) -> None:
    """Regression for malformed vertices / non-closing motif faces.

    Slot-style motifs may be clipped to a triangular face, but the resulting
    rings still have to be valid *interior* hole polygons.  A hole touching the
    outer boundary is invalid for Plan Tracer's face representation and used to
    produce the broken screenshots.
    """

    tool = PlanTrace2DCreatorTool()
    sketch = _right_triangle_sketch()
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    outer = Polygon(face.polygon_points)

    holes = tool._services.patterns._valid_hole_polygons_for_face(
        face,
        kind=kind,
        cell_size=14.0,
        wall=2.0,
        margin=3.0,
        angle=0.0,
        aspect=1.0,
        seed=11,
        max_segments=12000,
        ignore_existing_pattern_holes=True,
    )

    assert holes, f"{kind} did not generate any holes"
    for hole in holes:
        poly = Polygon(hole)
        assert poly.is_valid, f"{kind} produced invalid polygon {hole!r}"
        assert poly.area > 1.0e-6
        assert outer.covers(poly)
        assert not poly.boundary.intersects(outer.boundary), (
            f"{kind} produced a hole touching the face boundary"
        )
