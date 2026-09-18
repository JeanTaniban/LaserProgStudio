# 00 - Creator UI direction

This document fixes the boundary between the diagnostic workbench, the public API and the built-in catalog.

The official flow is:

```text
Tool Core Analysis
    validates and optimizes visual motifs
        ↓
tool_api.ui_catalog / tool_api.ui_motifs
    exposes approved motifs as public API
        ↓
Gizmo catalog
    displays the public motifs with visibility toggles
        ↓
Creator tools
    reuse the public motifs instead of inventing local UI
```

## The confusion to avoid

There are two different things that looked similar but are not the same.

| Thing | Meaning | Must it draw UI? |
|---|---|---:|
| Catalog metadata | Names, labels, API entry points and recommendations for available UI families | no |
| Visual motifs | Actual actors, handles, previews, overlays and rendering policy extracted from Tool Core Analysis | yes |

A list such as `point_styles`, `line_styles` or `actor_interactions` is only metadata. It says what exists, but it does not prove the viewport will use the optimized Tool Core Analysis visuals.

The executable motif API is the important part:

```python
from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs

build_creator_ui_motifs(ctx, owner_tool=tool_id)
```

That call builds the official visual motifs through the public Creator API. The built-in **Gizmo catalog** must use that API. It must not construct a parallel demo scene.

The same rule applies to interaction and camera behaviour. Hover, selection, grab state, empty-click selection clearing, drag fast-path rendering, camera-axis orientation and field-of-view scaling are native API/runtime responsibilities. The runtime contract is exported as `CREATOR_UI_RUNTIME_CONTRACT = "native_non_overridable"`: tool authors can declare actors and official style ids, but they cannot opt out of the optimized interaction path or replace selected/grabbed feedback with local colors. The `CreatorStudioToolAdapter` runs `tool_api.interaction.handle_native_creator_ui_event(...)` before tool code, then chooses the correct optimized refresh path internally. A tool author must not compute camera-facing gizmo planes, pixel-to-world scale, hover flags, grabbed state, empty-click selection clearing or drag repaint strategy locally.

The same native-boundary rule applies to two panel/overlay behaviours added for production tools:

- **AutoPreview** is declared on `inspector.panel(..., auto_preview=inspector.auto_preview(...))`; the API/runtime owns debounce and triggers the existing preview action after inspector edits settle.
- **Overlays** are declared through `ctx.overlay`; the lifecycle cleanup closes and synchronises tool-owned Qt overlay widgets, and the overlay adapter owns z-order, drag repaint and hit geometry.


### Frozen native runtime contract

The Creator UI runtime is intentionally locked at the API boundary. External tools declare `ToolActor` objects and official style ids; the adapter owns hover, selection, grab, drag fast-path refresh, empty-click deselection, camera-facing orientation and FOV scaling. Normal tools must not call low-level refresh helpers from `on_event`, must not rebuild handles on mouse move, and must not override selected/grabbed colors locally.

Runtime interaction feedback always wins over a requested baseline visual state. For example, a `minimal` dot requested as `visual_state="grabbable"` still turns yellow when selected and orange when grabbed. This prevents a tool from accidentally keeping a selected tiny dot blue and losing the visual language validated in Tool Core Analysis.

## Responsibilities

### Tool Core Analysis

Tool Core Analysis is the laboratory and visual reference. It is where handle styles, actor rendering, preview primitives, overlay behavior and stress scenes are validated.

It is not a public dependency for normal tools. Creator tools should not import diagnostic internals or copy code from diagnostic scenes.

### `tool_api.ui_catalog`

`tool_api.ui_catalog` is the metadata layer. It exposes:

- stable family ids;
- labels and descriptions;
- public API entry points;
- recommended recipes for common tool categories;
- generated markdown documentation.

It does not render visuals and does not create handles.

### `tool_api.ui_motifs`

`tool_api.ui_motifs` is the executable public motif layer. It exposes the approved visuals extracted from Tool Core Analysis.

Use it when a tool, test or catalog needs to build or structurally refresh the official motif scene. Normal pointer events do not call these helpers from tool code; the adapter/runtime does it:

```python
from laserprog_studio.tool_api.gizmos import (
    build_creator_ui_motifs,
    refresh_creator_ui_interaction,
    refresh_creator_ui_drag,
    refresh_creator_ui_motifs,
    apply_creator_ui_motif_visibility,
    refresh_creator_ui_camera,
)

build_creator_ui_motifs(ctx, owner_tool=tool_id)
# The native runtime calls these internally for pointer events:
refresh_creator_ui_interaction(ctx, owner_tool=tool_id)  # hover/select/release, persistent
refresh_creator_ui_drag(ctx, owner_tool=tool_id, changed_actor_ids=moved_ids)  # drag, range-update fast path
refresh_creator_ui_motifs(ctx, owner_tool=tool_id)       # full rebuild/reset, not during drag
apply_creator_ui_motif_visibility(ctx, owner_tool=tool_id, visible_by_family={"point_styles": False})
refresh_creator_ui_camera(ctx, owner_tool=tool_id)       # after camera drag/wheel end
```

