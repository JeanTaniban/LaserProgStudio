# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.gizmo_catalog_benchmark import BenchmarkCase, build_case_primitives
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool


class _Camera:
    def GetPosition(self):
        return (120.0, -90.0, 80.0)

    def GetFocalPoint(self):
        return (12.0, 34.0, 56.0)

    def GetParallelProjection(self):
        return False

    def GetParallelScale(self):
        return 50.0

    def GetViewAngle(self):
        return 30.0


class _Renderer:
    def GetActiveCamera(self):
        return _Camera()


class _Plotter:
    renderer = _Renderer()
    camera = None


def _all_positions(primitives):
    for primitive in primitives:
        if hasattr(primitive, "position"):
            yield primitive.position
        elif hasattr(primitive, "positions"):
            yield from primitive.positions
        elif hasattr(primitive, "points"):
            yield from primitive.points
        elif hasattr(primitive, "segments"):
            for segment in primitive.segments:
                yield from segment
        elif hasattr(primitive, "vertices"):
            yield from primitive.vertices
        elif hasattr(primitive, "polygons"):
            for polygon in primitive.polygons:
                yield from polygon


def _element_count(primitives, family: str) -> int:
    if family == "points":
        return sum(len(getattr(item, "positions", ())) or int(hasattr(item, "position")) for item in primitives)
    if family == "lines":
        return sum(len(getattr(item, "segments", ())) or int(hasattr(item, "points")) for item in primitives)
    if family == "faces":
        return sum(len(getattr(item, "polygons", ())) or int(hasattr(item, "vertices")) for item in primitives)
    return sum(
        len(getattr(item, "positions", ()))
        + len(getattr(item, "segments", ()))
        + len(getattr(item, "polygons", ()))
        + int(hasattr(item, "position"))
        + int(hasattr(item, "points"))
        + int(hasattr(item, "vertices"))
        for item in primitives
    )


def test_catalog_ground_frame_uses_world_xy_and_discards_camera_focal_z() -> None:
    ctx = ToolContext(owner=SimpleNamespace(plotter=_Plotter()))
    origin, unit = GizmoCatalogCreatorTool._ground_frame(ctx)

    assert origin == (12.0, 34.0, 0.0)
    assert unit > 0.0


def test_benchmark_datasets_are_flat_on_ground_and_have_requested_counts() -> None:
    origin = (10.0, 20.0, 0.0)
    for case in (
        BenchmarkCase("points", "points", 30),
        BenchmarkCase("lines", "lines", 30),
        BenchmarkCase("faces", "faces", 30),
        BenchmarkCase("mixed", "mixed", 30),
        BenchmarkCase("styles", "points", 30, style_count=8),
    ):
        primitives = build_case_primitives(draw2d, case, origin, 1.5)
        assert _element_count(primitives, case.family) == case.count
        assert all(position[2] == 0.0 for position in _all_positions(primitives))


def test_catalog_panel_exposes_scenario_enum_and_manual_benchmarks() -> None:
    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)

    field_ids = set(ctx.inspector.panel.field_ids())
    assert {"catalog_test", "benchmark_report", "benchmark_file", "catalog_actions", "benchmark_actions"} <= field_ids
    action = next(field for field in ctx.inspector.panel.fields() if field.id == "benchmark_actions")
    button_ids = {button_id for button_id, _label in action.choices}
    assert {"benchmark_selected", "benchmark_all", "benchmark_cancel"} <= button_ids
    assert "Idle" in str(ctx.inspector.value("benchmark_report"))


def test_visible_benchmark_uses_explicit_show_measure_clear_holds_and_dense_cases() -> None:
    from laserprog_studio.tooling.gizmo_catalog_benchmark import BENCHMARK_CASES, ProjectedDrawingBenchmarkRunner

    assert ProjectedDrawingBenchmarkRunner.SHOW_HOLD_MS >= 400
    assert ProjectedDrawingBenchmarkRunner.AFTER_MEASURE_HOLD_MS > 0
    assert ProjectedDrawingBenchmarkRunner.EMPTY_HOLD_MS > 0
    assert ProjectedDrawingBenchmarkRunner.MEASURE_GAP_MS > 0
    names = {case.name for case in BENCHMARK_CASES}
    assert {"points_50", "points_10000", "concave_face_256_vertices", "convex_face_2000_vertices"} <= names


def test_large_benchmark_cases_use_packed_public_primitives() -> None:
    from laserprog_studio.tool_api.projected_drawing import ProjectedFaceBatch, ProjectedPointCloud, ProjectedSegmentBatch

    origin = (0.0, 0.0, 0.0)
    points = build_case_primitives(draw2d, BenchmarkCase("p", "points", 1000), origin, 1.0)
    lines = build_case_primitives(draw2d, BenchmarkCase("l", "lines", 1000), origin, 1.0)
    faces = build_case_primitives(draw2d, BenchmarkCase("f", "faces", 300), origin, 1.0)

    assert len(points) == 1 and isinstance(points[0], ProjectedPointCloud)
    assert len(lines) == 1 and isinstance(lines[0], ProjectedSegmentBatch)
    assert len(faces) == 1 and isinstance(faces[0], ProjectedFaceBatch)
