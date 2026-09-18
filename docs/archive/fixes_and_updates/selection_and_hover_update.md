# Selection and transform hover update

This update adds two interaction improvements:

- Empty left click clears the current part selection.
- Moving the mouse over a transform axis/ring highlights the hovered axis.

Implementation notes:

- Hover picking is limited to gizmo actors only, not scene meshes.
- Hover probing is throttled to avoid UI stutter.
- The gizmo is not rebuilt during hover; only actor material properties are updated.
- Translation arrows and rotation rings share the same X/Y/Z hover state.
- Empty click also clears the transform mode so no orphan gizmo remains visible.
