# Pass118 — Minimal dot size sliders

This pass keeps the Pass117 geometry-backed minimal dot, but exposes its size in the Tool Core Diagnostic panel so the final production values can be chosen visually.

## Changes

- Added two diagnostic sliders:
  - **Normal** minimal dot radius.
  - **Hover / grab** minimal dot radius.
- Moved minimal-dot size ownership into `GizmoManager`:
  - `set_minimal_dot_radii(...)`
  - `radius_for_style(...)`
  - `update_style_metrics(...)`
- The live painter no longer clamps minimal dots back to a large value. The slider values drive the geometry disc radius directly.
- Hover/grab state still uses persistent actors; the slider path updates existing handle records and re-renders without clearing the diagnostic scene.

## Production note

These sliders are temporary tuning controls. Once the right values are chosen, the fixed values should live in Tool Core and the diagnostic sliders can be removed or hidden.
