from __future__ import annotations

import pytest

from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.sketch.arrangement_faces import ArrangementFaceOptions, solve_faces_from_arrangement


LIVE_OPTIONS = SketchCompileOptions(
    merge_tolerance=1.0e-5,
    split_tolerance=1.0e-5,
    solve_faces=True,
    split_curve_intersections=False,
    split_curves_at_vertices=False,
)


def _rectangle(sketch: SketchDocument, *, x0: float = 0.0, y0: float = 0.0, x1: float = 100.0, y1: float = 100.0) -> None:
    for point_id, xy in {
        "ra": (x0, y0),
        "rb": (x1, y0),
        "rc": (x1, y1),
        "rd": (x0, y1),
    }.items():
        sketch.add_point(xy, point_id=point_id)
    for line_id, start, end in (
        ("rab", "ra", "rb"),
        ("rbc", "rb", "rc"),
        ("rcd", "rc", "rd"),
        ("rda", "rd", "ra"),
    ):
        sketch.add_line(start, end, line_id=line_id)


def _crossing_circle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    _rectangle(sketch)
    sketch.add_point((50.0, 90.0), point_id="center")
    sketch.add_point((70.0, 90.0), point_id="radius")
    sketch.add_circle("center", "radius", circle_id="circle")
    return sketch


def _polygons(sketch: SketchDocument):
    geometry = pytest.importorskip("shapely.geometry")
    return [geometry.Polygon(face.polygon_points, holes=list(face.hole_polygons)) for face in sketch.faces.values()]


def test_arrangement_solver_is_reachable_and_marks_generated_cells() -> None:
    sketch = _crossing_circle_sketch()

    created = solve_faces_from_arrangement(
        sketch,
        ArrangementFaceOptions(join_tolerance=1.0e-5),
    )

    assert len(created) == 3
    assert len(sketch.faces) == 3
    assert all(face.metadata.get("arrangement_solver") == "shapely_polygonize" for face in sketch.faces.values())


def test_live_plan_tracer_compile_partitions_circle_crossing_rectangle_into_selectable_cells() -> None:
    sketch = _crossing_circle_sketch()

    result = sketch.compile(LIVE_OPTIONS)

    assert not result.notes
    assert "circle" in sketch.circles
    assert not sketch.arcs
    assert len(sketch.faces) == 3
    assert sum(1 for face in sketch.faces.values() if {"circle", "rcd"}.issubset(face.boundary_entity_ids)) == 3

    polygons = _polygons(sketch)
    for index, first in enumerate(polygons):
        assert first.is_valid
        assert first.area > 1.0e-4
        for second in polygons[index + 1 :]:
            assert first.intersection(second).area <= 1.0e-5


def test_deleting_one_circle_rectangle_region_suppresses_only_that_cell() -> None:
    sketch = _crossing_circle_sketch()
    sketch.compile(LIVE_OPTIONS)
    geometry = pytest.importorskip("shapely.geometry")

    # Select the overlap cell inside both the rectangle and the circle.  It is
    # larger than the exterior circular cap but smaller than the remaining
    # rectangle region.
    candidates = [
        (geometry.Polygon(face.polygon_points, holes=list(face.hole_polygons)).area, face)
        for face in sketch.faces.values()
        if {"circle", "rcd"}.issubset(face.boundary_entity_ids)
    ]
    candidates.sort(key=lambda item: item[0])
    overlap = candidates[1][1]
    deleted_signature = str(overlap.metadata["signature"])

    sketch.delete_face_only(overlap.id, compile_after=False)
    sketch.compile(LIVE_OPTIONS)

    assert deleted_signature in sketch.suppressed_face_signatures
    assert "circle" in sketch.circles
    assert not sketch.arcs
    assert len(sketch.faces) == 2
    assert all(face.metadata.get("signature") != deleted_signature for face in sketch.faces.values())
