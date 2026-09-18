# Performance pass v12 — unified transform drag preview

This pass continues the transform-gizmo migration started in v10/v11.  The visual
Translate/Rotate/Scale handles are now native API gizmos; the remaining expensive
part was the live drag loop itself.

## Bottleneck addressed

Previous drag updates rewrote mesh vertices, modified VTK polydata, refreshed the
full inspector and requested a viewport render on every mouse move.  On large or
overlapping selections this made transform drag compete with VTK bounds updates,
inspector bounds calculations and render scheduling.

## New behaviour

- Translate, Rotate and Scale share one actor-preview model.
- Mouse movement updates existing selected actors with `SetPosition` or a
  temporary `UserMatrix`.
- Mesh vertices and polydata are committed once on release by
  `_commit_live_transform_preview()`.
- Translation smart-snap uses the cached snap index built at drag start, with the
  uncached path kept as a fallback.
- Sub-pixel mouse moves are ignored.
- Inspector/light readouts are throttled during drag.
- Drag render requests go through the central render scheduler instead of forcing
  immediate PyVista draws from the transform loop.

## Safety / fallback

Set `LPS_TRANSFORM_ACTOR_PREVIEW=0` to use the older live mesh-update path during
debugging.  The fallback still uses the central drag render request helper.

## Diagnostics

New application audit counters:

- `transform.drag.translate.actor_preview`
- `transform.drag.rotate.actor_preview`
- `transform.drag.scale.actor_preview`
- `transform.drag.translate.snap_cached`
- `transform.drag.translate.snap_uncached`
- `transform.drag.skipped_subpixel`
- `transform.drag.readout_throttled`
- `transform.drag.render_throttled`
- `transform.drag.<mode>.commit_once`
