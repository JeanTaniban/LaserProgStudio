# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api import ToolContext
from laserprog_studio.tool_api.plan2d.actors import register_plan_cursor
from laserprog_studio.tool_api.plan2d.snap import _scene_plan2d_guide_cache


def _top_plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )


def test_pass1000_snap_screen_index_survives_non_structural_invalidation() -> None:
    ctx = ToolContext()
    ctx.scene_cache.add_segment("mesh.edge", (0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
    ctx.profiler.reset()

    first = ctx.scene_cache.snap_targets_near((10.0, 0.0), ctx)
    assert first
    assert ctx.profiler.counters["scene_cache.snap.rebuild_screen_index"].count == 1

    # Cursor/hover visual updates invalidate the broad scene cache, but they do
    # not change the snap target pool. This must not rebuild the screen grid.
    ctx.scene_cache.invalidate()
    second = ctx.scene_cache.snap_targets_near((12.0, 0.0), ctx)

    assert second
    assert ctx.profiler.counters["scene_cache.snap.rebuild_screen_index"].count == 1


def test_pass1000_plan2d_scene_guide_cache_survives_cursor_invalidation() -> None:
    ctx = ToolContext()
    ctx.scene_cache.add_point("mesh.vertex", (5.0, 7.0, 0.0))
    plane = _top_plane()
    ctx.profiler.reset()

    first = _scene_plan2d_guide_cache(ctx, plane)
    ctx.scene_cache.invalidate()
    second = _scene_plan2d_guide_cache(ctx, plane)

    assert first is second
    assert ctx.profiler.values["plan2d.guide_cache.scene.misses"] == 1
    assert ctx.profiler.values["plan2d.guide_cache.scene.hits"] == 1


def test_pass1000_plan2d_cursor_registration_does_not_invalidate_scene_snap_cache() -> None:
    ctx = ToolContext()
    ctx.scene_cache.add_point("mesh.vertex", (1.0, 2.0, 0.0))
    ctx.scene_cache.rebuild(ctx, scope="snap")
    version_before = ctx.scene_cache.version
    structure_before = ctx.scene_cache.snap_structure_signature()

    register_plan_cursor(
        ctx,
        owner_tool="plan.trace.2d",
        cursor_id="plan.trace.2d:cursor",
        world_pos=(3.0, 4.0, 0.0),
        visible=True,
        snap_kind="free",
        snapped=False,
    )

    assert ctx.scene_cache.valid is True
    assert ctx.scene_cache.version == version_before
    assert ctx.scene_cache.snap_structure_signature() == structure_before


class _JitteryCamera:
    def GetPosition(self):
        return (10.0, 20.0, 30.0)

    def GetFocalPoint(self):
        return (0.0, 0.0, 0.0)

    def GetViewUp(self):
        return (0.0, 1.0, 0.0)

    def GetClippingRange(self):
        return (0.1, 1000.0)

    def GetParallelScale(self):
        return 42.0

    def GetViewAngle(self):
        return 30.0

    def GetParallelProjection(self):
        return 1


class _JitteryPlotter:
    def __init__(self) -> None:
        self.camera = _JitteryCamera()
        self.window_size = (1024, 768)


class _JitteryOwner:
    def __init__(self) -> None:
        self.plotter = _JitteryPlotter()
        self.calls = 0

    def _world_to_display(self, point):
        # Simulate a live VTK projection that can jitter slightly after actor UI
        # updates even when the camera did not move. Cache keys must not depend
        # on these projected sentinel values.
        self.calls += 1
        return (float(point[0]) + self.calls * 0.01, float(point[1]), float(point[2]))


def _install_jittery_viewport(ctx: ToolContext) -> None:
    owner = _JitteryOwner()
    ctx.owner = owner

    def world_to_screen(world_pos):
        x, y_vtk, _z = owner._world_to_display(tuple(float(v) for v in world_pos))
        return (float(x), float(owner.plotter.window_size[1]) - float(y_vtk))

    ctx.viewport.world_to_screen = world_to_screen


def test_pass1001_scene_snap_screen_index_ignores_projection_jitter_without_camera_change() -> None:
    ctx = ToolContext()
    _install_jittery_viewport(ctx)
    ctx.scene_cache.add_segment("mesh.edge", (0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
    ctx.profiler.reset()

    first = ctx.scene_cache.snap_targets_near((10.0, 768.0), ctx)
    second = ctx.scene_cache.snap_targets_near((12.0, 768.0), ctx)

    assert first
    assert second
    assert ctx.profiler.counters["scene_cache.snap.rebuild_screen_index"].count == 1


def test_pass1001_plan_trace_snap_screen_index_ignores_projection_jitter_without_camera_change() -> None:
    from laserprog_studio.tool_core.snap.types import SnapTarget
    from laserprog_studio.tooling.plan_trace_2d.snap_targets import PlanTrace2DSnapTargetsService

    class _DummyTool:
        id = "plan.trace.2d"
        _state = object()
        _services = object()

    ctx = ToolContext()
    _install_jittery_viewport(ctx)
    service = PlanTrace2DSnapTargetsService(_DummyTool())
    targets = (SnapTarget.segment("edge", (0.0, 0.0, 0.0), (100.0, 0.0, 0.0)),)
    ctx.profiler.reset()

    first = service._near_targets_from_pool(ctx, targets, (10.0, 768.0))
    second = service._near_targets_from_pool(ctx, targets, (12.0, 768.0))

    assert first
    assert second
    assert ctx.profiler.counters["plan_trace.snap.build_screen_index"].count == 1


def test_pass1002_scene_snap_screen_index_ignores_dynamic_projection_callable_wrappers() -> None:
    """Real UI adapters can expose a new callable wrapper on every attribute read."""

    class _DynamicViewport:
        camera_revision = 1
        projection_revision = 1

        @property
        def world_to_screen(self):
            def _project(point):
                return (float(point[0]), float(point[1]))

            return _project

    ctx = ToolContext()
    ctx.viewport = _DynamicViewport()
    ctx.scene_cache.add_segment("mesh.edge", (0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
    ctx.profiler.reset()

    first = ctx.scene_cache.snap_targets_near((10.0, 0.0), ctx)
    second = ctx.scene_cache.snap_targets_near((12.0, 0.0), ctx)
    third = ctx.scene_cache.snap_targets_near((14.0, 0.0), ctx)

    assert first
    assert second
    assert third
    assert ctx.profiler.counters["scene_cache.snap.rebuild_screen_index"].count == 1


def test_pass1002_projection_signature_changes_when_explicit_view_revision_changes() -> None:
    class _DynamicViewport:
        def __init__(self) -> None:
            self.view_revision = 1

        @property
        def world_to_screen(self):
            def _project(point):
                return (float(point[0]), float(point[1]))

            return _project

    ctx = ToolContext()
    ctx.viewport = _DynamicViewport()
    ctx.scene_cache.add_segment("mesh.edge", (0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
    ctx.profiler.reset()

    ctx.scene_cache.snap_targets_near((10.0, 0.0), ctx)
    ctx.viewport.view_revision += 1
    ctx.scene_cache.snap_targets_near((12.0, 0.0), ctx)

    assert ctx.profiler.counters["scene_cache.snap.rebuild_screen_index"].count == 2
