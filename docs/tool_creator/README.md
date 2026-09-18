# Tool Creator API

This folder documents the public API intended for people who create tools for LaserProg Studio without knowing the historical Qt/PyVista internals.

The preferred import paths are now grouped by domain:

```python
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, register_tool, require_tool_api
from laserprog_studio.tool_api.scene import actors, interaction, snap
from laserprog_studio.tool_api.visual import inspector
```

Start with `00_external_tool_quickstart.md` if you are building a tool from outside the project. See `00_api_map.md` for the complete public surface map and `00_creator_ui_direction.md` for the viewport UI/Gizmo source-of-truth rule.

A creator tool should use these blocks:

| Block | Purpose | Public entry point |
|---|---|---|
| Registration | Make the tool visible to the app and toolbar/palette | `register_tool(...)` |
| Lifecycle | Open, close, receive events, cleanup | `CreatorTool`, `ToolContext.cleanup_tool(...)` |
| Input | Normalized mouse/keyboard/drag events | `ToolEvent` |
| Actors | Register selectable/grabbable viewport objects | `actors.point`, `actors.line`, `ctx.actors`, `ctx.actor_registry(...)` |
| Scene cache | Rebuild/read cached snap data from scene, sketch and UI actors | `ctx.scene_cache` |
| Smart snap | Snap to grid, sketch, scene, tool actors, UI and temporary targets | `ctx.snap.smart(...)` |
| Preview/Gizmos/Overlay | Temporary visual feedback in the viewport, using official styles/motifs | `ctx.preview`, `ctx.gizmos`, `ctx.overlay`, official `actors.*` styles and `tool_api.gizmos.iter_creator_ui_families()` |
| Projected drawing 2D | Non-interactive world points, lines and faces rendered as persistent screen-space batches | `tool_api.projected_drawing`, `ctx.projected_drawing.for_tool(...)` |
| Gizmo catalog | Focused viewer for the non-interactive projected drawing 2D API | `tool_api.projected_drawing`, `ctx.projected_drawing.for_tool(...)` |
| Inspector | Add controls in the right Tool area without writing Qt; optionally request native debounced AutoPreview | `ctx.inspector.set_panel(...)`, `inspector.auto_preview(...)` |
| Document | Read and mutate scene meshes without touching ModelStore/MainWindow | `ctx.document` |
| Scene selection | Read/set selected scene objects, separate from tool actors | `ctx.scene_selection` |
| Picking | Object/face/edge/vertex/ray picking façade | `ctx.pick` |
| Preview sessions | Preview/apply/cancel workflows for modifiers | `ctx.preview_session.start(...)` |
| Operations | Register/run previewable mesh operations | `ctx.operations` |
| Jobs/Status | Progress, warnings, reports, deterministic job wrapper | `ctx.jobs`, `ctx.status` |
| Commands | Undoable actions and grouped transactions | `ctx.commands.do(...)`, `ctx.commands.transaction(...)` |
| Diagnostics | Living examples and regression checks | Tool Core Diagnostic |

The important rule is simple: a new tool should not directly import the main window, PySide widgets, PyVista actors, Tool Core Analysis internals or old controllers unless the public API is missing something. Tool Core Analysis remains the source of truth for interactive Creator motifs. The Gizmo catalog is now reserved for the separate projected drawing 2D renderer.

## Minimal shape

A normal external tool declares actors and lets the native runtime handle viewport interaction. No mouse drag state machine is needed for hover/select/grab.

```python
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, register_tool, require_tool_api
from laserprog_studio.tool_api.scene import actors
from laserprog_studio.tool_api.visual import inspector


TOOL_ID = "com.example.my_tool"
require_tool_api("0.13.0", max_major=0)
TOOL_MANIFEST = ToolManifest(id=TOOL_ID, label="My Tool", entrypoint="my_package.my_tool:create_tool", api_min="0.13.0")


class MyTool(CreatorTool):
    id = TOOL_ID
    label = "My Tool"

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.panel(
                "My Tool",
                id=self.id,
                owner_tool=self.id,
                sections=[
                    inspector.section("Geometry", [
                        inspector.float_field("width", "Width", default=20.0, unit="mm"),
                    ]),
                ],
            )
        )
        ctx.actor_registry(self.id).add(
            actors.point("p1", (0, 0, 0), interaction="grabbable", point_style="target")
        )


def create_tool() -> MyTool:
    return MyTool()


EXTENSION = register_tool(
    id=TOOL_ID,
    label="My Tool",
    runtime=create_tool(),
    toolbar_code="MYT",
    toolbar_visibility="palette",
)
```

