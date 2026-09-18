# Source cleanup pass 11 — Creator API isolation

This pass removes the remaining direct owner-window dependencies from the first
migrated Creator tools.

## API additions

- `TOOL_API_VERSION` is now `0.13.0`.
- `ctx.document.ensure()` creates/binds a usable document/model store through the
  application bridge when a creator tool opens without an already-bound scene.
- `ctx.scene_selection.select_indices(...)`, `select_range(...)`, and
  `select_last(...)` replace direct writes to `owner.selected_indices`,
  `owner.active_index`, and Qt mesh-list selection.
- `ctx.view.focus_index(...)`, `focus_bounds(...)`, `focus_meshes(...)`,
  `focus_scene(...)`, and `refresh(...)` replace direct calls to the historical
  camera helpers.

## Migrated tools tightened

- `PrimitiveCreatorTool` stages preview, selection, and camera focus through
  `ctx.document`, `ctx.scene_selection`, and `ctx.view` only.
- `BoxCreatorTool` does the same for its six-board preview.

The tools may still run inside the historical Qt application, but the owner access
is now isolated inside API services instead of tool implementations.
