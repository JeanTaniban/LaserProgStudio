# Pass177 - Creator UI drag fast path

## Problem

The Gizmo catalog was still noticeably slower than Tool Core Diagnostic during grab/drag. The remaining gap was architectural, not visual: the catalog used the persistent painter, but it still asked the renderer to sweep the full catalogue scene on every drag move. Tool Core Diagnostic does less work: move one handle, refresh only dependent primitives for that row, then mutate existing viewport batches.

## Direction

The Creator API now exposes the same split explicitly:

```python
refresh_creator_ui_interaction(ctx, owner_tool=tool_id)
refresh_creator_ui_drag(ctx, owner_tool=tool_id, changed_actor_ids=moved_ids)
```

Use `refresh_creator_ui_interaction(...)` for hover, press, release and visual-state changes. Use `refresh_creator_ui_drag(...)` for mouse-move drag events. Tool authors should not rebuild motifs, rebuild snap caches, sync static overlays, or repaint every motif during drag.

## Implementation

`refresh_creator_ui_drag(...)` updates only moved actors and their dependent previews. The shared Tool Core Analysis painter records cached mesh ranges for handles and preview primitives, then updates only those ranges during drag. If no live viewport cache exists, the API safely falls back to the persistent full renderer.

The Gizmo catalog now delegates drag moves directly to this API path.