`CreatorStudioToolAdapter` is inserted by `register_tool(...)` for `CreatorTool` runtimes. It runs the optimized native Creator UI policy before `on_event`, so the tool does not call any low-level interaction or refresh helper. The same native boundary applies to light-tool AutoPreview and overlays: declare `auto_preview=inspector.auto_preview(...)` on the panel when wanted, declare floating UI through `ctx.overlay`, and let the runtime debounce, clean up and synchronise widgets.

The root `laserprog_studio.tool_api` import remains available as a stable aggregate import, but new tools should prefer the grouped domains.

The capitalised forms (`inspector.Panel`, `inspector.Section`, `inspector.FloatField`, ...) remain available. The lower-case helpers are the recommended style for external tools because they accept lists and read like a small declaration language.

## Interaction contract

Actors expose one of three interaction modes. For `CreatorTool` runtimes registered through `register_tool(...)`, the standard hover/select/grab state machine is automatic and runs before the tool receives `on_event`. It returns camera gestures to the host when the pointer is not on a tool actor, and it clears the tool selection on an empty click without treating an empty camera drag as a click.

Actors expose one of three interaction modes:

| Mode | Can select | Can move | Typical use |
|---|---:|---:|---|
| `fixed` | no | no | Guides, decorations, locked references |
| `selectable` | yes | no | Lines, constraints, reference geometry |
| `grabbable` | yes | yes, after selection | Points, handles, editable vertices |

`grabbable` intentionally means “selectable first, movable second”. This prevents accidental moves and keeps multi-selection behavior predictable.

## Current complete example

See:

```text
examples/tool_creator/creator_api_demo_tool.py
```

It covers the full public path: declarative inspector, actors, `SceneCache`, classic smart snap, custom world targets, UI snap targets and undoable commands.

## Pass124 safety rules

Smart snap sources are explicit:

- tool actors use `TOOL_ACTOR_POINT` / `TOOL_ACTOR_EDGE`;
- persistent construction guides use `TOOL_TEMP_POINT` / `TOOL_TEMP_EDGE`;
- real screen-space overlays/gizmos use `UI_POINT` / `UI_EDGE`.

Use `ctx.scene_cache.add_point(..., owner_tool=self.id)` for persistent construction targets and `ctx.scene_cache.clear_tool_targets(self.id)` or `tool.close(ctx)` to clean them.


## Pass125 professional contract

Pass125 adds API versioning, external-tool manifests, public API exceptions, an actor registry and dynamic inspector field states.

Recommended new-tool rules:

- call `require_tool_api("0.13.0", max_major=0)` near the top of the tool module;
- expose a `ToolManifest`;
- use `ctx.actor_registry(self.id)` instead of writing directly to `ctx.selection`;
- use `ctx.inspector.set_enabled`, `set_visible`, `set_readonly` and `set_error` for dynamic panels;
- run `tool_api.audit.assert_no_forbidden_imports(...)` on external examples/plugins.

See `docs/pass125_professional_creator_api.md` for details.


## Native styles

See `12_native_interaction_styles.md` for point, line and interaction visual style ids.

## Creator UI direction

See `00_creator_ui_direction.md` before adding interactive viewport UI/Gizmos. Validate those visuals in Tool Core Analysis and expose approved motifs through `tool_api.ui_motifs`. The Gizmo catalog no longer hosts that motif vocabulary; it is dedicated to the projected drawing 2D renderer. Persistent hover/drag refresh, camera-axis orientation and field-of-view scale remain API/renderer responsibilities.

## Gizmo catalog

See `16_gizmo_catalog_tool.md` for the built-in viewer made exclusively from projected 2D points, lines and faces.

## Projected drawing 2D

See `21_projected_drawing_2d.md` for the render-only world-to-screen API used exclusively by the Gizmo Catalog and intended for incremental Plan Tracer migration.

## Plan tracer 2D

See `17_plan_tracer_2d.md` for the rebuilt Plan tracer foundation. It demonstrates the official locked-plane drawing path: camera-oriented plane height picking, a draggable overlay toolbox, a `diamond` cursor, `minimal dot` point placement and API-owned smart snap/performance.


## Folding

See `23_folding_tool.md` for the five-step mesh deformation tool. It demonstrates free-camera face picking, projected curve handles, vectorized mesh deformation, preview/apply/cancel semantics and editable generated geometry without direct Qt/VTK/PyVista dependencies.

## Performance contract

See `19_performance_contract.md` before building a tool with hover, snap, drag, previews or scene-cache access. It documents the anti-footguns found during the Plan Tracer 2D audit: idempotent document binding, stable viewport projection functions, structural vs transient cache invalidation, and the safe Creator UI refresh paths.

- [20 - Editable generated geometry](20_editable_generated_geometry.md)
- [22 — Selection context menu](22_selection_context_menu.md)

## Cloth

See `24_cloth_tool.md` for the integrated piecewise-planar 3D textile-surface Creator, its state machines, shared tracing contracts, linked flat-pattern output, V1 restrictions and regression strategy.
