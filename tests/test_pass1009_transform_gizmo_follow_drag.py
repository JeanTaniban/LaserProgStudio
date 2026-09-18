# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.application.transform_gizmo_api import (
    MANIPULATOR_ID,
    OWNER_TOOL,
    move_native_translate_gizmo_live,
    pick_native_transform_gizmo,
    sync_native_translate_gizmo,
)


class _FakePlotter:
    def height(self) -> int:
        return 400

    def width(self) -> int:
        return 600

    def render(self) -> None:
        return None


class _FakeOwner:
    _native_transform_gizmo_enabled = True

    def __init__(self) -> None:
        self.plotter = _FakePlotter()
        self.gizmo_actors = {}
        self._native_transform_gizmo_active = False

    def _world_to_display(self, point):
        x, y, z = point
        return (300.0 + float(x) * 10.0, 200.0 + float(y) * 10.0, float(z))


def _axes():
    return {
        "x": ((1.0, 0.0, 0.0), "#ff0000"),
        "y": ((0.0, 1.0, 0.0), "#00ff00"),
        "z": ((0.0, 0.0, 1.0), "#0000ff"),
    }


def test_pass1009_native_translate_gizmo_can_follow_live_drag_without_rebuild() -> None:
    owner = _FakeOwner()
    assert sync_native_translate_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=_axes(), render=False)
    owner._native_transform_gizmo_drag_base_snapshot = owner._native_transform_gizmo_snapshot

    assert move_native_translate_gizmo_live(owner, offset=(4.0, 2.0, 0.0), render=False)

    ctx = owner._native_transform_gizmo_ctx
    assert owner._native_transform_gizmo_snapshot.center == (4.0, 2.0, 0.0)
    assert ctx.transform_gizmos.handle(f"{MANIPULATOR_ID}:center", owner_tool=OWNER_TOOL).position == (4.0, 2.0, 0.0)
    assert ctx.transform_gizmos.handle(f"{MANIPULATOR_ID}:x", owner_tool=OWNER_TOOL).position == (14.0, 2.0, 0.0)
    line = next(item for item in ctx.preview.items(owner_tool=OWNER_TOOL) if item.id == f"{MANIPULATOR_ID}:axis:x")
    assert line.points == ((4.0, 2.0, 0.0), (12.6, 2.0, 0.0))

    # Picking follows the moved snapshot; the old +X tip at qx ~= 400 is no
    # longer the best target, the new tip is around qx ~= 440.
    assert pick_native_transform_gizmo(owner, 438.0, 180.0) == ("gizmo", "x")


def test_pass1009_translation_drag_updates_native_gizmo_during_actor_preview() -> None:
    source = Path("src/laserprog_studio/controllers/transform_drag.py").read_text(encoding="utf-8")
    body = source.split("def _update_gizmo_translate_drag", 1)[1].split("def _update_gizmo_rotate_drag", 1)[0]
    start = source.split("def _start_gizmo_translate_drag", 1)[1].split("def _start_gizmo_rotate_drag", 1)[0]

    assert "_native_transform_gizmo_drag_base_snapshot" in start
    assert "move_native_translate_gizmo_live" in body
    assert "transform.drag.translate.gizmo_follow" in body
