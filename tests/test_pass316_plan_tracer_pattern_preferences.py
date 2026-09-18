from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.services.project_preferences import (
    LaserEngravingPreferences,
    ProjectPreferences,
    coerce_project_preferences,
)
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def test_plan_tracer_pattern_max_segments_is_project_preference() -> None:
    prefs = coerce_project_preferences({"laser": {"plan_tracer_pattern_max_segments": "250000"}})
    assert prefs.laser.plan_tracer_pattern_max_segments == 250000
    assert ProjectPreferences().laser.plan_tracer_pattern_max_segments == 120000


def test_plan_tracer_pattern_budget_rejects_absurd_values() -> None:
    assert coerce_project_preferences({"laser": {"plan_tracer_pattern_max_segments": "42"}}).laser.plan_tracer_pattern_max_segments == 120000
    assert coerce_project_preferences({"laser": {"plan_tracer_pattern_max_segments": "2000000"}}).laser.plan_tracer_pattern_max_segments == 120000


def test_plan_tracer_reads_pattern_budget_from_owner_preferences() -> None:
    tool = PlanTrace2DCreatorTool()
    prefs = ProjectPreferences(laser=LaserEngravingPreferences(plan_tracer_pattern_max_segments=333000))
    ctx = SimpleNamespace(owner=SimpleNamespace(project_preferences=prefs))
    assert tool._pattern_max_segments(ctx) == 333000


def test_plan_tracer_add_forces_current_board_thickness_preference(monkeypatch) -> None:
    tool = PlanTrace2DCreatorTool()
    tool._state.extrusion_depth = 99.0
    ctx = SimpleNamespace(owner=SimpleNamespace(project_preferences=ProjectPreferences(laser=LaserEngravingPreferences(default_board_thickness_mm=4.2))))
    called = {}

    def fake_apply(received_ctx):
        called["depth"] = tool._state.extrusion_depth
        return True

    monkeypatch.setattr(tool, "on_apply", fake_apply)
    monkeypatch.setattr(tool, "_close_after_validation", lambda *args, **kwargs: None)
    assert tool._apply_add_and_close(ctx) is True
    assert called["depth"] == 4.2
