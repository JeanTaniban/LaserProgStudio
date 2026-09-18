from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.plan2d import metrics as metric_api
from laserprog_studio.tooling.plan_trace_2d.constants import _METRIC_OVERLAY_ID


def test_metric_api_can_build_modern_validation_bar_without_breaking_legacy_default() -> None:
    session = metric_api.rectangle_metric_session(_METRIC_OVERLAY_ID, width=80.0, height=40.0)

    legacy = metric_api.build_metric_edit_window(
        window_id=_METRIC_OVERLAY_ID,
        owner_tool="plan_trace",
        session=session,
        validate_button_id="plan_trace_2d.metric.validate",
        cancel_button_id="plan_trace_2d.metric.cancel",
    )
    modern = metric_api.build_metric_edit_window(
        window_id=_METRIC_OVERLAY_ID,
        owner_tool="plan_trace",
        session=session,
        validate_button_id="plan_trace_2d.metric.validate",
        cancel_button_id="plan_trace_2d.metric.cancel",
        width_px=0,
        overlay_kind="metric_bar",
    )

    assert legacy.overlay_kind == "toolbar"
    assert legacy.title == ""
    assert modern.overlay_kind == "metric_bar"
    assert modern.title == "Rectangle placement"
    assert modern.width_px >= 520
    assert [field.label for field in modern.fields] == ["Width", "Height"]
    assert modern.buttons[0].style == "primary"


def test_plan_tracer_uses_metric_bar_and_metric_buttons_do_not_steal_focus() -> None:
    metrics_source = Path("src/laserprog_studio/tooling/plan_trace_2d/metrics.py").read_text(encoding="utf-8")
    qt_layout_source = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")

    show_metric_overlay = metrics_source.split("def _show_metric_overlay", 1)[1].split("def _validate_metric_draft", 1)[0]
    assert 'overlay_kind="metric_bar"' in show_metric_overlay
    assert "width_px=0" in show_metric_overlay
    assert "button.setFocusPolicy(Qt.NoFocus)" in qt_layout_source
    assert "button.setAutoDefault(False)" in qt_layout_source
    assert "flush_overlay_edits_for_button(self, button_id)" in Path("src/laserprog_studio/tool_core/overlay/qt_adapter.py").read_text(encoding="utf-8")
