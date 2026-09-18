from __future__ import annotations

import math
import time
from types import SimpleNamespace

from shapely.geometry import Polygon

from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _rounded_rectangle_points(
    *,
    width: float = 400.0,
    height: float = 250.0,
    radius: float = 70.0,
    samples_per_corner: int = 512,
) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    corners = (
        (width - radius, radius, -90.0),
        (width - radius, height - radius, 0.0),
        (radius, height - radius, 90.0),
        (radius, radius, 180.0),
    )
    for cx, cy, start_degrees in corners:
        for index in range(samples_per_corner):
            angle = math.radians(start_degrees + 90.0 * index / samples_per_corner)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return tuple(points)


def _rectangle_sketch(width: float = 120.0, height: float = 80.0) -> SketchDocument:
    sketch = SketchDocument()
    point_ids = [
        sketch.add_point(point).id
        for point in ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    ]
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


def test_zero_margin_on_dense_rounded_face_stays_interactive() -> None:
    """Regression: edge margin 0 must not intersect every pattern cell."""

    outer_points = _rounded_rectangle_points()
    face = SimpleNamespace(
        id="rounded-face",
        polygon_points=outer_points,
        hole_polygons=(),
        metadata={},
    )
    tool = PlanTrace2DCreatorTool()

    started = time.perf_counter()
    holes = tool._services.patterns._valid_hole_polygons_for_face(
        face,
        kind="square",
        cell_size=4.0,
        wall=0.5,
        margin=0.0,
        angle=13.0,
        aspect=1.5,
        seed=3,
        max_segments=120_000,
        ignore_existing_pattern_holes=True,
    )
    elapsed = time.perf_counter() - started

    assert holes
    # The previous all-cell intersection path took several seconds on this
    # fixture before actor synchronization.  Keep generous CI headroom while
    # still detecting a return to the blocking algorithm.
    assert elapsed < 3.0, f"zero-margin rounded-face clipping took {elapsed:.2f}s"
    outer = Polygon(outer_points).buffer(1.0e-8)
    assert all(outer.covers(Polygon(ring)) for ring in holes)


def test_single_face_pattern_does_not_reclip_every_generated_opening(monkeypatch) -> None:
    """A motif already clipped to one face must not be intersected a second time."""

    tool = PlanTrace2DCreatorTool()
    tool._state.sketch = _rectangle_sketch()
    face_id = next(iter(tool._state.sketch.faces))

    def _unexpected_split(*_args, **_kwargs):
        raise AssertionError("single-face motif unexpectedly entered union split clipping")

    monkeypatch.setattr(tool._services.patterns, "_split_union_holes_by_face", _unexpected_split)

    ok = tool._services.patterns.apply_as_union_face_holes(
        ToolContext(),
        (face_id,),
        kind="square",
        cell_size=14.0,
        wall=2.0,
        margin=0.0,
        angle=17.0,
        aspect=1.0,
        seed=3,
        keep_form=True,
        max_segments=50_000,
        persistent=False,
        render=False,
    )

    assert ok is True
    assert tool._state.pattern_generated_count > 0
