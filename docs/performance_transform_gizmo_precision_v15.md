# Performance / UX pass v15 — native transform gizmo precision

This pass continues the native/API transform gizmo migration with a focus on correctness and perceived stability.

## Fixed

- Translate arrow guides are now oriented from the real world-space axis projected into the active viewport billboard plane.  The arrow glyph no longer always points to screen +X.
- Native gizmo picking is exclusive and ambiguity-aware.  When projected axes/rings overlap, the picker returns no handle rather than stealing the wrong axis.
- Translate/scale axis picking ignores the shared triad center and uses the outer part of the axis shaft plus the tip.  This prevents X/Y/Z hover flicker around the origin.
- Rotate drag projection now falls back to a screen-space least-squares projection on the rotation plane basis when ray/plane intersection is numerically unstable.
- Scale handles are clamped outside the selected bounds/frame, so they remain visible even when the camera-derived gizmo length is smaller than the part.
- Tool-Core/Creator UI actors are marked as foreground/no-bounds where VTK supports it, to reduce cases where scene geometry visually hides interaction UI.
- Guide batches are split by style/color/width so one hovered axis does not visually affect all arrows in the same style batch.
- Removed an accidental double update in scale drag dispatch.

## Diagnostics and tests

- Added `tests/test_pass1012_transform_gizmo_precision.py`.
- Existing native transform, central render, camera budget, and Plan Tracer motif tests still pass in the targeted suite.
