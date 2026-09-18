# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder
from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES
from laserprog_studio.tool_core.overlay import OverlayFieldSpec


def test_pass114_minimal_is_simple_point_without_extra_guides() -> None:
    style = DEFAULT_POINT_STYLES["minimal"]
    assert style.guide_shape == "none"
    assert style.draw_core is True
    assert style.fixed_color != style.grabbable_color
    assert style.grabbable_color != style.hover_color
    assert style.hover_color != style.grabbed_color


def test_pass114_overlay_manager_supports_cursor_popovers_and_drag() -> None:
    runner = CoreDiagRunner()
    overlay = runner.ctx.overlay
    pop = overlay.show_popover_at_cursor(
        "test.cursor",
        owner_tool="tool_core_diag",
        title="Cursor",
        cursor_px=(100, 200),
        fields=[OverlayFieldSpec("test.cursor.value", "Value", "42")],
        movable=True,
    )
    assert pop.position_px == (114, 218)
    assert pop.overlay_kind == "popover"
    assert pop.movable is True

    assert overlay.begin_window_drag("test.cursor", (120, 230)) is True
    assert overlay.drag_window((170, 260)) is True
    moved = overlay.window("test.cursor")
    assert moved is not None
    assert moved.position_px == (164, 248)
    assert overlay.end_window_drag() == "test.cursor"


def test_pass114_runner_creates_multiple_overlay_types() -> None:
    runner = CoreDiagRunner()
    runner.run_overlay_types((300, 140))
    windows = runner.ctx.overlay.windows
    assert {"diag.overlay.palette", "diag.overlay.inspector", "diag.overlay.cursor_popover", "diag.overlay.tooltip"}.issubset(windows)
    assert windows["diag.overlay.cursor_popover"].position_px == (314, 158)
    assert windows["diag.overlay.cursor_popover"].movable is False
    assert windows["diag.overlay.palette"].movable is True
    assert windows["diag.overlay.tooltip"].movable is False


def test_pass114_camera_size_is_end_only_in_diagnostic_controller() -> None:
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    panel = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    assert "End-only policy" in controller
    assert "return False" in controller
    assert "Creator API Lab" in panel
    assert "Full validation" in panel
