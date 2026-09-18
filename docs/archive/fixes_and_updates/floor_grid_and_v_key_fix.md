# Floor grid toggle and V key fix

This update adds a lightweight floor grid display toggle to the top toolbar, after the Boolean tools.

## Floor grid

- New `Grid` toggle button in the top toolbar.
- The grid is drawn as non-pickable VTK/PyVista line geometry.
- It uses a 10 mm step by default.
- It is rebuilt with the scene and sized around the current scene bounds.
- It does not interfere with part picking, transform gizmos, or Boolean tools.

## Keyboard fix

The plain `V` key is now ignored in the 3D viewport and at the window level. This prevents accidental buggy camera changes caused by VTK/PyVista default key handling.

`Ctrl+V` is not blocked by this fix.
