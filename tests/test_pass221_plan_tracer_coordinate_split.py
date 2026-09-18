from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_TRACE = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d"


def test_coordinate_mapper_owns_plan_tracer_coordinate_conversions() -> None:
    mapper = (PLAN_TRACE / "coordinate_mapper.py").read_text(encoding="utf-8")
    snap = (PLAN_TRACE / "snap.py").read_text(encoding="utf-8")
    sketch_sync = (PLAN_TRACE / "sketch_sync.py").read_text(encoding="utf-8")
    drawing = (PLAN_TRACE / "drawing.py").read_text(encoding="utf-8")
    dimensions = (PLAN_TRACE / "dimensions.py").read_text(encoding="utf-8")

    assert "class PlanTrace2DCoordinateMapper" in mapper
    assert "display_world_to_semantic" in mapper
    assert "semantic_world_to_sketch_xy" in mapper
    assert "sketch_xy_to_display_world" in mapper
    assert "sample_arc_display_points" in mapper

    assert "semantic_point_for_display_world" not in drawing
    assert "semantic_point_for_display_world" not in dimensions
    assert "services.snap._sketch_xy" not in sketch_sync
    assert "services.snap._semantic_world" not in sketch_sync
    assert "services.coordinates" in snap


def test_snap_targets_are_split_from_cursor_and_drag_service() -> None:
    services = (PLAN_TRACE / "services.py").read_text(encoding="utf-8")
    snap = (PLAN_TRACE / "snap.py").read_text(encoding="utf-8")
    targets = (PLAN_TRACE / "snap_targets.py").read_text(encoding="utf-8")

    assert "PlanTrace2DSnapTargetsService" in targets
    assert "snap_targets: Any" in services
    assert "snap_targets=PlanTrace2DSnapTargetsService(tool)" in services
    assert snap.count("def _live_snap_targets") == 1
    assert "return self.services.snap_targets._live_snap_targets" in snap
    assert "for line_id, line in self._state.sketch.lines.items()" not in snap
    assert "for line_id, line in self._state.sketch.lines.items()" in targets
