# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter, CreatorTool


class _DummyCreator(CreatorTool):
    id = "dummy.creator"
    label = "Dummy Creator"


class _Plotter:
    def height(self) -> float:
        return 100.0


class _Owner:
    def __init__(self) -> None:
        self.plotter = _Plotter()

    def _world_to_display(self, world):
        return (float(world[0]), float(world[1]), float(world[2]))

    def _display_to_world_at_depth(self, x, y, depth):
        return (float(x), float(y), float(depth))


def test_pass1003_document_bind_same_target_is_cache_noop() -> None:
    ctx = ToolContext()
    scene = SimpleNamespace(meshes=[])

    ctx.document.bind(scene)
    first_version = ctx.scene_cache.version
    assert ctx.profiler.values["document.bind.changed_target"] == 1

    ctx.document.bind(scene)
    assert ctx.scene_cache.version == first_version
    assert ctx.profiler.values["document.bind.same_target"] == 1


def test_pass1003_creator_tool_context_reuses_viewport_projection_functions() -> None:
    owner = _Owner()
    scene = SimpleNamespace(meshes=[])
    context = SimpleNamespace(owner=owner, active_scene=scene, tool_context=None)
    adapter = CreatorStudioToolAdapter(
        ToolSpec(id="dummy.creator", label="Dummy", category="tool", panel_index=1),
        _DummyCreator(),
    )

    ctx = adapter.tool_context(context)
    world_to_screen = ctx.viewport.world_to_screen
    screen_to_world = ctx.viewport.screen_to_world_on_plane
    first_version = ctx.scene_cache.version

    ctx_again = adapter.tool_context(context)

    assert ctx_again is ctx
    assert ctx.viewport.world_to_screen is world_to_screen
    assert ctx.viewport.screen_to_world_on_plane is screen_to_world
    assert ctx.scene_cache.version == first_version
    assert ctx.profiler.values["creator.viewport_projection.install"] == 1
    assert ctx.profiler.values["creator.viewport_projection.reuse"] == 1
    assert ctx.profiler.values["document.bind.same_target"] == 1
