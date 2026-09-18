# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.ui.floor_grid_model import FLOOR_GRID_MAJOR_EVERY, floor_grid_layers, floor_grid_plan


def test_floor_grid_plan_always_includes_origin_even_for_offset_scene() -> None:
    plan = floor_grid_plan((240.0, 260.0, -30.0, -10.0, 5.0, 30.0), requested_step=10.0)

    assert plan["xmin"] <= 0.0 <= plan["xmax"]
    assert plan["ymin"] <= 0.0 <= plan["ymax"]
    assert plan["xmin"] <= 240.0 and plan["xmax"] >= 260.0
    assert plan["ymin"] <= -30.0 and plan["ymax"] >= -10.0


def test_floor_grid_layers_separate_minor_major_axes_and_origin_marker() -> None:
    _plan, layers = floor_grid_layers((-20.0, 20.0, -20.0, 20.0, 0.0, 10.0), requested_step=10.0)

    assert layers["minor"]
    assert layers["major"]
    assert len(layers["axis_x"]) == 1
    assert len(layers["axis_y"]) == 1
    assert len(layers["origin"]) >= 38

    # The axes must not be duplicated as ordinary major/minor grid lines.
    assert all(line[0][1] != 0.0 or line[1][1] != 0.0 for line in layers["major"])
    assert all(line[0][0] != 0.0 or line[1][0] != 0.0 for line in layers["major"])


def test_floor_grid_keeps_major_step_as_every_fifth_visible_minor_line() -> None:
    plan = floor_grid_plan((-10.0, 10.0, -10.0, 10.0, -1.0, 1.0), requested_step=10.0)

    assert plan["major_step"] == plan["step"] * FLOOR_GRID_MAJOR_EVERY
    assert plan["origin_radius"] >= 4.0
