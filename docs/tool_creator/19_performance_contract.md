# Creator API performance contract

This page documents the rules that keep Creator tools responsive in dense scenes.
It was written after the Plan Tracer 2D performance audit, where an apparently
small API misuse made every mouse move rebuild snap and viewport caches.

The short version: **tool code declares state; the Creator runtime owns hot-path
interaction, cache invalidation and visual refresh.**

## Hot-path rule

Mouse move, hover and drag handlers are hot paths. They must not do work that is
structural unless the user really changed geometry.

Do this:

```python
class MyTool(CreatorTool):
    def on_open(self, ctx):
        ctx.actor_registry(self.id).add(
            actors.point("p0", (0, 0, 0), interaction="grabbable", point_style="target")
        )

    def on_event(self, event, ctx):
        # Optional tool-specific behaviour only. Hover/select/grab already ran.
        if event.is_move:
            return False
```

Do not do this inside `on_event` or helper methods called by every mouse move:

```python
# Bad: rebinding is a runtime responsibility and may invalidate caches.
ctx.document.bind(scene)

# Bad: reinstalling projection closures makes cache keys unstable.
ctx.viewport.world_to_screen = lambda p: ...

# Bad: full UI rebuild on hover/drag.
refresh_creator_ui_motifs(ctx, owner_tool=self.id)
ctx.preview.clear_tool(self.id)
ctx.gizmos.clear_tool(self.id)
```

## Context and document binding

`CreatorStudioToolAdapter.tool_context()` is allowed to run for every event. It
is therefore responsible for idempotent binding:

- rebinding the same document target must be a no-op;
- viewport projection adapters must be installed once per owner, then reused;
- tools should treat `ctx.document`, `ctx.viewport`, `ctx.scene_cache`,
  `ctx.selection`, `ctx.preview`, `ctx.gizmos` and `ctx.overlay` as stable
  services owned by the runtime.

External tools should not call `ctx.document.bind(...)` unless they are building
a custom host integration. Normal tools receive a ready-to-use context.

## Scene cache invalidation

Use the smallest invalidation scope possible.

| Situation | Correct API | Must not do |
|---|---|---|
| Move a cursor/helper excluded from snap | `ctx.selection.register_actor(...)` via API helper, no scene invalidation | `ctx.actor_registry(...).add(...)` if the actor changes every frame |
| Add/remove real snap geometry | `ctx.actor_registry(...).add(...)` or `ctx.scene_cache.add_point/add_segment` | Mutate private cache lists |
| Temporary one-query snap points | `ctx.snap.smart(..., extra_targets=...)` | Store them as scene objects |
| Tool closes/resets | `ctx.cleanup_tool(self.id)` or `ctx.scene_cache.clear_tool_targets(self.id)` | Leave persistent temp targets behind |

A visual actor is not always a snap target. Cursor actors, hover handles and
pure UI overlays should not invalidate scene snap structures.

## Snap rule

For a locked-plane drawing tool, split snap data into two groups:

- **near targets**: exact candidates close to the cursor, used by the snap
  manager for vertex/edge/midpoint hits;
- **alignment targets**: larger stable guide cache, used for horizontal,
  vertical, axis and intersection guides.

Avoid rebuilding the full scene guide cache on every mouse move. The cache key
should depend on structural snap data and camera/projection state, not on cursor
position or transient UI actors.

## Visual refresh rule

Use the runtime refresh path that matches the action:

| Action | Correct path |
|---|---|
| Hover/select state changed | Native runtime / `refresh_creator_ui_interaction(..., return_snapshot=False)` |
| Drag or cursor position changed | `refresh_creator_ui_drag(..., changed_actor_ids=(...), render=False)` or domain helper such as `plan2d.sync_plan_actor_visuals(..., position_only=True)` |
| Camera changed | `refresh_creator_ui_camera(...)` |
| Tool opened, topology changed, style changed | Full motif/actor rebuild is allowed |

