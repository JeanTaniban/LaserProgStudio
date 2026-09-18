# Pass189 — Plan tracer opening view, anchor target and overlay enum

This pass corrects the first-step UX of the rebuilt Plan tracer 2D tool.

## Direction

The start of Plan tracer is now deterministic:

1. on tool open, the API chooses the closest fixed planar view from the current camera direction;
2. the camera is immediately locked to that orthographic view;
3. the overlay shows `Select anchor height point`;
4. the first click raycasts/picks the height anchor;
5. the API offsets the drawing plane slightly toward the camera so Creator UI motifs remain visible above the selected surface;
6. a fixed official `target` motif marks the anchor reference height;
7. the overlay palette is the only drawing-mode source and behaves like an exclusive enum.

## API additions

`tool_api.planar_drawing` now exposes:

- `PLAN_TRACE_ANCHOR_ROLE`
- `PLAN_TRACE_DEFAULT_SURFACE_OFFSET`
- `pick_plan_height(..., view=...)`
- `offset_plan_height_pick_for_visibility(...)`
- `register_plan_anchor_target(...)`

Tool authors should use these helpers instead of writing local raycast offsets, custom anchor widgets or separate mode state.

## Tool behavior

The inspector no longer offers alternative drawing-mode buttons.  It may reset the draft, but `Modify`, `Line`, `Rectangle`, `Circle`, `Half-circle` and `Point` are selected from the overlay palette only.  `Escape` remains a shortcut to `Modify`.
