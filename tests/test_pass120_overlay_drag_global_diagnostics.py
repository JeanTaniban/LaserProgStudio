# -*- coding: utf-8 -*-
from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.overlay import OverlayDragDiagnostics, OverlayFieldSpec, OverlayManager, OverlayWindowSpec


def test_pass120_qt_overlay_drag_uses_global_delta_not_local_feedback() -> None:
    source = read_qt_overlay_runtime_source()

    assert "globalPosition" in source
    assert "_drag_start_global" in source
    assert "_drag_start_pos" in source
    assert "global-delta drag move" in source
    assert "mapToParent(pos)" not in source
    assert "adapter.manager.drag_window(pointer)" not in source


def test_pass120_overlay_drag_diagnostics_detects_teleport_and_collapse() -> None:
    diag = OverlayDragDiagnostics()
    diag.record(
        "press",
        "w",
        pointer_global_px=(100, 100),
        widget_pos_px=(20, 20),
        spec_pos_px=(20, 20),
        size_px=(240, 80),
    )
    diag.record(
        "move",
        "w",
        pointer_global_px=(104, 104),
        widget_pos_px=(240, 240),
        spec_pos_px=(240, 240),
        size_px=(20, 8),
    )
    report = diag.report()
    codes = {issue.code for issue in report.issues}

    assert "OVERLAY_TELEPORT" in codes
    assert "OVERLAY_GEOMETRY_COLLAPSE" in codes
    assert "move samples: 1" in report.to_markdown()


def test_pass120_overlay_manager_exposes_drag_report() -> None:
    manager = OverlayManager()
    manager.show_window(
        OverlayWindowSpec(
            id="test.drag",
            title="Drag",
            owner_tool="tool_core_diag",
            fields=[OverlayFieldSpec("test.drag.info", "Info", "ready")],
            movable=True,
        )
    )
    manager.drag_diagnostics.record(
        "press",
        "test.drag",
        pointer_global_px=(10, 10),
        widget_pos_px=(3, 4),
        spec_pos_px=(3, 4),
        size_px=(220, 70),
    )

    assert len(manager.drag_report().samples) == 1
    manager.clear_drag_diagnostics()
    assert len(manager.drag_report().samples) == 0


def test_pass120_diagnostic_panel_exports_overlay_drag_report() -> None:
    panel = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])

    assert "API benchmark" in panel
    assert "Full validation" in panel
    assert "export_overlay_drag_diagnostics" in controller
    assert "Overlay drag samples" in controller
