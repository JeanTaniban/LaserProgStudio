# Light transform overlay

When the right Inspector panel is collapsed below a small width, LaserProg Studio now enables a light transform overlay at the bottom of the 3D viewport.

## Behavior

- The full Inspector remains unchanged when the right panel is open.
- When the right panel is collapsed, a compact overlay appears over the 3D view.
- The overlay is semi-transparent by default and becomes more opaque on hover.
- It exposes three enum-style modes:
  - Position
  - Rotation
  - Scale
- The three X/Y/Z value fields show the values for the selected mode.
- Editing a value applies the transform immediately to the current selection.

## Notes

The overlay reuses the same live transform pipeline as the full Inspector, so multi-selection, rotation state, local scale dimensions, undo snapshots, and tool/preview locks stay consistent.

Transforms remain disabled while another tool owns the scene or when a preview is active.
