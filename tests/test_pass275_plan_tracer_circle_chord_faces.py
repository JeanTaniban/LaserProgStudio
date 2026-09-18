from __future__ import annotations

from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument


def _rect(sketch: SketchDocument, x0: float, y0: float, x1: float, y1: float) -> None:
    for point_id, xy in {
        "ra": (x0, y0),
        "rb": (x1, y0),
        "rc": (x1, y1),
        "rd": (x0, y1),
    }.items():
        sketch.add_point(xy, point_id=point_id)
    for line_id, a, b in (
        ("rab", "ra", "rb"),
        ("rbc", "rb", "rc"),
        ("rcd", "rc", "rd"),
        ("rda", "rd", "ra"),
    ):
        sketch.add_line(a, b, line_id=line_id)


def test_circle_crossed_by_rectangle_edge_creates_chorded_circle_regions_without_splitting_circle() -> None:
    sketch = SketchDocument()
    _rect(sketch, 0.0, 0.0, 100.0, 100.0)
    sketch.add_point((50.0, 90.0), point_id="center")
    sketch.add_point((70.0, 90.0), point_id="radius")
    sketch.add_circle("center", "radius", circle_id="circle")

    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )

    chorded = [face for face in sketch.faces.values() if {"circle", "rcd"}.issubset(set(face.boundary_entity_ids))]
    assert len(chorded) >= 2
    assert "circle" in sketch.circles
    assert not sketch.arcs


def test_circle_inside_rectangle_still_builds_inner_island_and_outer_hole() -> None:
    sketch = SketchDocument()
    _rect(sketch, 0.0, 0.0, 100.0, 100.0)
    sketch.add_point((50.0, 50.0), point_id="center")
    sketch.add_point((65.0, 50.0), point_id="radius")
    sketch.add_circle("center", "radius", circle_id="circle")

    sketch.compile(SketchCompileOptions(split_curve_intersections=False, split_curves_at_vertices=False, solve_faces=True))

    assert any(face.hole_polygons for face in sketch.faces.values())
    assert any(set(face.boundary_entity_ids) == {"circle"} for face in sketch.faces.values())
