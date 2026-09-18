# 00 - External tool quickstart

This is the start point for someone who does not know the LaserProg Studio internals.

A normal tool author should think in terms of **semantic objects**, not renderer details:

```text
register a CreatorTool
    ↓
declare ToolActors, inspector fields, previews and official gizmos
    ↓
let the native Creator runtime handle hover/select/grab, drag performance and camera-facing UI
```

## Minimal native tool

This tool has two grabbable points and one selectable line. It does not implement a mouse state machine. The native runtime handles hover, selection, grab, fast drag rendering, empty-click selection clearing, camera-axis orientation and field-of-view scaling.

```python
from dataclasses import dataclass

from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, register_tool, require_tool_api
from laserprog_studio.tool_api.scene import actors
from laserprog_studio.tool_api.visual import inspector

TOOL_ID = "example.native_two_points"
require_tool_api("0.13.0", max_major=0)

TOOL_MANIFEST = ToolManifest(
    id=TOOL_ID,
    label="Native Two Points",
    entrypoint="example.native_two_points:create_tool",
    api_min="0.13.0",
)


@dataclass(slots=True)
class NativeTwoPointsTool(CreatorTool):
    id: str = TOOL_ID
    label: str = "Native Two Points"

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.panel(
                "Native Two Points",
                id=self.id,
                owner_tool=self.id,
                sections=[
                    inspector.section("Geometry", [
                        inspector.float_field("length", "Length", default=50.0, unit="mm"),
                    ]),
                ],
            )
        )
        self.reset(ctx)

    def reset(self, ctx: ToolContext) -> None:
        length = float(ctx.inspector.value("length", 50.0))
        registry = ctx.actor_registry(self.id)
        registry.clear()
        registry.add(actors.point("a", (0.0, 0.0, 0.0), interaction="grabbable", point_style="target"))
        registry.add(actors.point("b", (length, 0.0, 0.0), interaction="grabbable", point_style="target"))
        registry.add(actors.line("edge", (0.0, 0.0, 0.0), (length, 0.0, 0.0), interaction="selectable"))
        ctx.scene_cache.rebuild(ctx, scope="snap")


def create_tool() -> NativeTwoPointsTool:
    return NativeTwoPointsTool()


EXTENSION = register_tool(
    id=TOOL_ID,
    label="Native Two Points",
    runtime=create_tool(),
    toolbar_code="NTP",
    toolbar_visibility="palette",
)
```

## What is automatic

When the tool is registered with a `CreatorTool` runtime, `CreatorStudioToolAdapter` runs the native Creator UI runtime before `on_event`. The tool author does not choose the repaint strategy.

Native means:

| Concern | Owner |
|---|---|
| hover state | API/runtime |
| selection and additive selection | API/runtime |
| grabbable actor drag | API/runtime |
| fast drag path | API/runtime |
| empty-click selection clearing | API/runtime |
| empty camera pan/orbit passthrough | API/runtime |
| camera-axis gizmo orientation | API/renderer |
| field-of-view pixel scale | API/renderer |
| Tool Core Analysis visual style | API/renderer |
| debounced AutoPreview from inspector edits | API/runtime |
| tool-owned overlay close/sync on exit | API/runtime |

## What a normal tool should not do

Do not write local code for these concerns in a production tool:

```python
# Do not call these from normal tool code.
interaction.hover_select_grab_actors(...)
interaction.handle_native_creator_ui_event(...)
gizmos.refresh_creator_ui_interaction(...)
gizmos.refresh_creator_ui_drag(...)
gizmos.refresh_creator_ui_camera(...)
gizmos.refresh_creator_ui_motifs(...)
ctx.gizmos.create_handle(...)  # low-level escape hatch only
```

Those functions remain public because diagnostics, tests, render adapters and the built-in Gizmo catalog need them. They are not the normal authoring path.

## Correct mental model

Use:

```python
actors.point(..., interaction="grabbable", point_style="target")
actors.line(..., interaction="selectable", line_style="selectable")
ctx.preview.show_line(..., line_style="guide")
ctx.gizmos.translate(...)
ctx.overlay.show_tooltip(...)
```

Avoid:

```python
# Wrong for a normal Creator tool.
# This creates a private UI language and bypasses the optimized native runtime.
custom_qt_widget_for_hover()
custom_pyvista_actor_for_handle()
my_tool_drag_state_machine()
rebuild_all_gizmos_on_mouse_move()
```

If the public API cannot express the visual you need, add the motif to Tool Core Analysis first, extract it into `tool_api.ui_motifs`, then use it through the API.

For light generators, request AutoPreview declaratively instead of wiring timers yourself:

```python
ctx.inspector.set_panel(
    inspector.panel(
        "Native Two Points",
        id=self.id,
        owner_tool=self.id,
        auto_preview=inspector.auto_preview(action_id="preview", debounce_ms=250),
        sections=[...],
    )
)
```

The runtime debounces inspector edits and triggers the normal `preview` action. Heavy tools should keep a manual Preview button or run through `ctx.jobs`.


## Native UI contract

The Creator UI runtime contract is `native_non_overridable`. Declare actors, interactions and official style ids; do not implement local hover/selection/grab, camera-facing orientation, FOV scale, or custom selected/grabbed colors. Minimal dots are a good sanity check: idle is blue, selected is yellow, grabbed/dragged is orange, and this feedback is resolved by the API/runtime.
