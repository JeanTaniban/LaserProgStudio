"""Minimal creator-tool example for the public Tool API.

This file is intentionally headless-testable: it uses ToolContext, declarative
actors, SceneCache, smart snap and the inspector manager without importing Qt.
"""
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, require_tool_api
from laserprog_studio.tool_api.scene import actors, snap
from laserprog_studio.tool_api.visual import inspector

TOOL_ID = "example.minimal_point_line"
require_tool_api("0.13.0", max_major=0)
TOOL_MANIFEST = ToolManifest(
    id=TOOL_ID,
    label="Minimal Point Line",
    entrypoint="examples.tool_creator.minimal_point_line_tool:create_tool",
    api_min="0.13.0",
    description="Minimal headless example for the creator API.",
)


@dataclass(slots=True)
class MinimalPointLineTool(CreatorTool):
    """Two grabbable points connected by one selectable line."""

    id: str = TOOL_ID
    label: str = "Minimal Point Line"

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.Panel(
                id=self.id,
                owner_tool=self.id,
                title="Minimal Point Line",
                description="Move two points and keep the line selectable.",
                sections=(
                    inspector.Section(
                        "Geometry",
                        (
                            inspector.FloatField("length", "Length", default=50.0, min_value=0.0, unit="mm"),
                            inspector.BoolField("snap", "Smart snap", default=True),
                        ),
                    ),
                    inspector.Section("Actions", (inspector.Button("reset", "Reset"), inspector.Button("apply", "Apply"))),
                ),
            )
        )
        self._register_default_actors(ctx)
        ctx.scene_cache.rebuild(ctx, scope="snap")

    def reset(self, ctx: ToolContext) -> None:
        ctx.actors.clear(owner_tool=self.id)
        self._register_default_actors(ctx)
        ctx.scene_cache.rebuild(ctx, scope="snap")

    def smart_snap(self, ctx: ToolContext, world_pos: tuple[float, float, float], screen_pos: tuple[float, float]):
        length = float(ctx.inspector.value("length", 50.0))
        return ctx.snap.smart(
            world_pos,
            screen_pos,
            ctx,
            extra_targets=[snap.point("demo.midpoint", (length * 0.5, 0.0, 0.0), priority=10)],
        )

    def _register_default_actors(self, ctx: ToolContext) -> None:
        length = float(ctx.inspector.value("length", 50.0))
        start = (0.0, 0.0, 0.0)
        end = (length, 0.0, 0.0)
        registry = ctx.actor_registry(self.id)
        registry.add(actors.point("demo.p1", start, interaction="grabbable", point_style="target"))
        registry.add(actors.point("demo.p2", end, interaction="grabbable", point_style="target"))
        registry.add(actors.line("demo.edge", start, end, interaction="selectable", line_style="selectable"))


def create_tool() -> MinimalPointLineTool:
    return MinimalPointLineTool()
