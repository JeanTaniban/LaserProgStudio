# Window refactor - Gizmo diagnostic fix

## Cause confirmed from user log

The diagnostics log showed that `update_gizmo()` crashed before creating any VTK actors:

- `TypeError: GizmoViewMixin._log_gizmo_state_once() got multiple values for argument 'reason'`
- `TypeError: SceneStateMixin._bounds_from_vertices_list() takes 1 positional argument but 2 were given`

The second error also broke duplicate/paste because the clipboard offset calculation uses the same bounds helper.

## Fixes

- Restored `@staticmethod` on `SceneStateMixin._bounds_from_vertices_list`, matching the original monolithic `window.py` behavior.
- Renamed the first parameter of `_log_gizmo_state_once` from `reason` to `event`, so hidden-state logs can safely include a `hidden_reason` field.
- Added detailed diagnostic logs for:
  - transform mode changes (`[TRANSFORM_DIAG]`),
  - gizmo update gates and build steps (`[GIZMO_TRACE]`),
  - VTK overlay/main renderer actor creation (`[GIZMO_DIAG]`),
  - selection and bounds (`[SELECTION_DIAG]`, `[BOUNDS]`),
  - keyboard shortcuts (`[KEY_DIAG]`),
  - gizmo picking (`[PICKING_DIAG]`),
  - copy/paste/duplicate offset logic (`[CLIPBOARD_DIAG]`).

## Expected behavior

- `N`: transform mode none, gizmos hidden.
- `T`: translation arrows visible when at least one part is selected.
- `R`: rotation rings visible when at least one part is selected.
- `S`: scale handles visible when at least one part is selected.
- `Ctrl+C`, `Ctrl+V`, `Ctrl+D`: copy, paste, duplicate should no longer fail on `_bounds_from_vertices_list`.

## Static guard

`scripts/verify_refactor_structure.py` now checks that `_bounds_from_vertices_list` remains a staticmethod and that the diagnostic log categories stay present.
