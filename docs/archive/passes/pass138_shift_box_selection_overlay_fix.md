# Pass138 – Shift box selection and overlay repaint fix

This pass fixes the native rectangle-selection workflow used by the Creator API Lab and by the shared selection overlay.

## Fixes

- Rectangle selection now starts with **Shift + left drag** in the Creator API Lab.
- A normal left drag on empty viewport is left to camera navigation/orbit.
- Empty click still clears the tool-actor selection, but the visual repaint remains deferred so camera drags are not refreshed at press time.
- The selection rectangle overlay no longer resizes itself to the rubber-band rectangle. It is now one full-size transparent overlay that stores and repaints the current rectangle.
- The overlay explicitly clears its backing store with `CompositionMode_Source` before drawing the current rectangle, preventing stacked/stale blue rectangles over the OpenGL viewport.
- The older scene selection-box controller also uses the same clearing overlay contract.

## Public API addition

`BoxSelectionActivationModifier` is now exported from:

- `laserprog_studio.tool_api.selection_box`
- `laserprog_studio.tool_api.scene`
- `laserprog_studio.tool_api`

Default activation is `SHIFT`, so `ctx.selection_box.handle_event(...)` does not start a selection rectangle on plain left drag.

Direct calls to `ctx.selection_box.begin(...)` remain available for tools that intentionally implement their own activation gesture.

## Validation

Added `tests/test_pass138_selection_box_shift_overlay.py`.

Full test suite result: **564 passed, 3 skipped**.
