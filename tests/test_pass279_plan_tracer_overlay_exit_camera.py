from __future__ import annotations

from pathlib import Path


def test_metric_validation_overlay_is_bottom_centered() -> None:
    source = Path("src/laserprog_studio/tooling/plan_trace_2d/metrics.py").read_text(encoding="utf-8")

    assert 'anchor="viewport_bottom_center"' in source
    assert 'anchor="viewport_top_center"' not in source.partition("def _show_metric_overlay")[2].partition("def _validate_metric_draft")[0]


def test_plan_tracer_toolbox_uses_sectioned_toolbar_v2_for_polyline_actions() -> None:
    overlay = Path("src/laserprog_studio/tooling/plan_trace_2d/overlay.py").read_text(encoding="utf-8")
    layout = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")
    style = Path("src/laserprog_studio/tool_core/overlay/qt_style.py").read_text(encoding="utf-8")

    assert "build_command_deck_window" in overlay
    assert "OverlayToolbarSectionSpec" in overlay
    assert 'label="Rebuild"' in overlay
    assert "def _rebuild_command_deck_widget" in layout
    assert "ToolCoreCommandDeckSection" in style
    assert "ToolCoreCommandDeckChip" in style
    assert "_command_deck_responsive_slot_widths" in layout
    assert "button.setFixedSize(int(slot_width), _COMMAND_DECK_BUTTON_HEIGHT)" in layout
    assert "for section in visible_sections:" in layout


def test_escape_shortcut_tries_creator_cancel_before_close_fallback() -> None:
    router = Path("src/laserprog_studio/application/creator_global_shortcuts.py").read_text(encoding="utf-8")

    assert "dispatch_creator_key_shortcut(owner, \"escape\")" in router
    assert "cancel(getattr(owner, \"context\", None))" in router
    assert "owner.close_active_tool()" in router
    assert router.index("cancel(getattr(owner, \"context\", None))") < router.index("owner.close_active_tool()")


def test_plan_tracer_close_releases_plan_camera_through_api() -> None:
    tool = Path("src/laserprog_studio/tooling/plan_trace_2d_tool.py").read_text(encoding="utf-8")
    api_init = Path("src/laserprog_studio/tool_api/plan2d/__init__.py").read_text(encoding="utf-8")
    plane = Path("src/laserprog_studio/tool_api/plan2d/plane.py").read_text(encoding="utf-8")

    assert "plan2d.release_plan_view_camera(ctx)" in tool
    assert '"release_plan_view_camera": "plane"' in api_init
    assert "def release_plan_view_camera" in plane
    assert "view_iso()" in plane
