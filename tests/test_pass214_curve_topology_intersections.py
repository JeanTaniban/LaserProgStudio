from __future__ import annotations

from laserprog_studio.tool_api import snap
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.snap import SnapKind, SnapSource


def test_point_on_arc_splits_arc_into_topological_arc_edges() -> None:
    sketch = SketchDocument()
    s = sketch.add_point((0.0, 0.0), point_id="s")
    e = sketch.add_point((10.0, 0.0), point_id="e")
    c = sketch.add_point((5.0, 5.0), point_id="c")
    p = sketch.add_point((8.5355339059, 3.5355339059), point_id="p_on_arc")
    sketch.add_arc(s.id, e.id, c.id, arc_id="arc")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=False))

    assert result.split_arcs == 1
    assert "arc" not in sketch.arcs
    assert len(sketch.arcs) == 2
    assert all("p_on_arc" in {arc.start_point_id, arc.end_point_id} for arc in sketch.arcs.values())
    assert any(point.metadata.get("hidden_control") for point in sketch.points.values())


def test_line_circle_intersection_splits_line_and_circle_into_arcs() -> None:
    sketch = SketchDocument()
    center = sketch.add_point((0.0, 0.0), point_id="center")
    radius = sketch.add_point((10.0, 0.0), point_id="radius")
    a = sketch.add_point((-15.0, 0.0), point_id="a")
    b = sketch.add_point((15.0, 0.0), point_id="b")
    sketch.add_circle(center.id, radius.id, circle_id="circle")
    sketch.add_line(a.id, b.id, line_id="line")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=False))

    assert result.curve_intersection_points == 1  # the +X hit reused the radius point
    assert result.split_lines == 1
    assert result.split_circles == 1
    assert "circle" not in sketch.circles
    assert len(sketch.lines) == 4  # also split at the existing circle-center point on the chord
    assert len(sketch.arcs) == 2
    assert any(abs(point.position[0] + 10.0) <= 1.0e-6 and abs(point.position[1]) <= 1.0e-6 for point in sketch.points.values())


def test_line_arc_intersection_splits_line_and_arc_even_at_arc_control_point() -> None:
    sketch = SketchDocument()
    s = sketch.add_point((0.0, 0.0), point_id="s")
    e = sketch.add_point((10.0, 0.0), point_id="e")
    c = sketch.add_point((5.0, 5.0), point_id="control")
    a = sketch.add_point((5.0, -2.0), point_id="a")
    b = sketch.add_point((5.0, 8.0), point_id="b")
    sketch.add_arc(s.id, e.id, c.id, arc_id="arc")
    sketch.add_line(a.id, b.id, line_id="line")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=False))

    assert result.split_lines == 1
    assert result.split_arcs == 1
    assert len(sketch.lines) == 2
    assert len(sketch.arcs) == 2
    assert all("control" in {arc.start_point_id, arc.end_point_id} for arc in sketch.arcs.values())


def test_circle_circle_intersections_split_both_circles() -> None:
    sketch = SketchDocument()
    c1 = sketch.add_point((0.0, 0.0), point_id="c1")
    r1 = sketch.add_point((5.0, 0.0), point_id="r1")
    c2 = sketch.add_point((6.0, 0.0), point_id="c2")
    r2 = sketch.add_point((11.0, 0.0), point_id="r2")
    sketch.add_circle(c1.id, r1.id, circle_id="circle1")
    sketch.add_circle(c2.id, r2.id, circle_id="circle2")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=False))

    assert result.curve_intersection_points == 2
    assert result.split_circles == 2
    assert not sketch.circles
    assert len(sketch.arcs) >= 4



def test_rebuild_faces_uses_curve_chord_regions_after_circle_split() -> None:
    sketch = SketchDocument()
    center = sketch.add_point((0.0, 0.0), point_id="center")
    radius = sketch.add_point((10.0, 0.0), point_id="radius")
    a = sketch.add_point((-15.0, 0.0), point_id="a")
    b = sketch.add_point((15.0, 0.0), point_id="b")
    sketch.add_circle(center.id, radius.id, circle_id="circle")
    sketch.add_line(a.id, b.id, line_id="line")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=True))

    assert result.rebuilt_faces == 2
    assert len(sketch.faces) == 2
    assert all(any(edge_id in sketch.arcs for edge_id in face.boundary_entity_ids) for face in sketch.faces.values())
    assert all(any(edge_id in sketch.lines for edge_id in face.boundary_entity_ids) for face in sketch.faces.values())
    assert all(not face.hole_polygons for face in sketch.faces.values())

def test_arc_arc_intersection_creates_snap_candidate() -> None:
    ctx = ToolContext()
    target_a = snap.arc(
        "arc.a",
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (5.0, 5.0, 0.0),
        source=SnapSource.CUSTOM_CURVE,
        priority=60,
    )
    target_b = snap.arc(
        "arc.b",
        (0.0, 5.0, 0.0),
        (10.0, 5.0, 0.0),
        (5.0, 0.0, 0.0),
        source=SnapSource.CUSTOM_CURVE,
        priority=60,
    )

    result = ctx.snap.smart((5.0, 2.5, 0.0), (5.0, 2.5), ctx, extra_targets=[target_a, target_b])

    assert result.snapped is True
    assert result.kind == SnapKind.INTERSECTION
    assert result.metadata["intersection_type"] == "arc_arc"


def test_line_circle_snap_returns_exact_intersection_kind() -> None:
    ctx = ToolContext()
    result = ctx.snap.smart(
        (-10.0, 0.0, 0.0),
        (-10.0, 0.0),
        ctx,
        extra_targets=[
            snap.segment("line", (-15.0, 0.0, 0.0), (15.0, 0.0, 0.0), source=SnapSource.CUSTOM_EDGE, priority=70),
            snap.circle("circle", (0.0, 0.0, 0.0), 10.0, source=SnapSource.CUSTOM_CURVE, priority=70),
        ],
    )

    assert result.snapped is True
    assert result.kind == SnapKind.INTERSECTION
    assert result.metadata["intersection_type"] == "line_circle"
    assert result.position == (-10.0, 0.0, 0.0)
