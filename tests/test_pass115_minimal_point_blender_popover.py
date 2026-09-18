# -*- coding: utf-8 -*-
from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner
from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, GizmoVisualState
from laserprog_studio.tool_core.overlay import OverlayFieldSpec


def test_pass115_minimal_handle_is_colored_dot_style() -> None:
    style = DEFAULT_POINT_STYLES["minimal"]
    assert style.label == "Minimal dot"
    assert style.guide_shape == "none"
    assert style.draw_core is True
    assert style.color_for(GizmoVisualState.GRABBABLE) != style.color_for(GizmoVisualState.HOVER)
    assert style.color_for(GizmoVisualState.HOVER) != style.color_for(GizmoVisualState.GRABBED)


def test_pass115_context_popover_is_blender_style_non_draggable_clickaway() -> None:
    runner = CoreDiagRunner()
    pop = runner.ctx.overlay.show_context_popover_at_cursor(
        "diag.overlay.middle_popover",
        owner_tool="tool_core_diag",
        title="Viewport options",
        cursor_px=(220, 140),
        fields=[OverlayFieldSpec("opt.a", "Mode", "Dummy option")],
    )
    assert pop.overlay_kind == "context_menu"
    assert pop.movable is False
    assert pop.close_on_click_outside is True
    assert pop.position_px == (238, 154)
    assert runner.ctx.overlay.handle_click_outside(owner_tool="tool_core_diag") == 1
    assert runner.ctx.overlay.window("diag.overlay.middle_popover").visible is False  # type: ignore[union-attr]


def test_pass115_qt_overlay_adapter_synchronizes_widget_position_before_drag() -> None:
    source = read_qt_overlay_runtime_source()
    assert "set_window_position(self.window_id, int(self.x()), int(self.y()))" in source
    assert "globalPosition" in source
    assert "made the overlay jump" in source
    assert "mapToParent(pos)" not in source


def test_pass115_middle_click_popover_is_wired_in_diagnostic_tool() -> None:
    interaction = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    assert "event.button() == Qt.MiddleButton" in interaction
    assert "show_blender_style_popover(qx, qy)" in interaction
    assert "show_context_popover_at_cursor" in controller
    assert "Click-away overlays closed" in controller
