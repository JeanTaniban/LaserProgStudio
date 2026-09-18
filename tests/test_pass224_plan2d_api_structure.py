# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.planar_tools import FixedPlanarView, make_locked_plane
from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_api.surface import active_import_paths, supported_import_paths

ROOT = Path(__file__).resolve().parents[1]
PLAN_TRACE = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d"
API_PLAN2D = ROOT / "src" / "laserprog_studio" / "tool_api" / "plan2d"


def test_plan2d_package_has_long_term_sections() -> None:
    expected = {
        "__init__.py",
        "plane.py",
        "sketch.py",
        "actors.py",
        "snap.py",
        "dimensions.py",
        "metrics.py",
        "curves.py",
    }
    assert expected.issubset({path.name for path in API_PLAN2D.glob("*.py")})
    assert plan2d.plane.Plan2DCoordinateMapper
    assert plan2d.sketch.PlanSketch
    assert plan2d.actors.register_plan_line
    assert plan2d.snap.smart_snap_on_plan
    assert plan2d.dimensions.DimensionSpec
    assert plan2d.metrics.MetricEditSession
    assert plan2d.curves.ArcIntent


def test_plan2d_is_active_and_plan_modules_are_supported_aliases() -> None:
    active = set(active_import_paths())
    supported = set(supported_import_paths())
    assert "laserprog_studio.tool_api.plan2d" in active
    assert "laserprog_studio.tool_api.planar_drawing" not in active
    assert "laserprog_studio.tool_api.dimensions" not in active
    assert "laserprog_studio.tool_api.metrics" not in active
    assert "laserprog_studio.tool_api.planar_drawing" in supported
    assert "laserprog_studio.tool_api.dimensions" in supported
    assert "laserprog_studio.tool_api.metrics" in supported


def test_coordinate_mapper_is_public_and_round_trips_semantic_display_sketch_spaces() -> None:
    plane = make_locked_plane(FixedPlanarView.TOP, depth=2.0)
    display_plane = plane.with_depth(2.75)
    mapper = plan2d.Plan2DCoordinateMapper(plane, display_plane)

    semantic = mapper.sketch_xy_to_world((12.0, -5.0))
    display = mapper.semantic_to_display_world(semantic)

    assert semantic == (12.0, -5.0, 2.0)
    assert display == (12.0, -5.0, 2.75)
    assert mapper.display_to_semantic_world(display) == semantic
    assert mapper.world_to_sketch_xy(semantic) == (12.0, -5.0)
    assert mapper.display_world_to_sketch_xy(display) == (12.0, -5.0)


def test_plan_sketch_facade_compiles_without_exposing_core_imports_to_tools() -> None:
    sketch = plan2d.create_sketch()
    a = sketch.add_point((0.0, 0.0))
    b = sketch.add_point((10.0, 0.0))
    line = sketch.add_line(a, b)
    result = sketch.compile()

    assert line in sketch.line_ids
    assert result.rebuilt_polylines >= 1
    assert sketch.entity_counts()["lines"] == 1


def test_plan_tracer_uses_plan2d_entrypoint_for_new_work_not_legacy_planar_drawing() -> None:
    sources = [
        *(PLAN_TRACE.glob("*.py")),
        ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d_tool.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert "from laserprog_studio.tool_api import planar_drawing as plan2d" not in combined
    assert "from laserprog_studio.tool_api import plan2d" in combined
    assert "tool_api.plan2d.curves" not in (PLAN_TRACE / "state.py").read_text(encoding="utf-8")
