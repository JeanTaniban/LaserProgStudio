# Performance pass v13 — live-follow native translate gizmo

## Goal

The historical transform gizmo stayed at the original selection center during translation drag. That avoided moving many legacy VTK cone/cylinder actors, but it made the manipulator visually detach from the dragged part.

After v10-v12, the transform gizmo is API-backed and persistent, so the translate manipulator can follow the dragged selection center without returning to the old actor churn.

## Changes

- Added `move_native_translate_gizmo_live(...)` in `application/transform_gizmo_api.py`.
- Captured the native translate gizmo snapshot at drag start.
- During translation drag, the current snap-corrected offset is applied to:
  - API handle positions,
  - preview axis lines,
  - the native picking snapshot.
- The update uses `fast_update_creator_viewport_ui(...)` first, then falls back to the normal persistent renderer if the fast range update is unavailable.
- Added diagnostic counter:
  - `transform.drag.translate.gizmo_follow`
  - `transform.gizmo.native.translate.live_move`

## Important behavior

The mesh vertices are still committed only once on mouse release. Only the selected mesh actors and the small API gizmo overlay move during live drag.

This keeps the v12 performance model while restoring the expected UX: the gizmo remains centered on the part being moved.
