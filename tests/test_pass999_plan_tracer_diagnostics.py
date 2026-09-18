from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.perf.profiler import ToolProfiler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "laserprog_studio"


def _text(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_tool_profiler_exports_jitter_and_slow_events() -> None:
    profiler = ToolProfiler(slow_threshold_ms=0.1)
    profiler.record_timing("plan_trace.cursor.update", 0.05)
    profiler.record_timing("plan_trace.cursor.update", 2.0)
    profiler.increment("plan_trace.cursor.moves", 3)
    profiler.set_value("plan_trace.snap_targets.total", 42)

    flat = profiler.snapshot()
    detailed = profiler.snapshot_detailed()

    assert flat["plan_trace.cursor.update.count"] == 2
    assert flat["plan_trace.cursor.update.last_ms"] == 2.0
    assert flat["plan_trace.cursor.update.p95_ms"] >= 0.05
    assert detailed["counters"]["plan_trace.cursor.update"]["p95_ms"] >= 0.05
    assert detailed["values"]["plan_trace.cursor.moves"] == 3
    assert detailed["gauges"]["plan_trace.snap_targets.total"] == 42
    assert detailed["slow_events"][-1]["name"] == "plan_trace.cursor.update"


def test_plan_tracer_overlay_exports_markdown_json_and_csv() -> None:
    overlay = _text("tooling/plan_trace_2d/overlay.py")
    assert "plan_trace_2d_timings.md" in overlay
    assert "plan_trace_2d_timings.json" in overlay
    assert "plan_trace_2d_timings.csv" in overlay
    assert "_write_timing_markdown" in overlay
    assert "_write_timing_csv" in overlay
    assert "_diagnostic_context" in overlay
    assert "slow_events" in overlay


def test_plan_tracer_tool_lifecycle_and_event_timings_are_present() -> None:
    tool = _text("tooling/plan_trace_2d_tool.py")
    assert "plan_trace.lifecycle.open" in tool
    assert "plan_trace.lifecycle.close" in tool
    assert "plan_trace.event.total" in tool
    assert "plan_trace.event.mouse_move.update_cursor" in tool
    assert "plan_trace.apply.build_mesh" in tool
    assert "tool_close" in tool


def test_plan_tracer_snap_mouse_drag_and_cursor_timings_are_present() -> None:
    snap = _text("tooling/plan_trace_2d/snap.py")
    assert "plan_trace.draw_press.total" in snap
    assert "plan_trace.cursor.project" in snap
    assert "plan_trace.cursor.smart_snap" in snap
    assert "plan_trace.cursor.sync_actor_visuals" in snap
    assert "plan_trace.drag.resolve_positions.total" in snap
    assert "plan_trace.drag.sync_moved_points" in snap


def test_plan_tracer_snap_target_cache_timings_are_present() -> None:
    snap_targets = _text("tooling/plan_trace_2d/snap_targets.py")
    assert "plan_trace.snap_targets.fast_signature" in snap_targets
    assert "plan_trace.snap_targets.structural_signature" in snap_targets
    assert "plan_trace.snap_targets.build_live_targets" in snap_targets
    assert "plan_trace.snap_targets.build.arc_samples" in snap_targets
    assert "plan_trace.snap.near_query.total" in snap_targets


def test_plan2d_and_scene_cache_timings_are_present() -> None:
    plan2d_snap = _text("tool_api/plan2d/snap.py")
    scene_cache = _text("tool_core/scene_cache.py")
    assert "plan2d.guide_cache.scene.build" in plan2d_snap
    assert "plan2d.guide_cache.extra.build" in plan2d_snap
    assert "plan2d.smart_snap.alignment.nearest_axes" in plan2d_snap
    assert "plan2d.smart_snap.prepare_targets" in plan2d_snap
    assert "scene_cache.rebuild.total" in scene_cache
    assert "scene_cache.snap.near_query.total" in scene_cache
    assert "scene_cache.mesh.collect_objects" in scene_cache


def test_overlay_style_uses_qt_cursor_api_instead_of_invalid_stylesheet_property() -> None:
    qt_style = _text("tool_core/overlay/qt_style.py")
    assert "Unknown property cursor" not in qt_style
    assert "cursor:" not in qt_style
    assert "setCursor" in qt_style
    assert "Qt.OpenHandCursor" in qt_style
