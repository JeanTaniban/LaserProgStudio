# -*- coding: utf-8 -*-
from __future__ import annotations

import math

import numpy as np
import pytest

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.folding.geometry import (
    arbitrary_face_plane,
    deform_vertices,
    resample_shape_angles,
    sample_curve,
    shape_handle_points,
)
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingMode, FoldingPhase
from laserprog_studio.tooling.folding.serialization import attach_folding_source, restore_folding_source
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool


def _plane():
    return arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def _curve(*, shape=(90.0, -120.0, 90.0), angle=90.0):
    return FoldingCurve(
        start=(0.0, 0.0, 0.0),
        end=(10.0, 0.0, 0.0),
        mode=FoldingMode.LIVING_HINGE.value,
        fold_angle_deg=angle,
        shape_angles_deg=tuple(shape),
    )


def _mesh() -> WorkMesh:
    return WorkMesh(
        name="complex living hinge",
        vertices=[
            (-4.0, -2.0, 0.0), (-4.0, 2.0, 0.0),
            (2.5, -2.0, 0.0), (2.5, 2.0, 0.0),
            (5.0, -2.0, 0.0), (5.0, 2.0, 0.0),
            (7.5, -2.0, 0.0), (7.5, 2.0, 0.0),
            (12.0, -2.0, 0.0), (12.0, 2.0, 0.0),
            (16.0, -2.0, 1.0), (16.0, 2.0, 1.0),
        ],
        triangles=[(0, 2, 1), (1, 2, 3), (2, 4, 3), (3, 4, 5), (4, 6, 5), (5, 6, 7), (6, 8, 7), (7, 8, 9)],
    )


def test_custom_profile_can_create_an_s_curve_and_keeps_neutral_length() -> None:
    curve = _curve()
    points = sample_curve(_plane(), curve, count=10_001)
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    assert length == pytest.approx(10.0, rel=2.0e-10, abs=2.0e-10)

    segments = np.diff(np.asarray(points), axis=0)
    angles = np.unwrap(np.arctan2(segments[:, 2], segments[:, 0]))
    curvature = np.diff(angles)
    assert np.any(curvature > 1.0e-5)
    assert np.any(curvature < -1.0e-5)


def test_complex_profile_still_moves_the_outer_region_rigidly() -> None:
    source = [(-3.0, -2.0, 0.0), (-1.0, 3.0, 1.0), (12.0, -2.0, 0.0), (16.0, 3.0, 1.0)]
    result = deform_vertices(source, _plane(), _curve(shape=(100.0, -150.0, 80.0), angle=120.0))
    assert result[0] == pytest.approx(source[0], abs=1.0e-10)
    assert result[1] == pytest.approx(source[1], abs=1.0e-10)
    assert math.dist(result[2], result[3]) == pytest.approx(math.dist(source[2], source[3]), rel=1.0e-10, abs=1.0e-10)


def test_profile_detail_resampling_supports_one_to_seven_handles() -> None:
    values = (60.0, -40.0, 80.0)
    assert len(resample_shape_angles(values, 1)) == 1
    assert len(resample_shape_angles(values, 5)) == 5
    assert len(resample_shape_angles(values, 7)) == 7
    assert resample_shape_angles((0.0, 0.0, 0.0), 7) == pytest.approx((0.0,) * 7)


def test_complex_profile_round_trips_in_folding_metadata() -> None:
    mesh = _mesh()
    curve = _curve(shape=(35.0, -75.0, 120.0, -40.0, 15.0), angle=-105.0)
    folded = attach_folding_source(mesh, source_mesh=mesh, plane=_plane(), curve=curve)
    restored = restore_folding_source(folded)
    assert restored is not None
    assert restored[2].shape_angles_deg == pytest.approx(curve.shape_angles_deg)
    assert restored[2].fold_angle_deg == pytest.approx(-105.0)


def test_renderer_exposes_shape_handles_without_rebuilding_mesh() -> None:
    mesh = _mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    tool.session.target_object_id = mesh.mesh_id
    tool.session.target_index = 0
    tool.session.source_mesh = mesh
    tool.session.plane = _plane()
    tool.session.curve = _curve(shape=(0.0, 0.0, 0.0, 0.0, 0.0))
    tool.session.phase = FoldingPhase.ADJUST_CURVE
    tool._renderer.sync(ctx)

    ids = {item.id for item in ctx.projected_drawing.for_tool(tool.id).items()}
    assert {f"folding:shape:{index}" for index in range(1, 6)}.issubset(ids)
    assert "folding:angle" in ids
    assert len(shape_handle_points(_plane(), tool.session.curve)) == 5

    tool._on_value_changed(ctx, "folding_profile_detail", "7")
    assert tool.session.curve.shape_control_count == 7
    ids = {item.id for item in ctx.projected_drawing.for_tool(tool.id).items()}
    assert {f"folding:shape:{index}" for index in range(1, 8)}.issubset(ids)


def test_dragging_a_shape_handle_changes_only_the_lightweight_profile() -> None:
    mesh = _mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    tool.session.target_object_id = mesh.mesh_id
    tool.session.target_index = 0
    tool.session.source_mesh = mesh
    tool.session.plane = _plane()
    tool.session.curve = _curve(shape=(0.0, 0.0, 0.0))
    tool.session.phase = FoldingPhase.ADJUST_CURVE
    tool._renderer.sync(ctx)

    actor = ctx.selection.actor("folding:shape:2")
    assert actor is not None
    before = tool.session.curve.shape_angles_deg
    current = actor.points[0]
    ctx.selection.state.grabbed_ids = (actor.id,)
    ctx.viewport.screen_to_world_on_plane = lambda _screen, _plane: (current[0], current[1], current[2] + 2.0)

    from laserprog_studio.tool_core import ToolEvent, ToolEventType

    replacements = tool.resolve_drag_positions(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(20.0, 20.0)), ctx)
    assert replacements is not None and actor.id in replacements
    assert tool.session.curve.shape_angles_deg != before
    assert tool._preview is None  # no heavy mesh preview was rebuilt by the drag resolver
