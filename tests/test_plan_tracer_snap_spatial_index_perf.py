from types import SimpleNamespace

from laserprog_studio.tool_core.scene_cache import SceneCache
from laserprog_studio.tool_core.snap import SnapManager, SnapSource


class CountingViewport:
    def __init__(self):
        self.calls = 0

    def world_to_screen(self, point):
        self.calls += 1
        return (float(point[0]), float(point[1]))


def test_scene_snap_spatial_query_keeps_repeated_plan_tracer_moves_local():
    cache = SceneCache()
    for index in range(1600):
        cache.add_point(f"far-{index}", (10000.0 + index * 10.0, 10000.0, 0.0), source=SnapSource.MESH_VERTEX.value)
    cache.add_point("near", (20.0, 20.0, 0.0), source=SnapSource.MESH_VERTEX.value)
    cache.valid = True
    viewport = CountingViewport()
    ctx = SimpleNamespace(scene_cache=cache, viewport=viewport)
    manager = SnapManager()

    first = manager.smart((20.2, 20.1, 0.0), (20.2, 20.1), ctx, rebuild_cache=False)
    assert first.snapped
    assert first.source_id == "near"

    viewport.calls = 0
    second = manager.smart((20.3, 20.1, 0.0), (20.3, 20.1), ctx, rebuild_cache=False)
    assert second.snapped
    assert second.source_id == "near"
    assert viewport.calls < 80


def test_scene_snap_spatial_query_preserves_long_segment_hits():
    cache = SceneCache()
    cache.add_segment("long", (0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), source=SnapSource.MESH_EDGE.value)
    cache.valid = True
    viewport = CountingViewport()
    ctx = SimpleNamespace(scene_cache=cache, viewport=viewport)
    manager = SnapManager()

    result = manager.smart((500.0, 2.0, 0.0), (500.0, 2.0), ctx, rebuild_cache=False)
    assert result.snapped
    assert str(result.source_id).startswith("long")
