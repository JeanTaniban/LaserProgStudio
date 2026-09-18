# 01 - Create a tool

Use `laserprog_studio.tool_api.register_tool` as the high-level registration entry point.

For new external-style tools, the runtime should be a `CreatorTool`. `register_tool(...)` wraps it in `CreatorStudioToolAdapter`, which runs the native Creator UI runtime before tool code. That is what makes hover/select/grab, fast drag rendering, empty-click selection clearing and camera-facing UI behaviour automatic.

```python
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, register_tool, require_tool_api
from laserprog_studio.tool_api.scene import actors

TOOL_ID = "minimal_point_line"
require_tool_api("0.13.0", max_major=0)

TOOL_MANIFEST = ToolManifest(
    id=TOOL_ID,
    label="Minimal Point Line",
    entrypoint="my_plugin.minimal_point_line:create_tool",
    api_min="0.13.0",
)


class MinimalPointLineTool(CreatorTool):
    id = TOOL_ID
    label = "Minimal Point Line"

    def on_open(self, ctx: ToolContext) -> None:
        registry = ctx.actor_registry(self.id)
        registry.add(actors.point("p1", (0, 0, 0), interaction="grabbable", point_style="target"))
        registry.add(actors.point("p2", (50, 0, 0), interaction="grabbable", point_style="target"))
        registry.add(actors.line("edge", (0, 0, 0), (50, 0, 0), interaction="selectable"))
        ctx.scene_cache.rebuild(ctx, scope="snap")


def create_tool() -> MinimalPointLineTool:
    return MinimalPointLineTool()


extension = register_tool(
    id=TOOL_ID,
    label="Minimal Point Line",
    runtime=create_tool(),
    toolbar_code="MPL",
    description="Edit two points connected by a line.",
    panel_index=910,
    toolbar_visibility="palette",
)
```

The wrapper creates and registers both:

- a `ToolSpec`, used by the lifecycle/panel system;
- an optional `ToolbarItemSpec`, used by the toolbar and + Tools palette;
- a `CreatorStudioToolAdapter`, used by the native Creator UI runtime.

Use `toolbar_visibility="toolbar"` only for tools that should appear in the default top toolbar. Use `"palette"` for tools discoverable through the palette without occupying a default toolbar slot. Use `"hidden"` for internal tests and diagnostics.

## Recommended lifecycle base

For new tools, prefer `CreatorTool`:

```python
from laserprog_studio.tool_api.core import CreatorTool

class MyTool(CreatorTool):
    id = "com.example.my_tool"
    label = "My Tool"

    def on_open(self, ctx):
        ...

    # Optional. Actor hover/select/grab is already handled before this is called.
    def on_event(self, event, ctx):
        return False
```

Call `tool.close(ctx)` when the tool is deactivated. It automatically calls `ctx.cleanup_tool(tool.id)`, which removes tool-owned actors, previews, gizmos, overlays, inspector panels and temporary snap targets.

The manual equivalent is:

```python
ctx.cleanup_tool(self.id)
```

## Native interaction rule

A production Creator tool should not call these low-level functions from `on_event`:

```python
interaction.hover_select_grab_actors(...)
interaction.handle_native_creator_ui_event(...)
gizmos.refresh_creator_ui_interaction(...)
gizmos.refresh_creator_ui_drag(...)
gizmos.refresh_creator_ui_camera(...)
gizmos.refresh_creator_ui_motifs(...)
```

They are owned by the adapter/runtime and are available for diagnostics, tests and renderer bridges. A tool author declares `ToolActor` objects and official styles; the API chooses the optimized interaction and rendering path.

Use a raw `StudioTool` runtime only for internal tools that intentionally bypass the Creator API contract. External tools should not do that.
