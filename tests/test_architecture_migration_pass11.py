# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "laserprog_studio" / "application"


def _source(name: str) -> str:
    return (APP / name).read_text(encoding="utf-8")


def test_texture_gizmo_controller_is_now_a_service_facade() -> None:
    source = _source("texture_gizmo_controller.py")

    assert "class TextureGizmoController" in source
    assert "TextureGizmoTargetService" in source
    assert "TextureGizmoLiveUpdateService" in source
    assert "TextureGizmoEventService" in source
    assert "TextureGizmoRenderService" in source
    assert "TextureGizmoDragService" in source
    assert "def update_texture_rotation_gizmo" in source
    assert "def _handle_texture_rotation_global_mouse_event" in source
    assert "from .._window_deps import *" not in source
    assert len(source.splitlines()) < 230


def test_texture_gizmo_services_own_focused_responsibilities() -> None:
    target = _source("texture_gizmo_target_service.py")
    live = _source("texture_gizmo_live_update_service.py")
    events = _source("texture_gizmo_event_service.py")
    render = _source("texture_gizmo_render_service.py")
    drag = _source("texture_gizmo_drag_service.py")

    assert "class TextureGizmoTargetService" in target
    assert "def _texture_rotation_target" in target
    assert "def _pick_texture_rotation_gizmo_from_qt_pos" in target
    assert "def _texture_move_screen_matrix" in target

    assert "class TextureGizmoLiveUpdateService" in live
    assert "def _texture_projection_live_update_current_target" in live
    assert "def _texture_projection_set_actor_uvs_fast" in live

    assert "class TextureGizmoEventService" in events
    assert "def _install_texture_rotation_vtk_observers" in events
    assert "def _poll_texture_rotation_gizmo_drag" in events
    assert "app.installEventFilter(self.owner)" in events
    assert "_qtimer()(self.owner)" in events

    assert "class TextureGizmoRenderService" in render
    assert "def update_texture_rotation_gizmo" in render

    assert "class TextureGizmoDragService" in drag
    assert "def _start_texture_rotation_gizmo_drag" in drag
    assert "def _finish_texture_rotation_gizmo_drag" in drag

    for source in (target, live, events, render, drag):
        assert "from .._window_deps import *" not in source
        assert len(source.splitlines()) < 520


def test_pass11_documentation_exists() -> None:
    assert (ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_11.md").exists()
