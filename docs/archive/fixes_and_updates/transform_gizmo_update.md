# Transform gizmo update

## Goal

The transform axes were too small and the previous camera-observer approach caused UI stutter.
This update keeps the axes readable while avoiding continuous actor rebuilds during camera movement.

## What changed

- Removed the camera ModifiedEvent observer used by the previous transform-gizmo experiment.
- Removed screen-space axis picking from the previous experiment.
- The gizmo is now made from simple PyVista arrow primitives.
- Axis length is computed from the camera visible height when the gizmo is rebuilt.
- A small wheel debounce refresh updates the size after zoom bursts without rebuilding on every camera frame.
- Axis labels are colored 3D geometry instead of relying on white/transparent overlay labels.
- Picking tries the three gizmo axis actors first, then falls back to normal scene picking.

## Axis mapping

- X arrow: red, vector `(1, 0, 0)`, moves vertices on X only.
- Y arrow: green, vector `(0, 1, 0)`, moves vertices on Y only.
- Z arrow: blue, vector `(0, 0, 1)`, moves vertices on Z only.

## Why not the native affine widget yet

PyVista exposes `AffineWidget3D`, and VTK exposes `vtkAxesTransformWidget`. They are useful for a full native transform workflow, but they store/apply transforms through actor matrices or VTK widget state. LaserProg currently edits the real mesh vertices directly, so integrating that widget safely would require a deeper refactor to keep exports, inspector values, undo-like previews, and 3MF data consistent.

The current solution is intentionally conservative and low-risk.