A tool should normally not call these directly. Registered `CreatorTool`
runtimes get the native interaction path automatically. Domain helpers such as
`tool_api.plan2d.register_plan_cursor` and `tool_api.plan2d.sync_plan_actor_visuals`
exist so specialized tools can still stay on the safe path.

## Instrumentation checklist

When a new tool feels slow, export or inspect counters around these names:

- event: `*.event.mouse_move.total`, `*.event.mouse_press.total`;
- cursor: `*.cursor.update`, `*.cursor.smart_snap`, `*.cursor.actor_sync`;
- snap cache: `scene_cache.snap.rebuild_screen_index`, `scene_cache.snap.near_query.total`;
- UI: `*.render`, `*.sketch.actor_visual_sync`, `*.cursor.sync_actor_visuals`;
- document/runtime: `document.bind.same_target`, `document.bind.changed_target`,
  `creator.viewport_projection.install`, `creator.viewport_projection.reuse`.

Red flags:

- `document.bind.changed_target` increases during plain mouse moves;
- viewport projection install count increases after the tool is open;
- scene snap screen index rebuild count tracks mouse move count;
- full motif refresh or preview clear appears in move/hover handlers.

## Review checklist for external tools

Before accepting a new tool:

1. `on_event` does not bind documents, reinstall viewport functions or clear all visuals on move.
2. Actors are registered through `ctx.actor_registry(self.id)` or domain API helpers.
3. Per-frame helper actors use a cursor/helper API that does not invalidate structural snap caches.
4. Snap uses `extra_targets` for one-shot candidates and `ctx.scene_cache.add_*` only for persistent construction guides.
5. Expensive compile/mesh/document rebuilds happen on click, release, apply or debounce — not on every hover.
6. A diagnostic scenario exists for dense scenes and reports timing counters in `diagnostics/`.

## Planar tool incremental-visual rule

Planar route tools such as Plan Tracer and Vent Generator must distinguish
**topology changes** from **pointer-only changes**.

A topology change is a click/release/apply operation that adds, deletes or
commits geometry. It may rebuild route actors, generated previews and scene snap
indexes.

A pointer-only change is a hover, cursor preview, ADD pending point or live drag.
It must update only the actors that moved:

```python
# Good: only the cursor/pending link moved.
plan2d.register_plan_cursor(ctx, owner_tool=tool_id, cursor_id="my.tool.pending", world_pos=p)
plan2d.sync_plan_actor_visuals(
    ctx,
    owner_tool=tool_id,
    changed_actor_ids=("my.tool.pending",),
    extra_preview_ids=("my.tool.pending_link",),
    position_only=True,
    render=True,
)
```

Avoid this pattern in mouse-move code:

```python
# Bad: every move re-registers the whole route even though only the cursor moved.
for waypoint in route.waypoints:
    plan2d.register_plan_point(...)
for segment in route.segments:
    plan2d.register_plan_line(...)
plan2d.sync_plan_actor_visuals(ctx, owner_tool=tool_id, position_only=True)
```

The Vent Generator audit found this exact issue after the snap-cache fix: the
snap was fast, but route visual synchronisation still touched all waypoints and
segments during ADD preview. External tools should expose a `changed_indices`,
`changed_actor_ids` or equivalent dirty set for hot-path updates.

## Built-in timing exports

Heavy built-in tools should expose an inspector action that writes a report in
`diagnostics/`. Recommended files:

- `<tool>_timings.md` for human inspection;
- `<tool>_timings.json` for complete data;
- `<tool>_timings.csv` for sorting counters.

Use consistent counter prefixes. Examples:

- `vent.event.mouse_move`, `vent.pointer.resolve`, `vent.visual.sync`;
- `plan_trace.cursor.update`, `plan_trace.cursor.smart_snap`;
- shared runtime counters such as `scene_cache.snap.rebuild_screen_index`,
  `creator.ui.refresh.direct_lookup`, `document.bind.same_target`.

A new external tool should not be accepted as “fast” unless it can show that
mouse-move counters stay stable with many scene objects and many tool actors.
