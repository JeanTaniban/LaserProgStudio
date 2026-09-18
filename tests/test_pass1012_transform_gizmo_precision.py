# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.application.transform_gizmo_api import (
    OWNER_TOOL,
    SCALE_MANIPULATOR_ID,
    pick_native_transform_gizmo,
    sync_native_scale_gizmo,
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


def test_pass1012_translate_pick_ignores_shared_triad_center() -> None:
    owner = _FakeOwner()
    assert sync_native_translate_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=_axes(), render=False)

    assert pick_native_transform_gizmo(owner, 300.0, 200.0) is None
    assert pick_native_transform_gizmo(owner, 392.0, 200.0) == ("gizmo", "x")
    assert pick_native_transform_gizmo(owner, 300.0, 108.0) == ("gizmo", "y")


def test_pass1012_scale_handles_are_clamped_outside_large_frame() -> None:
    owner = _FakeOwner()
    frame = (
        ("x_max", (10.0, -10.0, 0.0), (10.0, 10.0, 0.0), "#ff0000"),
        ("y_max", (-10.0, 10.0, 0.0), (10.0, 10.0, 0.0), "#00ff00"),
    )
    assert sync_native_scale_gizmo(owner, center=(0.0, 0.0, 0.0), length=1.0, axes=_axes(), frame_specs=frame, render=False)

    ctx = owner._native_transform_gizmo_ctx
    x_handle = ctx.transform_gizmos.handle(f"{SCALE_MANIPULATOR_ID}:scale:x", owner_tool=OWNER_TOOL)
    y_handle = ctx.transform_gizmos.handle(f"{SCALE_MANIPULATOR_ID}:scale:y", owner_tool=OWNER_TOOL)
    assert x_handle.position[0] > 10.0
    assert y_handle.position[1] > 10.0


def test_pass1012_transform_gizmo_rendering_is_isolated_from_generic_creator_painter() -> None:
    generic = Path("src/laserprog_studio/application/_tool_core_diag_scene_painter.py").read_text(encoding="utf-8")
    transform = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")

    assert "_native_transform_gizmo_snapshot" not in generic
    assert "def _guide_direction_uv" not in generic
    assert "ctx.transform_gizmos" not in generic
    assert "TransformGizmo" not in generic
    assert "overlay_assembly" in transform
    assert "main_assembly" in transform
