from __future__ import annotations

import pytest

from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument


def _rect(sketch: SketchDocument, prefix: str, x0: float, y0: float, x1: float, y1: float) -> None:
    point_ids = (f"{prefix}a", f"{prefix}b", f"{prefix}c", f"{prefix}d")
    for point_id, xy in zip(point_ids, ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
        sketch.add_point(xy, point_id=point_id)
    for line_id, a, b in (
        (f"{prefix}ab", point_ids[0], point_ids[1]),
        (f"{prefix}bc", point_ids[1], point_ids[2]),
        (f"{prefix}cd", point_ids[2], point_ids[3]),
        (f"{prefix}da", point_ids[3], point_ids[0]),
    ):
        sketch.add_line(a, b, line_id=line_id)


def _compile_live(sketch: SketchDocument) -> None:
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )


def _face_polygons(sketch: SketchDocument):
    shapely = pytest.importorskip("shapely.geometry")
    Polygon = shapely.Polygon
    return [Polygon(face.polygon_points, holes=list(face.hole_polygons)) for face in sketch.faces.values()]


def _assert_non_overlapping_faces(sketch: SketchDocument) -> None:
    polygons = _face_polygons(sketch)
    for index, first in enumerate(polygons):
        assert first.is_valid
        for second in polygons[index + 1 :]:
            assert second.is_valid
            assert first.intersection(second).area <= 1.0e-5


def test_arrangement_solver_partitions_circle_crossed_by_multiple_lines_without_splitting_user_circle() -> None:
    sketch = SketchDocument()
    sketch.add_point((0.0, 0.0), point_id="center")
    sketch.add_point((20.0, 0.0), point_id="radius")
    sketch.add_circle("center", "radius", circle_id="circle")
    for point_id, xy in {
        "ha": (-30.0, 0.0),
        "hb": (30.0, 0.0),
        "va": (0.0, -30.0),
        "vb": (0.0, 30.0),
    }.items():
        sketch.add_point(xy, point_id=point_id)
    sketch.add_line("ha", "hb", line_id="horizontal")
    sketch.add_line("va", "vb", line_id="vertical")

    _compile_live(sketch)

    circle_cells = [face for face in sketch.faces.values() if "circle" in face.boundary_entity_ids]
    assert len(circle_cells) == 4
    assert "circle" in sketch.circles
    assert not sketch.arcs
    _assert_non_overlapping_faces(sketch)


def test_arrangement_solver_partitions_rectangle_circle_line_combo_as_non_overlapping_cells() -> None:
    sketch = SketchDocument()
    _rect(sketch, "outer", 0.0, 0.0, 120.0, 120.0)
    _rect(sketch, "inner", 28.0, 36.0, 72.0, 82.0)
    sketch.add_point((82.0, 45.0), point_id="circle_center")
    sketch.add_point((106.0, 45.0), point_id="circle_radius")
    sketch.add_circle("circle_center", "circle_radius", circle_id="circle")
    sketch.add_point((70.0, -8.0), point_id="cut_a")
    sketch.add_point((92.0, 126.0), point_id="cut_b")
    sketch.add_line("cut_a", "cut_b", line_id="slanted_cut")

    _compile_live(sketch)

    assert "circle" in sketch.circles
    assert not sketch.arcs
    circle_faces = [face for face in sketch.faces.values() if "circle" in face.boundary_entity_ids]
    assert len(circle_faces) >= 4
    assert len(sketch.faces) >= 6
    _assert_non_overlapping_faces(sketch)


def test_arrangement_solver_partitions_circle_crossing_rectangle_edge_symmetrically() -> None:
    sketch = SketchDocument()
    _rect(sketch, "box", 0.0, 0.0, 100.0, 70.0)
    sketch.add_point((100.0, 35.0), point_id="circle_center")
    sketch.add_point((125.0, 35.0), point_id="circle_radius")
    sketch.add_circle("circle_center", "circle_radius", circle_id="circle")

    _compile_live(sketch)

    crossing_cells = [face for face in sketch.faces.values() if "circle" in face.boundary_entity_ids and len(face.boundary_entity_ids) >= 2]
    assert len(crossing_cells) >= 2
    assert len(sketch.faces) >= 3
    _assert_non_overlapping_faces(sketch)
