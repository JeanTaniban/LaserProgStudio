# Modifiers and split plane - update

This pass adds a new Modifiers section after Booleans.

## New toolbar section

- `Modifiers`
- `CUT` opens the Split by plane modifier.

Modifiers behave like classic tools: they open the right inspector, own the preview workflow, and are closed by Apply or Cancel.

## Split by plane modifier

The modifier displays a light blue cutting plane in the 3D view.

Parameters:

- Position X/Y/Z
- Rotation X/Y/Z
- Plane size
- Tolerance

Actions:

- `Use selection center` places the plane at the current selection center.
- `Face camera` orients the plane approximately toward the current camera view.
- `Preview split` generates a preview result.
- Global `Apply` validates the preview.
- Global `Cancel` discards it.

## Geometry process

The modifier uses PyVista/VTK closed-surface clipping when available. It creates the two sides of the cut, then runs the existing disconnected-island separation so pieces produced by the cut become independent parts.

## Notes

The best results require closed/watertight meshes. If the plane does not cross the selected mesh volume, no preview is generated.
