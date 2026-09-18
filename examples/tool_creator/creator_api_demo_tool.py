"""Complete headless creator-tool example.

It shows the preferred public API style after Pass124:

- declarative right-inspector panel;
- fixed/selectable/grabbable actors;
- SceneCache rebuild and exclusion;
- standard smart snap with tool-temp world and UI targets;
- undoable command.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, require_tool_api
from laserprog_studio.tool_api.scene import actors, snap
from laserprog_studio.tool_api.visual import inspector

TOOL_ID = "example.creator_api_demo"
require_tool_api("0.5.0", max_major=0)
TOOL_MANIFEST = ToolManifest(
    id=TOOL_ID,
    label="Creator API Demo",
    entrypoint="examples.tool_creator.creator_api_demo_tool:create_tool",
    api_min="0.5.0",
    description="Complete headless demo for the professional creator API contract.",
)


@dataclass(slots=True)
class CreatorApiDemoTool(CreatorTool):
    id: str = TOOL_ID
    applied: list[str] = field(default_factory=list)

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.panel(
                "Creator API Demo",
                id=self.id,
                owner_tool=self.id,
                description="External-tool friendly API demo.",
                sections=[
                    inspector.section(
                        "Geometry",
                        [
                            inspector.float_field("length", "Length", default=80.0, min_value=5.0, max_value=500.0, unit="mm"),
                            inspector.bool_field("snap", "Smart snap", default=True),
                            inspector.choice_field("mode", "Mode", default="line", choices=[("line", "Line"), ("guide", "Guide")]),
                        ],
                    ),
                    inspector.section(
                        "Actions",
                        [
                            inspector.button("reset", "Reset", on_click=lambda _event: self.reset(ctx)),
                            inspector.button("apply", "Apply", on_click=lambda _event: self.apply(ctx)),
                        ],
                    ),
                ],
            )
        )
        self.reset(ctx)

    def reset(self, ctx: ToolContext) -> None:
        length = float(ctx.inspector.value("length", 80.0))
        registry = ctx.actor_registry(self.id)
        registry.clear()
        registry.add(actors.point("creator_demo.origin", (0.0, 0.0, 0.0), interaction="fixed"))
        registry.add(actors.point("creator_demo.a", (0.0, 10.0, 0.0), interaction="grabbable"))
        registry.add(actors.point("creator_demo.b", (length, 10.0, 0.0), interaction="grabbable"))
        registry.add(actors.line("creator_demo.edge", (0.0, 10.0, 0.0), (length, 10.0, 0.0), interaction="selectable"))
        ctx.scene_cache.rebuild(ctx, scope="snap")

    def snap_cursor(self, ctx: ToolContext, world_pos: tuple[float, float, float], screen_pos: tuple[float, float]):
        length = float(ctx.inspector.value("length", 80.0))
        return ctx.snap.smart(
            world_pos,
            screen_pos,
            ctx,
            exclude_ids=ctx.selection.ids(),
            extra_targets=[
                snap.tool_point("creator_demo.midpoint", (length * 0.5, 10.0, 0.0), priority=10, owner_tool=self.id),
                snap.ui_point("creator_demo.overlay_crosshair", screen_pos, world_pos=world_pos, priority=12),
            ],
        )

    def apply(self, ctx: ToolContext) -> None:
        def do() -> None:
            self.applied.append("apply")

        def undo() -> None:
            if self.applied:
                self.applied.pop()

        ctx.commands.do("creator-demo-apply", do=do, undo=undo)


def create_tool() -> CreatorApiDemoTool:
    return CreatorApiDemoTool()
