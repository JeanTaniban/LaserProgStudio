# Performance pass v11 — unified native transform gizmos

This pass continues the migration started in v10.  Translate, Rotate and Scale now use the same Creator/UI API bridge instead of each mode owning a separate VTK overlay implementation.

## Goals

- Remove the heavy legacy transform gizmo path progressively.
- Keep the historical fallback behind `LPS_NATIVE_TRANSFORM_GIZMO=0`.
- Avoid VTK `PropPicker` for normal transform-gizmo interaction.
- Keep one semantic gizmo model for all transform modes: API handles, preview primitives, screen-space picking, and persistent viewport painting.

## What changed

### API extension

`GizmoManager.rotate(...)` and `GizmoManager.scale(...)` now support the same production options as `translate(...)`:

- `axis_length`
- `axis_vectors`

This allows the application transform UI to declare world-axis rotation and local-axis scale without rebuilding bespoke cone, tube and cube actors.

### Application bridge

`laserprog_studio.application.transform_gizmo_api` now exposes:

- `sync_native_translate_gizmo(...)`
- `sync_native_rotate_gizmo(...)`
- `sync_native_scale_gizmo(...)`
- `pick_native_transform_gizmo(...)`
- `sync_native_transform_interaction(...)`

The snapshot model is shared across modes, so hover/grab state and screen-space picking no longer depend on VTK foreground actors.

### Rotate

Rotate is represented as API preview rings plus lightweight ring handles. Picking measures screen-space distance to the projected ring polyline.

### Scale

Scale is represented as API axis handles plus adaptive frame-edge preview lines. The frame edges remain pickable through the same math picker and return handles like `x_min`, `x_max`, `y_min` and `y_max`, preserving the existing drag logic.

## Compatibility

The legacy VTK actor implementation remains available when the native path fails or when disabled with:

```bash
LPS_NATIVE_TRANSFORM_GIZMO=0
```

The migration is intentionally conservative: drag math, snapping, undo and inspector updates still use the existing transform-drag code. This pass only replaces the visual/picking layer.

## Diagnostics

The app performance audit receives mode-specific counters:

- `transform.gizmo.native.sync`
- `transform.gizmo.native.rotate.sync`
- `transform.gizmo.native.scale.sync`
- `transform.gizmo.native.<mode>.pick_hit`
- `transform.gizmo.native.<mode>.pick_miss`

## Follow-up work

The next useful step is to reduce live transform cost during Rotate/Scale drags, especially the per-event vertex writes and inspector refreshes. The gizmo rendering path is now unified, so that later optimization can target transform drag itself instead of three separate overlay systems.
