# 09 - Creator API checklist

Use this checklist before accepting a new external tool.

## Imports

The tool imports from `laserprog_studio.tool_api`, not from the main window, Qt widgets, PyVista or historical controllers.

## Inspector

The right Tool area is declared through `ctx.inspector.set_panel(...)`.

Every field has a stable id, a human label, a default value and validation when relevant.

## Actors

Every interactive viewport element is registered as a `ToolActor` through `actors.point`, `actors.line`, `actors.circle`, `actors.arc` or `actors.polyline`.

Every actor explicitly declares one interaction mode: `fixed`, `selectable` or `grabbable`.

## Snap

The tool uses `ctx.snap.smart(...)` instead of owning a private snap engine.

Temporary geometry snap uses `snap.point(...)` or `snap.segment(...)`.

Temporary UI/GUI snap uses `snap.ui_point(...)`.

The tool excludes the currently moved actor or selection with `exclude_ids=...` when needed.

## Scene cache

The tool calls `ctx.scene_cache.rebuild(ctx, scope="snap")` when geometry changes.

The tool calls `ctx.scene_cache.invalidate()` when it cannot rebuild immediately.

## Commands

Every destructive or committed action goes through `ctx.commands.execute(...)` with a clear label and undo function.

## Diagnostic

The behavior is reproducible in Tool Core Diagnostic or in a headless test.

## Pass125 professional checklist

Before accepting a new external-style tool:

- [ ] The tool imports from `laserprog_studio.tool_api`, not from Qt/PyVista/internal modules.
- [ ] The module calls `require_tool_api("0.13.0", max_major=0)`.
- [ ] The module exposes a `ToolManifest`.
- [ ] Actors are registered through `ctx.actor_registry(tool_id)` or `ctx.actors`.
- [ ] Duplicate actor replacement is explicit with `replace=True`.
- [ ] Dynamic inspector validation uses `set_error`, `set_enabled`, `set_visible` or `set_readonly`.
- [ ] Multi-step actions use `ctx.commands.transaction(...)`.
- [ ] The tool can be closed/cancelled without leaving actors, previews, snap targets or inspector panels behind.
- [ ] Tool-owned overlays are declared through `ctx.overlay` and are cleaned through the Creator lifecycle; the tool does not keep Qt widget references.
- [ ] Import audit passes for examples/plugins.
- [ ] Real scene mutations use `ctx.document`, not `mesh_store` or window internals.
- [ ] Scene-object selection uses `ctx.scene_selection`, not actor selection.
- [ ] Modifiers/generators use `ctx.preview_session` for preview/apply/cancel.
- [ ] Heavy operations report through `ctx.status` and `ctx.jobs`.

## Native Creator UI checklist

Before accepting a tool with viewport actors or gizmos:

- [ ] The tool subclasses `CreatorTool` and is registered with `register_tool(..., runtime=create_tool(), ...)`.
- [ ] The tool declares actors through `ctx.actor_registry(tool_id)` / `actors.*`; it does not draw private PyVista or Qt handles.
- [ ] The tool does not call `hover_select_grab_actors(...)`, `handle_native_creator_ui_event(...)` or `refresh_creator_ui_*` from `on_event`.
- [ ] `on_event` is only for domain-specific commands or custom gestures that are not normal actor hover/select/grab.
- [ ] Empty-click selection clearing is left to the native runtime.
- [ ] Camera-axis orientation and FOV scaling are left to the renderer/API.
- [ ] Full motif rebuild/reset is not called on mouse move.
- [ ] The tool does not override native selected/grabbed feedback. `minimal` dots must turn yellow on selection and orange during grab through `styles.resolve_actor_visual(...)` / the renderer, not through tool-local colors.
- [ ] The public runtime contract remains `CREATOR_UI_RUNTIME_CONTRACT == "native_non_overridable"`.

## Native AutoPreview checklist

For tools that opt into automatic preview regeneration:

- [ ] The panel declares `auto_preview=inspector.auto_preview(...)` or an equivalent `AutoPreviewConfig`.
- [ ] AutoPreview triggers an existing `preview` action; it does not duplicate the preview implementation.
- [ ] The debounce is at least large enough for the tool cost. Cheap viewport previews can use ~150-300 ms; heavy mesh operations should remain manual or use jobs.
- [ ] The tool does not create a local Qt timer for inspector field changes.

## Overlay runtime checklist

- Declare overlays with `ctx.overlay` / `OverlayWindowSpec`; do not instantiate Qt widgets in a tool.
- Do not call `raise_()`, `move()`, `repaint()`, `update()` or mouse-grab APIs from tool code.
- Do not allow draggable overlays to overlap by local Qt code. The native runtime separates them and commits the final position.
- Use `ctx.cleanup_tool(tool_id, include_persistent_overlays=True)` through the Creator lifecycle instead of manually hiding widgets.


## Native overlay drag checklist

- Declare overlays through `ctx.overlay`; do not create Qt widgets in a tool.
- Do not implement overlay drag, collision avoidance, `raise_()`, repaint loops or cursor handling locally.
- The runtime owns the non-overlap policy, viewport clamp, direct move fast-path, soft-wall rebase, pointer-exit cancellation and final position commit.
- If two draggable overlays would overlap, the runtime treats the blocker as a wall. The OS cursor is not warped; if the pointer leaves the dragged overlay rectangle, the runtime cancels the drag and clears the stale offset.

## Overlay release redraw

- Do not repaint, hide/show or move Qt overlay widgets from a tool.
- Draggable overlays use the native fast path during movement and a single release redraw on release/cancel to clean translucent traces over the 3D viewport.
- If a tool appears to need manual overlay repaint code, the overlay adapter/API must be fixed instead.


## Performance / hot-path safety

- [ ] `on_event` does not call `ctx.document.bind(...)`, install viewport projection callables, or clear/rebuild all previews/gizmos on mouse move.
- [ ] Cursor/helper actors that move every frame are registered through an API helper that does not invalidate scene snap structures.
- [ ] Snap caches distinguish structural geometry from transient UI state; `scene_cache.snap.rebuild_screen_index` must not scale with mouse-move count.
- [ ] Hover/drag visual updates use the native runtime or position-only refresh paths; full motif refresh is reserved for open, topology changes, style changes, or explicit rebuilds.
- [ ] Dense-scene diagnostics write timings to `diagnostics/` and include counters listed in `19_performance_contract.md`.
- [ ] Pointer-only previews update only changed actors/cursors/preview items; they do not re-register every point/segment in the route.
- [ ] Route-like tools expose a dirty set (`changed_indices`, `changed_actor_ids`, etc.) so ADD preview and MOD drag remain incremental.
