# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.cavity_volume import measure_cavity_volume
from laserprog_studio.tooling.ids import TOOL_VOLUME_MEASURE
from laserprog_studio.tooling.registry import get_tool_spec, validate_tool_registry
from laserprog_studio.ui.toolbar_catalog import get_toolbar_item_spec, validate_toolbar_item_registry
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _cube_shell(prefix: str, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, *, offset: int = 0):
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),  # bottom
        (4, 5, 6), (4, 6, 7),  # top
        (0, 1, 5), (0, 5, 4),  # front
        (1, 2, 6), (1, 6, 5),  # right
        (2, 3, 7), (2, 7, 6),  # back
        (3, 0, 4), (3, 4, 7),  # left
    ]
    return vertices, [(a + offset, b + offset, c + offset) for a, b, c in triangles]


def test_measure_cavity_volume_detects_inner_shell_liters() -> None:
    outer_v, outer_t = _cube_shell("outer", 0, 100, 0, 100, 0, 100, offset=0)
    inner_v, inner_t = _cube_shell("inner", 25, 75, 25, 75, 25, 75, offset=len(outer_v))
    mesh = WorkMesh("hollow box", outer_v + inner_v, outer_t + inner_t)

    report = measure_cavity_volume(mesh)

    assert report.closed_shell_count == 2
    assert report.cavity_count == 1
    assert report.cavity_volume_liters == pytest.approx(0.125)
    assert report.outer_volume_liters == pytest.approx(1.0)
    assert report.warning is None


def test_measure_cavity_volume_ignores_disconnected_solid_outside_outer_shell() -> None:
    outer_v, outer_t = _cube_shell("outer", 0, 100, 0, 100, 0, 100, offset=0)
    outside_v, outside_t = _cube_shell("outside", 200, 250, 0, 50, 0, 50, offset=len(outer_v))
    mesh = WorkMesh("two solids", outer_v + outside_v, outer_t + outside_t)

    report = measure_cavity_volume(mesh)

    assert report.closed_shell_count == 2
    assert report.cavity_count == 0
    assert report.cavity_volume_liters == 0.0
    assert report.warning is not None


def test_volume_measure_tool_is_registered_and_has_panel_toolbar() -> None:
    validate_tool_registry()
    validate_toolbar_item_registry()
    spec = get_tool_spec(TOOL_VOLUME_MEASURE)
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert spec.panel_index == 14
    assert spec.button_attr == "btn_tool_volume_measure"
    assert get_tool_panel_spec(TOOL_VOLUME_MEASURE) is not None
    toolbar = get_toolbar_item_spec("tool:volume_measure")
    assert toolbar is not None
    assert toolbar.tool_id == TOOL_VOLUME_MEASURE
    assert toolbar.code == "VOL"
