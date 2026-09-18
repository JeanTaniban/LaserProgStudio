# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_pass140_selection_box_prefers_vtk_actor2d_overlay() -> None:
    source = Path("src/laserprog_studio/ui/selection_box_overlay.py").read_text(encoding="utf-8")

    assert "vtkActor2D" in source
    assert "vtkPolyDataMapper2D" in source
    assert "SetCoordinateSystemToDisplay" in source
    assert "SetPoint" in source
    assert "Modified()" in source
    assert "AddActor2D" in source
    assert "_qt_rect_to_vtk_display_rect" in source
    assert "GetRenderWindow" in source
    assert "qt_h - float(target.top())" in source
    assert "no actor churn" in source.lower()


def test_pass140_qt_fallback_repaints_old_geometry_before_move() -> None:
    source = Path("src/laserprog_studio/ui/selection_box_overlay.py").read_text(encoding="utf-8")

    assert "parent.repaint(old_geometry)" in source
    assert "super().hide()" in source
    assert "update() alone can be queued behind mouse moves" in source


def test_pass140_box_selection_is_still_shift_only_in_lab() -> None:
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    manager = Path("src/laserprog_studio/tool_core/box_selection.py").read_text(encoding="utf-8")

    assert "shift_down" in controller
    assert "activation_modifier" in manager
    assert "BoxSelectionActivationModifier.SHIFT" in manager
