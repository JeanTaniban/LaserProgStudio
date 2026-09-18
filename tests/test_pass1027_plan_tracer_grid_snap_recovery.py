from __future__ import annotations

from laserprog_studio.planar_tools import make_locked_plane, plane_to_world, world_to_plane
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tool_core import ToolContext


class _PlaneViewport:
    def __init__(self, plane):
        self.plane = plane

    def world_to_screen(self, world):
        u, v = world_to_plane(self.plane, world)
        return (float(u), float(v))


def _ctx_with_grid(plane, size: float) -> ToolContext:
    ctx = ToolContext()
    ctx.viewport = _PlaneViewport(plane)
    ctx.snap.set_smart_snap(False)
    ctx.snap.set_grid_snap(True)
    ctx.snap.grid_provider.enabled = True
    ctx.snap.grid_provider.grid_size = float(size)
    return ctx


def test_plan2d_grid_snap_is_plane_local_on_locked_side_face() -> None:
    plane = make_locked_plane("front", depth=-20.75)
    ctx = _ctx_with_grid(plane, 5.0)
    candidate = plane_to_world(plane, 12.2, 7.6)

    result = plan2d.smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace",
        plane=plane,
        candidate_world=candidate,
        screen_pos=(12.2, 7.6),
        rebuild_cache=False,
    )

    assert result.snapped is True
    assert result.kind == "grid"
    assert tuple(round(v, 6) for v in world_to_plane(plane, result.world_pos)) == (10.0, 10.0)


def test_plan2d_grid_snap_ignores_far_huge_persisted_grid() -> None:
    plane = make_locked_plane("top", depth=20.75)
    ctx = _ctx_with_grid(plane, 100000.0)
    candidate = plane_to_world(plane, 32.204956, 44.021988)

    result = plan2d.smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace",
        plane=plane,
        candidate_world=candidate,
        screen_pos=(32.204956, 44.021988),
        rebuild_cache=False,
    )

    assert result.snapped is False
    assert result.kind == "free"
    assert tuple(round(v, 6) for v in result.world_pos) == tuple(round(v, 6) for v in candidate)
