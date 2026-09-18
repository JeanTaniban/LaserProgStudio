from __future__ import annotations

from pathlib import Path

from _path_setup import ROOT  # noqa: F401


def test_debug_mode_service_persists_and_disables_hot_diagnostics(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from laserprog_studio.services.debug_mode import is_debug_mode_enabled, set_debug_mode_enabled
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT
    from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_plan_trace_input_event

    set_debug_mode_enabled(False, persist=False)
    assert is_debug_mode_enabled() is False

    GLOBAL_APP_PERFORMANCE_AUDIT.reset()
    GLOBAL_APP_PERFORMANCE_AUDIT.increment("should.not.record")
    GLOBAL_APP_PERFORMANCE_AUDIT.record_timing("should.not.record", 12.0)
    record_plan_trace_input_event("mouse.move", screen_pos=(1, 2), world_pos=(3, 4, 5))

    snapshot = GLOBAL_APP_PERFORMANCE_AUDIT.snapshot()
    assert "should.not.record" not in snapshot["counters"]
    assert "should.not.record" not in snapshot["timers"]
    assert not (tmp_path / "diagnostics" / "plan_trace_input_debug.jsonl").exists()

    set_debug_mode_enabled(True, persist=False)
    assert is_debug_mode_enabled() is True
    GLOBAL_APP_PERFORMANCE_AUDIT.increment("should.record")
    record_plan_trace_input_event("mouse.move", screen_pos=(1, 2), world_pos=(3, 4, 5))

    snapshot = GLOBAL_APP_PERFORMANCE_AUDIT.snapshot()
    assert snapshot["counters"]["should.record"] == 1
    assert (tmp_path / "diagnostics" / "plan_trace_input_debug.jsonl").exists()


def test_debug_mode_documentation_exists() -> None:
    path = Path(ROOT) / "docs" / "debug_diagnostics_mode.md"
    text = path.read_text(encoding="utf-8")
    assert "View > Performance / Debug" in text
    assert "should_record_diagnostics" in text
    assert "Do not add unconditional hot-path disk writes" in text
