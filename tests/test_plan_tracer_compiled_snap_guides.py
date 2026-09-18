from types import SimpleNamespace

from laserprog_studio.planar_tools import PlanarToolConfig, compile_planar_snap_cache, make_locked_plane, snap_plane_point
from laserprog_studio.tool_api.plan2d.snap import smart_snap_on_plan
from laserprog_studio.tool_core.scene_cache import SceneCache
from laserprog_studio.tool_core.snap import SnapManager
from laserprog_studio.tool_core.snap.types import SnapSource


class CountingViewport:
    def __init__(self):
        self.calls = 0

    def world_to_screen(self, point):
        self.calls += 1
        return (float(point[0]), float(point[1]))


def test_compiled_planar_snap_cache_keeps_distant_axis_alignment():
    cache = compile_planar_snap_cache(
        [(100.0, 1000.0), (-250.0, -400.0)],
        [((0.0, 0.0), (1000.0, 0.0))],
    )

    snapped, label = snap_plane_point(
        (100.45, 12.0),
        PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=True, smart_snap_tolerance=1.0, smart_snap_priority=True),
        compiled_cache=cache,
    )

    assert snapped == (100.0, 12.0)
    assert label == "smart U"


def test_plan2d_api_snap_uses_cached_guides_without_losing_distant_alignment():
    scene_cache = SceneCache()
    for index in range(1600):
        scene_cache.add_point(f"far-{index}", (1000.0 + index * 10.0, 10000.0, 0.0), source=SnapSource.MESH_VERTEX.value)
    scene_cache.add_point("align-x", (500.0, 10000.0, 0.0), source=SnapSource.MESH_VERTEX.value)
    scene_cache.valid = True
    viewport = CountingViewport()
    ctx = SimpleNamespace(scene_cache=scene_cache, viewport=viewport, snap=SnapManager())
    plane = make_locked_plane("top")

    first = smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace_2d",
        plane=plane,
        candidate_world=(500.4, 20.0, 0.0),
        screen_pos=(500.4, 20.0),
        rebuild_cache=False,
    )
    assert first.snapped
    assert first.world_pos == (500.0, 20.0, 0.0)
    assert first.label == "Align U"

    viewport.calls = 0
    second = smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace_2d",
        plane=plane,
        candidate_world=(500.3, 30.0, 0.0),
        screen_pos=(500.3, 30.0),
        rebuild_cache=False,
    )
    assert second.snapped
    assert second.world_pos == (500.0, 30.0, 0.0)
    assert viewport.calls < 50
