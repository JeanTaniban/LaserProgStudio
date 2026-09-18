# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.state.texture_gizmo_state import TextureGizmoState

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


def test_texture_gizmo_controller_is_composed_and_facaded() -> None:
    gizmo_source = (STUDIO / "application" / "texture_gizmo_controller.py").read_text(encoding="utf-8")
    mixin_source = (STUDIO / "controllers" / "texture_projection_tool.py").read_text(encoding="utf-8")
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")

    assert "class TextureGizmoController" in gizmo_source
    assert "def update_texture_rotation_gizmo" in gizmo_source
    assert "def _handle_texture_rotation_global_mouse_event" in gizmo_source
    assert "from .._window_deps import *" not in gizmo_source
    assert "def _qevent" in gizmo_source
    assert "def _qapplication" in gizmo_source

    assert "return self._texture_gizmo_controller().update_texture_rotation_gizmo" in mixin_source
    assert "return self._texture_gizmo_controller()._finish_texture_rotation_gizmo_drag" in mixin_source
    assert len(mixin_source.splitlines()) < 240

    assert "self.texture_gizmo_controller = TextureGizmoController.create(self.app_context)" in runtime_source
    assert "self.texture_gizmo_state = TextureGizmoState()" in runtime_source


def test_texture_gizmo_state_applies_legacy_window_defaults() -> None:
    window = SimpleNamespace()
    TextureGizmoState().apply_to_window(window)

    assert window._texture_rotation_gizmo_pressed is False
    assert window._texture_rotation_gizmo_drag_active is False
    assert window._texture_rotation_gizmo_target_index is None
    assert window._texture_rotation_gizmo_screen_radius_px == 82.0
    assert window._texture_rotation_gizmo_pick_radius_px == 44.0
    assert window._texture_rotation_gizmo_vtk_observer_ids == []
    assert window._global_event_filter_installed is False


def test_pass10_documentation_exists() -> None:
    assert (ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_10.md").exists()
