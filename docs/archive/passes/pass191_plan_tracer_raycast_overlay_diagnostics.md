# Pass 191 — Plan tracer raycast diagnostics and overlay enum clicks

This pass fixes the first Plan tracer 2D foundation bugs observed in the GUI.

## Raycast anchor

`tool_api.planar_drawing.pick_plan_anchor_by_raycast(...)` now tries the real scene first:

1. native VTK `vtkCellPicker` against every visible scene mesh actor in `owner.actors_by_index`;
2. all candidate Qt→VTK coordinate conversions exposed by the host;
3. fallback to `ctx.pick.face_at(..., all_parts=True, only_selected=False)` and `ctx.pick.object_at(...)` for headless tests or alternate hosts;
4. fallback depth `0` only when no scene hit exists.

The returned `Plan2DAnchorPick` carries a `diagnostics` dictionary.  The Plan tracer anchor click enables compact logging:

```text
[PLAN_TRACE_RAYCAST] anchor-click result=hit backend=... depth=... pick_list=... attempts=...
```

This makes broken anchor picks diagnosable without changing the tool code.

## Overlay enum buttons

Grouped overlay buttons now update the stored `OverlayWindowSpec.buttons`, not only the global button table.  This means the checked/highlighted mode is visible immediately after a click.

The Qt overlay adapter also notifies the active Creator tool via `on_overlay_button_clicked(button_id, ctx)`.  Plan tracer mirrors this into its selected drawing mode and refreshes the overlay text immediately, instead of waiting for a later viewport hover.

## Direction

A Plan tracer-like tool still declares official API state only.  It does not create Qt widgets, custom raycasts or custom highlight styles.
