# -*- coding: utf-8 -*-
from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner
from laserprog_studio.tool_core.gizmos import GizmoVisualState


def test_pass119_minimal_dot_fixed_values_are_two_and_three() -> None:
    runner = CoreDiagRunner()

    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.GRABBABLE) == 2
    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.FIXED) == 2
    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.HOVER) == 3
    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.GRABBED) == 3


def test_pass119_minimal_style_does_not_force_large_minimum() -> None:
    source = Path("src/laserprog_studio/tool_core/gizmos/styles.py").read_text(encoding="utf-8")
    manager = Path("src/laserprog_studio/tool_core/gizmos/manager.py").read_text(encoding="utf-8")
    panel = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])

    assert "min_radius_px=None" in source
    assert "self.minimal_dot_normal_radius_px = 2" in manager
    assert "self.minimal_dot_active_radius_px = 3" in manager
    assert "Minimal dot" in panel
    assert "Active dot" in panel


def test_pass119_middle_click_popover_has_dummy_buttons() -> None:
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])

    assert "Option A" in controller
    assert "Option B" in controller
    assert "Apply" in controller
    assert "Middle-click Blender-style popover" in controller


def test_pass119_qt_overlay_drag_is_single_constraint_direct_widget_move() -> None:
    source = read_qt_overlay_runtime_source()

    assert "self._drag_offset_local" in source
    assert "The Qt adapter now owns" in source
    assert "adapter.manager.set_window_position(self.window_id, int(self.x()), int(self.y()))" in source
    assert "self.move(int(x), int(y))" in source
    assert "qt-move fast-path" in source
    assert "adapter.manager.drag_window(pointer)" not in source