### `tool_api.interaction`

`tool_api.interaction` owns the standard actor event policy. The application adapter calls `handle_native_creator_ui_event(...)` automatically for registered Creator actors. Low-level tests may still call `hover_select_grab_actors(...)`, but normal tools should not write their own pointer state machine. The policy does a read-only hit-test first; if the pointer is not on a tool actor, it returns `handled=False` so the camera can continue orbiting/panning.

It is responsible for:

- hover ids;
- selected ids;
- grabbed ids;
- incremental drag movement;
- empty click selection clearing without breaking camera drag;
- deciding when the tool visuals must refresh.

It does not ask tool code to choose the drawing path. `handle_native_creator_ui_event(...)` refreshes through `tool_api.gizmos.refresh_creator_ui_interaction(...)` after state changes, through `tool_api.gizmos.refresh_creator_ui_drag(...)` during actor drags, and does no repaint for unchanged hover or empty camera-drag moves. Do not call a full motif rebuild for every hover or drag move.

### Gizmo catalog

The Gizmo catalog is now a focused viewer for `tool_api.projected_drawing`. It intentionally does not instantiate the interactive `tool_api.ui_motifs` catalog. Its viewport content is limited to non-pickable projected points, lines and faces submitted through `ctx.projected_drawing`.

It must not:

- create historical gizmo handles or preview primitives;
- register selectable Creator actors;
- create local PyVista/Qt drawing actors;
- copy Tool Core Analysis internals;
- expose another private rendering language.

Tool Core Analysis remains the reference environment for interactive Creator motifs; the projected drawing catalog validates the separate render-only path intended for Plan Tracer migration.

### Creator viewport renderer

The Creator viewport renderer must render public motifs with the shared Tool Core Analysis painter. This keeps Creator tools and the diagnostic reference visually aligned. It also owns camera-dependent GUI orientation and scale: after a camera drag/wheel burst, the renderer snaps guides to the nearest world axis seen by the camera and recomputes world sizes from the current field of view.

### Inspector AutoPreview

AutoPreview is a panel policy, not a per-field callback pattern. A tool that wants automatic preview regeneration declares:

```python
ctx.inspector.set_panel(
    inspector.panel(
        "My light tool",
        id=tool_id,
        owner_tool=tool_id,
        auto_preview=inspector.auto_preview(action_id="preview", debounce_ms=250),
        sections=[...],
    )
)
```

The runtime restarts one debounce timer whenever a user-editable inspector value changes, then calls `ctx.inspector.trigger("preview")`. This guarantees that all AutoPreview tools share the same stale-value and timing behaviour. It also keeps the explicit Preview button as the single preview implementation.

### Overlay lifecycle and z-order

Tool overlays are model objects in `ctx.overlay`, not private Qt windows. The Creator lifecycle calls `ctx.cleanup_tool(...)`, which closes tool-owned overlays and synchronises the Qt overlay layer. During overlay drag, the native adapter keeps the dragged window above siblings, does not re-raise other overlays under it, repaints the exposed parent region, and keeps widget geometry fixed to the visible frame so overlapping overlays do not leave stale hit rectangles.

## Rules for new UI/Gizmo work

1. Validate a new visual idea in Tool Core Analysis first.
2. Extract the approved motif into `tool_api.ui_motifs` and its metadata into `tool_api.ui_catalog`.
3. Update the interaction helper if the motif needs a new standard hover/grab policy.
4. Update the Gizmo catalog so it displays the new public motif.
5. Use the motif from creator tools through the public API.
6. Do not add one-off viewport UI, camera-orientation code or pixel-to-world scale code directly inside a tool.

## What tool authors should use

Prefer semantic public APIs. Declare what the actor is and which official style id it wants; the native runtime resolves hover/selected/grabbed state and the shared renderer resolves the final visual recipe.

```python
from laserprog_studio.tool_api.scene import actors

actor = actors.point(
    "anchor",
    (0, 0, 0),
    owner_tool=tool_id,
    interaction="grabbable",
    point_style="target",
    line_style="grabbable",
)
ctx.actor_registry(tool_id).add(actor)
```

`styles.resolve_actor_visual(...)` exists for render adapters and diagnostics. Normal tool code should rarely need it.

