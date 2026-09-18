# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.application.transform_gizmo_api import (
    OWNER_TOOL,
    MANIPULATOR_ID,
    pick_native_transform_gizmo,
    sync_native_translate_gizmo,
)
from laserprog_studio.tool_core.gizmos import GizmoManager, MemoryGizmoBackend
from laserprog_studio.tool_core.transform_gizmos import TransformGizmoManager


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
        # Simple orthographic projection for deterministic screen-space picking.
        x, y, z = point
        return (300.0 + float(x) * 10.0, 200.0 + float(y) * 10.0, float(z))


def test_pass1007_gizmo_manager_translate_supports_axis_length_and_vectors() -> None:
    backend = MemoryGizmoBackend()
    manager = TransformGizmoManager(backend)

    manipulator = manager.translate(
        id="native.translate",
        owner_tool="test",
        origin=(10.0, 20.0, 30.0),
        axes=("x", "y"),
        axis_vectors={"x": (0.0, 1.0, 0.0), "y": (0.0, 0.0, 1.0)},
        axis_length=5.0,
        include_center=False,
    )

    assert manipulator.kind == "translate"
    assert manipulator.handle_ids == ("native.translate:x", "native.translate:y")
    assert manager.handle("native.translate:x", owner_tool="test").position == (10.0, 25.0, 30.0)
    assert manager.handle("native.translate:y", owner_tool="test").position == (10.0, 20.0, 35.0)
    assert backend.removed == 0


def test_pass1007_app_translate_gizmo_is_declared_through_creator_api() -> None:
    owner = _FakeOwner()
    axes = {
        "x": ((1.0, 0.0, 0.0), "#ff0000"),
        "y": ((0.0, 1.0, 0.0), "#00ff00"),
        "z": ((0.0, 0.0, 1.0), "#0000ff"),
    }

    assert sync_native_translate_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=axes, render=False)

    ctx = owner._native_transform_gizmo_ctx
    assert owner._native_transform_gizmo_active is True
    assert len(ctx.transform_gizmos.handles(owner_tool=OWNER_TOOL)) == 4  # X/Y/Z + non-pickable center
    assert len(ctx.preview.items(owner_tool=OWNER_TOOL)) == 3
    assert ctx.transform_gizmos.handle(f"{MANIPULATOR_ID}:x", owner_tool=OWNER_TOOL).kind == "translate:x"
    assert owner.gizmo_actors == {}


def test_pass1007_native_translate_gizmo_uses_math_pick_not_vtk_actor_pick() -> None:
    owner = _FakeOwner()
    axes = {
        "x": ((1.0, 0.0, 0.0), "#ff0000"),
        "y": ((0.0, 1.0, 0.0), "#00ff00"),
        "z": ((0.0, 0.0, 1.0), "#0000ff"),
    }
    sync_native_translate_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=axes, render=False)

    # Qt coordinates are top-left; fake projection converts world +X to qx 400.
    assert pick_native_transform_gizmo(owner, 395.0, 200.0) == ("gizmo", "x")
    assert pick_native_transform_gizmo(owner, 300.0, 100.0) == ("gizmo", "y")
    assert pick_native_transform_gizmo(owner, 40.0, 40.0) is None


def test_pass1007_legacy_translate_actor_build_is_behind_native_api_path() -> None:
    source = Path("src/laserprog_studio/controllers/gizmo_view.py").read_text(encoding="utf-8")

    assert "sync_native_translate_gizmo" in source
    assert "branch=translate_native_api" in source
    assert source.index("sync_native_translate_gizmo") < source.index("branch=translate_legacy")

from laserprog_studio.application.transform_gizmo_api import (
    ROTATE_MANIPULATOR_ID,
    SCALE_MANIPULATOR_ID,
    sync_native_rotate_gizmo,
    sync_native_scale_gizmo,
)


