# Pass124 - Snap/SceneCache and Creator Lifecycle Hardening

Pass124 hardens the creator API after the Pass123 review.

## Main changes

- Tool actor snap targets now report `TOOL_ACTOR_POINT` / `TOOL_ACTOR_EDGE`.
- UI targets are reserved for actual screen-space UI/GUI/gizmo targets.
- `exclude_ids` is applied during snap query and no longer forces a cache rebuild.
- `SceneCache.add_point(...)` and `add_segment(...)` now create persistent tool-temp targets that survive `rebuild(...)`.
- Tool-temp and UI/custom targets can be cleared by owner with `ctx.scene_cache.clear_tool_targets(owner_tool)`.
- `CreatorTool` provides an external-friendly lifecycle with automatic cleanup.
- `ctx.cleanup_tool(tool_id)` centralizes cleanup of actors, previews, gizmos, overlays, inspector panels and snap targets.
- `ctx.commands.do(...)` and `ctx.commands.transaction(...)` make undo/redo easier for external tools.
- Actor factories now reject ambiguous geometry early.
- `tool_api.interaction.select_or_grab(...)` provides the standard select/Shift/grab/move gesture.

## Why it matters

A creator can now clearly distinguish:

- scene geometry;
- sketch geometry;
- actors owned by the active tool;
- construction snap targets;
- screen-space UI targets.

That removes a class of bugs where smart snap could behave differently depending
on whether an element came from the viewport, an overlay or an internal actor.
