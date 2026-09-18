# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.gizmos import (
    DEFAULT_POINT_STYLES,
    GizmoHandle,
    GizmoManager,
    GizmoVisualState,
    MemoryGizmoBackend,
    axis_locked_billboard_basis,
)


class _Camera:
    def __init__(self, position, focal=(0.0, 0.0, 0.0)) -> None:
        self._position = position
        self._focal = focal

    def GetPosition(self):
        return self._position

    def GetFocalPoint(self):
        return self._focal


def test_pass116_minimal_dot_is_tunable_and_state_colored() -> None:
    style = DEFAULT_POINT_STYLES["minimal"]
    assert style.guide_shape == "none"
    assert style.draw_core is True
    assert len({style.color_for(state) for state in (GizmoVisualState.GRABBABLE, GizmoVisualState.HOVER, GizmoVisualState.GRABBED)}) == 3

    backend = MemoryGizmoBackend()
    manager = GizmoManager(backend)
    manager.set_minimal_dot_radii(normal_px=4, active_px=10)
    manager.create_handle(
        GizmoHandle(
            id="minimal",
            owner_tool="test",
            position=(0.0, 0.0, 0.0),
            radius_px=manager.radius_for_style("minimal", 12, GizmoVisualState.GRABBABLE),
            color=style.color_for(GizmoVisualState.GRABBABLE),
            style_id="minimal",
            base_radius_px=12,
            selectable=True,
        )
    )
    initial = manager.handles(owner_tool="test")[0]
    assert initial.radius_px == 4
    assert manager.update_visual_state("minimal", hover=True)
    hover = manager.handles(owner_tool="test")[0]
    assert hover.color == style.color_for(GizmoVisualState.HOVER)
    assert hover.radius_px == 10
    assert manager.update_visual_state("minimal", grabbed=True)
    grabbed = manager.handles(owner_tool="test")[0]
    assert grabbed.color == style.color_for(GizmoVisualState.GRABBED)
    assert grabbed.radius_px == 10


def test_pass116_axis_locked_billboard_basis_snaps_to_nearest_axis() -> None:
    top = axis_locked_billboard_basis(_Camera((0.0, 0.0, 10.0)))
    assert top.axis == "+Z"
    assert top.u == (1.0, 0.0, 0.0)
    assert top.v == (0.0, 1.0, 0.0)
    assert top.point((1.0, 2.0, 3.0), 4.0, 5.0, 0.25) == (5.0, 7.0, 3.25)

    side = axis_locked_billboard_basis(_Camera((10.0, 1.0, 0.0)))
    assert side.axis == "+X"
    assert side.u == (0.0, 1.0, 0.0)
    assert side.v == (0.0, 0.0, 1.0)
    assert side.point((1.0, 2.0, 3.0), 4.0, 5.0, 0.25) == (1.25, 6.0, 8.0)

    front = axis_locked_billboard_basis(_Camera((1.0, -10.0, 2.0)))
    assert front.axis == "-Y"
    assert front.u == (1.0, 0.0, 0.0)
    assert front.v == (0.0, 0.0, 1.0)


def test_pass116_diag_painter_uses_axis_locked_not_direct_billboard() -> None:
    source = read_tool_core_diag_scene_runtime_source()
    assert "plotter_axis_locked_billboard_basis" in source
    assert "axis_basis.point" in source
    assert "direct camera-facing UI" not in source  # policy lives in camera_scale, not ad-hoc painter text


def test_pass116_overlay_adapter_prevents_thin_bar_popover() -> None:
    source = read_qt_overlay_runtime_source()
    assert "_minimum_height_for_spec" in source
    assert "Do not let Qt collapse" in source
    assert "widget.resize(width, height)" in source
    assert "QSizePolicy.Fixed" in source
