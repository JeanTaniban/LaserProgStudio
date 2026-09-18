# Performance pass v10 — native/API transform gizmo migration

## Goal

Start replacing the historical application transform gizmo with the optimized Creator/API gizmo path.

The old translate arrows were built as multiple standalone VTK cone/cylinder/text actors. Every refresh cleared and recreated those actors, registered pick metadata again, reset clipping ranges and often forced a render. That is expensive during selection changes, camera moves and hover/drag startup.

## What changed

### New bridge

Added:

- `src/laserprog_studio/application/transform_gizmo_api.py`

This module declares the main application Translate gizmo through:

- `ToolContext.gizmos`
- `GizmoManager.translate(...)`
- `ToolContext.preview.show_line(...)`
- the persistent Creator UI painter used by the API lab

The migration is intentionally progressive. Translation uses the native/API path first. Rotation and scale still use the legacy VTK overlay until they are migrated separately.

### API extension

`GizmoManager.translate(...)` now supports:

- `axis_length`
- `axis_vectors`
- `include_center`

The default behavior remains the original unit XYZ manipulator, so existing tools are compatible.

### Picking

The API translate gizmo uses lightweight screen-space math picking over three projected axis segments. This avoids a VTK `PropPicker` over a list of foreground actors just to decide if the mouse is on an X/Y/Z arrow.

### Rendering

The new path uses the persistent Creator UI painter. It mutates/reuses batched actors instead of rebuilding the historical cone/cylinder actors.

Feature flag:

```text
LPS_NATIVE_TRANSFORM_GIZMO=0
```

Setting this disables the new path and falls back to the legacy translate gizmo.

## Follow-up migration plan

1. Migrate Rotate to API rings with screen-space angular picking.
2. Migrate Scale to API square/bounds handles.
3. Remove legacy foreground duplicate actors once all transform modes have native equivalents.
4. Move texture and split-plane gizmos onto the same API bridge.

## Diagnostics

New audit counters:

- `transform.gizmo.native.sync`
- `transform.gizmo.native.clear`
- `transform.gizmo.native.pick_hit`
- `transform.gizmo.native.pick_miss`
