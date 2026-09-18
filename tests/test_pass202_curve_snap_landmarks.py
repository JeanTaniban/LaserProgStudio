from __future__ import annotations

import math

from laserprog_studio.tool_api import snap
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.snap import SnapKind, SnapSource


def test_snap_api_expands_circle_to_center_quadrant_and_angle_landmarks() -> None:
    ctx = ToolContext()
    target = snap.circle(
        "circle.a",
        (10.0, 10.0, 0.0),
        5.0,
        source=SnapSource.CUSTOM_CURVE,
        priority=65,
        metadata={"include_angle_snap": True, "angle_step_degrees": 45.0},
    )

    center = ctx.snap.smart((10.0, 10.0, 0.0), (10.0, 10.0), ctx, extra_targets=[target])
    assert center.snapped is True
    assert center.kind == SnapKind.CENTER
    assert center.source == SnapSource.CENTER
    assert center.source_id == "circle.a:center"

    quadrant = ctx.snap.smart((15.0, 10.0, 0.0), (15.0, 10.0), ctx, extra_targets=[target])
    assert quadrant.snapped is True
    assert quadrant.kind == SnapKind.QUADRANT
    assert quadrant.metadata["angle_degrees"] == 0.0
    assert quadrant.position == (15.0, 10.0, 0.0)

    angle_pos = (10.0 + 5.0 / math.sqrt(2.0), 10.0 + 5.0 / math.sqrt(2.0), 0.0)
    angle = ctx.snap.smart(angle_pos, angle_pos[:2], ctx, extra_targets=[target])
    assert angle.snapped is True
    assert angle.kind == SnapKind.ANGLE
    assert angle.label == "Angle"
    assert angle.metadata["angle_degrees"] == 45.0


def test_circle_curve_snap_still_returns_edge_when_no_landmark_is_near() -> None:
    ctx = ToolContext()
    target = snap.circle("circle.edge", (0.0, 0.0, 0.0), 10.0, source=SnapSource.CUSTOM_CURVE)

    result = ctx.snap.smart((6.0, 8.0, 0.0), (6.0, 8.0), ctx, extra_targets=[target])

    assert result.snapped is True
    assert result.kind == SnapKind.EDGE
    assert result.source == SnapSource.CUSTOM_CURVE
    assert result.metadata["curve_type"] == "circle"
    assert result.position == (6.0, 8.0, 0.0)


def test_plan_2d_snap_cursor_has_api_owned_angle_style() -> None:
    style = plan2d.snap_cursor_style_for_kind(SnapKind.ANGLE)

    assert style.label == "Angle"
    assert style.show_label is True
    assert style.point_style == "chevron"