def test_pass1008_gizmo_manager_rotate_and_scale_accept_axis_vectors() -> None:
    backend = MemoryGizmoBackend()
    manager = TransformGizmoManager(backend)

    rot = manager.rotate(
        id="native.rotate",
        owner_tool="test",
        origin=(1.0, 2.0, 3.0),
        axes=("x",),
        axis_vectors={"x": (0.0, 1.0, 0.0)},
        axis_length=4.0,
    )
    sca = manager.scale(
        id="native.scale",
        owner_tool="test",
        origin=(1.0, 2.0, 3.0),
        axes=("z",),
        axis_vectors={"z": (1.0, 0.0, 0.0)},
        axis_length=6.0,
    )

    assert rot.kind == "rotate"
    assert rot.handle_ids == ("native.rotate:rotate:x",)
    assert manager.handle("native.rotate:rotate:x", owner_tool="test").position == (1.0, 6.0, 3.0)
    assert sca.kind == "scale"
    assert sca.handle_ids == ("native.scale:scale:z",)
    assert manager.handle("native.scale:scale:z", owner_tool="test").position == (7.0, 2.0, 3.0)
    assert backend.removed == 0


def test_pass1008_app_rotate_gizmo_uses_api_rings_and_math_pick() -> None:
    owner = _FakeOwner()
    axes = {
        "x": ((1.0, 0.0, 0.0), "#ff0000"),
        "y": ((0.0, 1.0, 0.0), "#00ff00"),
        "z": ((0.0, 0.0, 1.0), "#0000ff"),
    }

    assert sync_native_rotate_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=axes, render=False)
    ctx = owner._native_transform_gizmo_ctx
    assert owner._native_transform_gizmo_snapshot.mode == "rotate"
    assert len(ctx.transform_gizmos.handles(owner_tool=OWNER_TOOL)) == 3
    assert len(ctx.preview.items(owner_tool=OWNER_TOOL)) >= 3
    assert ctx.transform_gizmos.handle(f"{ROTATE_MANIPULATOR_ID}:rotate:x", owner_tool=OWNER_TOOL).kind == "rotate:x"
    # X ring lies in YZ. In the fake orthographic XY projection, its top point is near qy=108.
    assert pick_native_transform_gizmo(owner, 300.0, 108.0) == ("gizmo", "x")


def test_pass1008_app_scale_gizmo_uses_api_handles_frame_edges_and_math_pick() -> None:
    owner = _FakeOwner()
    axes = {
        "x": ((1.0, 0.0, 0.0), "#ff0000"),
        "y": ((0.0, 1.0, 0.0), "#00ff00"),
        "z": ((0.0, 0.0, 1.0), "#0000ff"),
    }
    frame = (("x_max", (5.0, -5.0, 0.0), (5.0, 5.0, 0.0), "#ff0000"),)

    assert sync_native_scale_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=axes, frame_specs=frame, render=False)
    ctx = owner._native_transform_gizmo_ctx
    assert owner._native_transform_gizmo_snapshot.mode == "scale"
    assert ctx.transform_gizmos.handle(f"{SCALE_MANIPULATOR_ID}:scale:x", owner_tool=OWNER_TOOL).kind == "scale:x"
    assert ctx.transform_gizmos.handle(f"{SCALE_MANIPULATOR_ID}:scale:x_max", owner_tool=OWNER_TOOL).kind == "scale:x_max"
    assert pick_native_transform_gizmo(owner, 374.0, 200.0) == ("gizmo", "x")
    assert pick_native_transform_gizmo(owner, 350.0, 150.0) == ("gizmo", "x_max")


def test_pass1008_rotate_and_scale_legacy_paths_are_behind_native_api() -> None:
    source = Path("src/laserprog_studio/controllers/gizmo_view.py").read_text(encoding="utf-8")

    assert "sync_native_rotate_gizmo" in source
    assert "branch=rotate_native_api" in source
    assert source.index("sync_native_rotate_gizmo") < source.index("branch=rotate_legacy")
    assert "sync_native_scale_gizmo" in source
    assert "branch=scale_native_api" in source
    assert source.index("sync_native_scale_gizmo") < source.index("branch=scale_legacy")