Use prebuilt manipulators when possible:

```python
ctx.gizmos.translate("move", owner_tool=tool_id, origin=(0, 0, 0))
ctx.gizmos.rotate("rotate", owner_tool=tool_id, origin=(0, 0, 0))
```

Direct `ctx.gizmos.create_handle(...)` calls are a low-level escape hatch. They are acceptable only when using official `style_id` values and shared style resolution. They should not be used to invent a new visual language.

## Public direction helpers

The architecture direction is also exposed from the API so tests and documentation can check the boundary:

```python
from laserprog_studio.tool_api.gizmos import (
    creator_ui_direction_layers,
    creator_ui_direction_markdown,
)

for layer in creator_ui_direction_layers():
    print(layer.title, layer.responsibility)

print(creator_ui_direction_markdown())
```

## Interaction performance rule

The Creator UI hot path is the same as Tool Core Analysis: during hover/grab/drag, tool code must not rebuild the motif scene, must not rebuild the snap cache, and must not resync static overlay windows. The non-optional runtime path is:

```python
handle_native_creator_ui_event(...)  # called by CreatorStudioToolAdapter
# internally chooses refresh_creator_ui_interaction or refresh_creator_ui_drag
```

`refresh_creator_ui_interaction(...)` updates existing actor-backed handles/previews with stable ids for state changes. `refresh_creator_ui_drag(...)` is stricter: it updates only moved actors, updates only the dependent primitives, and asks the shared painter to mutate cached mesh ranges instead of sweeping every motif. Full `build_creator_ui_motifs(...)` / `refresh_creator_ui_motifs(...)` calls are reserved for setup, reset, or structural changes. Empty camera drags are passed through immediately: the bridge skips Creator hit-testing on mouse-move when no actor is grabbed, then performs one end-of-camera refresh after release/wheel burst.

Visibility is semantic. `Hide all` and per-family toggles mark official motif actors as `api_ui_visible=False`, so hidden families are not hit-testable. `Show all` restores the same persistent motifs without requiring Reset.


## Native camera-navigation fast path

Button-down camera moves are not Creator hover events. The runtime skips Creator hit-testing and repaint while any viewport mouse button is held and no Creator actor is grabbed. This keeps Gizmo Catalog pan/orbit as fluid as Tool Core Analysis; only true actor grabs use the drag fast path.

## Native overlay behavior

Overlay windows are part of the Creator API runtime, not local tool widgets. A tool declares overlays; the runtime owns drag state, z-order, viewport clamping, collision avoidance, cleanup and final position commit. Draggable overlays are intentionally kept non-overlapping to avoid the repaint and hit-test artifacts produced by stacked translucent Qt child widgets. Overlay drag is handled through a direct widget-move fast path and the manager state is committed on release. When an overlay hits a viewport edge or another overlay, the runtime applies the native soft-wall policy: the widget stops, the blocked pointer delta is absorbed by rebasing the drag origin, and the next opposite move starts from the real visible position. The runtime does not warp the OS cursor. If the pointer leaves the real rectangle of a constrained overlay, the runtime cancels the drag, commits the current position, clears the pointer offset and swallows the matching release. Normal tools must not implement their own overlay drag or cursor handling.


## Plan tracer 2D drawing direction

Plan tracer-like tools must use `tool_api.plan2d` for locked-plane drawing behavior.  The API owns nearest-view selection from camera orientation, plan-height picking, projection/clamping to the drawing plane, smart snap, the `diamond` drawing cursor, `minimal dot` placed points and persistent Creator UI refresh.  The tool declares intent; it does not create custom point meshes, local snap logic or Qt/PyVista drawing widgets.

Hover remains a native visual update, but it is not an exclusive gesture.  Drawing tools still receive mouse moves so the API-owned cursor and snap result can track the pointer while actor hover state is updated by the runtime.

## Plan tracer opening and mode ownership

Plan tracer-like tools must let `tool_api.plan2d` own the first-step camera/view behavior. On open, the tool chooses the closest fixed view from the camera and locks the camera. It then shows only an anchor prompt overlay, with no drawing-mode buttons. The first click calls `pick_plan_anchor_by_raycast(...)`: face/object raycast hits define the semantic construction depth, and a miss falls back to depth `0`. The API then exposes both the semantic `plane` and the offset `display_plane`; tools use `register_plan_anchor_target(...)` to show the official `target` on the display plane while generated geometry stays clamped to the semantic anchor depth.

After the anchor is selected, the prompt is hidden and the real Plan tracer overlay palette appears. This palette is the only drawing-mode source. Palette buttons are an exclusive enum; the inspector must not duplicate mode buttons because that creates split state between UI surfaces.
