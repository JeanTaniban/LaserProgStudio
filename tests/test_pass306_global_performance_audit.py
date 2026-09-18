from __future__ import annotations

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT, export_application_performance_audit
from laserprog_studio.tool_core.perf.profiler import ToolProfiler


def test_pass306_global_audit_exports_single_markdown_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    GLOBAL_APP_PERFORMANCE_AUDIT.reset()
    GLOBAL_APP_PERFORMANCE_AUDIT.increment("app.test.counter")
    GLOBAL_APP_PERFORMANCE_AUDIT.set_value("app.test.value", "ok")
    with GLOBAL_APP_PERFORMANCE_AUDIT.measure("app.test.timer"):
        pass

    path = export_application_performance_audit(reason="unit-test")

    assert path == tmp_path / "diagnostics" / "application_performance_audit.md"
    text = path.read_text(encoding="utf-8")
    assert "LaserProg Studio — application performance audit" in text
    assert "app.test.timer" in text
    assert "app.test.counter" in text
    assert "Raw JSON" in text
    assert not (tmp_path / "diagnostics" / "application_performance_audit.json").exists()
    assert not (tmp_path / "diagnostics" / "application_performance_audit.csv").exists()


def test_pass306_tool_profiler_mirrors_into_global_audit() -> None:
    GLOBAL_APP_PERFORMANCE_AUDIT.reset()
    profiler = ToolProfiler()
    profiler.increment("demo.counter", 3)
    profiler.set_value("demo.value", 12)
    profiler.record_timing("demo.timer", 42.0, details={"phase": "unit"})

    snapshot = GLOBAL_APP_PERFORMANCE_AUDIT.snapshot()

    assert snapshot["counters"]["toolctx.demo.counter"] == 3
    assert snapshot["values"]["toolctx.demo.value"] == 12
    assert snapshot["timers"]["toolctx.demo.timer"]["count"] == 1
    assert snapshot["timers"]["toolctx.demo.timer"]["max_ms"] == 42.0
