# -*- coding: utf-8 -*-
from pathlib import Path


def test_transform_overlay2d_drag_survives_qvtk_nobutton_move() -> None:
    source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    assert "transform_drag_owned" in source
    assert "_gizmo_pressed_axis" in source
    assert "_viewport_pointer_buttons_down" in source
    no_button = source.split("if buttons == Qt.NoButton:", 1)[1].split("if buttons & Qt.RightButton:", 1)[0]
    assert "if not transform_drag_owned" in no_button
    assert "_reset_viewport_pointer_state" in no_button


def test_transform_drag_still_uses_explicit_release_cleanup() -> None:
    source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    release = source.split("elif etype == QEvent.MouseButtonRelease:", 1)[1]
    assert "self._finish_gizmo_drag()" in release
    assert "self._gizmo_pressed_axis = None" in release
