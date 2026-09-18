# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_pass139_selection_box_overlay_is_not_fullscreen_translucent() -> None:
    source = Path("src/laserprog_studio/ui/selection_box_overlay.py").read_text(encoding="utf-8")

    assert "must *not* cover the full" in source
    assert "super().setGeometry(geometry)" in source
    assert "parent.update(old_geometry)" in source
    assert "_sync_to_parent" not in source
    assert "fillRect(event.rect(), QColor(0, 0, 0, 0))" not in source
    assert "CompositionMode_Source)" not in source
    assert "CompositionMode_SourceOver" in source


def test_pass139_selection_box_overlay_keeps_shift_activation_in_lab() -> None:
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    assert "if bool(shift_down)" in controller
    assert "selection_box.begin" in controller
    assert "selection_box.update" in controller
    assert "selection_box.finish" in controller
