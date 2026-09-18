# Light overlay transform synchronization

The compact light transform overlay now mirrors the top transform toolbar.

## Behavior

- Position selects Translate (`T`).
- Rotation selects Rotate (`R`).
- Scale selects Scale (`S`).
- Selecting `N` in the toolbar clears the gizmo but keeps the current object selection.
- The overlay buttons are unchecked when the transform mode is `N`.

## Close button

A new `X` button was added at the left of the compact overlay.

Clicking it:

1. switches transform mode to `N`;
2. clears the current object selection;
3. removes the transform gizmo.

This differs from the toolbar `N` button, which keeps the selection.
