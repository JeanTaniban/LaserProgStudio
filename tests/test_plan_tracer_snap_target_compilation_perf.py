from types import SimpleNamespace

from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tool_core.snap import SnapManager


class CountingViewport:
    def __init__(self):
        self.calls = 0

    def world_to_screen(self, point):
        self.calls += 1
        return (float(point[0]), float(point[1]))


def _tool_with_grid_of_segments(count: int = 80):
    tool = PlanTrace2DCreatorTool()
    plane = make_locked_plane("top")
    tool._state.plane = plane
    tool._state.display_plane = plane
    for i in range(count):
        a = tool._state.sketch.add_point((float(i) * 10.0, 0.0), point_id=f"p{i}a")
        b = tool._state.sketch.add_point((float(i) * 10.0, 50.0), point_id=f"p{i}b")
        tool._state.sketch.add_line(a.id, b.id, line_id=f"l{i}")
    tool._state.points = [
        (point.id, tool._services.coordinates.sketch_xy_to_semantic_world(point.position))
        for point in tool._state.sketch.points.values()
    ]
    return tool


def test_plan_trace_exact_snap_uses_screen_index_but_full_alignment_targets_remain_available():
    tool = _tool_with_grid_of_segments(120)
    ctx = SimpleNamespace(viewport=CountingViewport())

    full = tool._services.snap_targets._live_snap_targets(ctx)
    near = tool._services.snap_targets._live_snap_targets_near(ctx, (0.0, 0.0))

    assert len(full) > len(near)
    assert any(target.id == "p119a" for target in full)
    assert not any(target.id == "p119a" for target in near)

    # A second nearby query reuses the compiled screen index instead of projecting
    # every target again.
    ctx.viewport.calls = 0
    tool._services.snap_targets._live_snap_targets_near(ctx, (1.0, 1.0))
    assert ctx.viewport.calls < 20


def test_plan2d_alignment_uses_full_extra_target_cache_while_exact_snap_is_local():
    from laserprog_studio.tool_api import plan2d
    from laserprog_studio.tool_core.scene_cache import SceneCache

    tool = _tool_with_grid_of_segments(140)
    ctx = SimpleNamespace(viewport=CountingViewport(), scene_cache=SceneCache(), snap=SnapManager())
    ctx.scene_cache.valid = True
    plane = tool._state.display_plane
    assert plane is not None

    near = tool._services.snap_targets._live_snap_targets_near(ctx, (500.4, 20.0))
    full = tool._services.snap_targets._live_snap_targets(ctx)
    assert len(full) > len(near)

    snap = plan2d.smart_snap_on_plan(
        ctx,
        owner_tool=tool.id,
        plane=plane,
        candidate_world=(1190.4, 20.0, 0.0),
        screen_pos=(1190.4, 20.0),
        extra_targets=near,
        extra_alignment_targets=full,
        rebuild_cache=False,
    )

    assert snap.snapped
    assert snap.world_pos == (1190.0, 20.0, 0.0)
    assert snap.label == "Align U"

    near2 = tool._services.snap_targets._live_snap_targets_near(ctx, (1189.8, 30.0))
    ctx.viewport.calls = 0
    plan2d.smart_snap_on_plan(
        ctx,
        owner_tool=tool.id,
        plane=plane,
        candidate_world=(1189.8, 30.0, 0.0),
        screen_pos=(1189.8, 30.0),
        extra_targets=near2,
        extra_alignment_targets=full,
        rebuild_cache=False,
    )
    assert ctx.viewport.calls < 50


def test_drag_snap_targets_stay_frozen_while_dragged_sketch_points_mutate(monkeypatch):
    tool = _tool_with_grid_of_segments(32)
    ctx = SimpleNamespace(viewport=CountingViewport())
    service = tool._services.snap_targets

    service._begin_drag_snap_cache(ctx, exclude_ids=("p5a",))
    frozen = service._live_snap_targets(ctx)
    assert frozen
    assert not any(target.id == "p5a" for target in frozen)
    old_world = next(target.world_pos for target in frozen if target.id == "p6a")

    point = tool._state.sketch.points["p6a"]
    point.position = (9999.0, 8888.0)
    tool._state.points = [
        (item.id, tool._services.coordinates.sketch_xy_to_semantic_world(item.position))
        for item in tool._state.sketch.points.values()
    ]

    def _fail_rebuild(_ctx):  # pragma: no cover - failure path validated by assertion
        raise AssertionError("drag snap cache should not rebuild during mouse moves")

    monkeypatch.setattr(service, "_build_live_snap_targets", _fail_rebuild)
    full_after_mutation = service._live_snap_targets(ctx)
    near_after_mutation = service._live_snap_targets_near(ctx, (60.0, 0.0))

    assert next(target.world_pos for target in full_after_mutation if target.id == "p6a") == old_world
    assert any(target.id == "p6a" for target in near_after_mutation)
    service._end_drag_snap_cache()
