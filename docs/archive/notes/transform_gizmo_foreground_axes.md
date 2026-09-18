# Transform gizmo foreground axes update

This update replaces the previous transform-axis display with thick primitive axes rendered in a foreground VTK layer.

## Goals

- Keep the UI smooth during camera navigation.
- Make the transform axes easier to see.
- Prevent the selected mesh from hiding the axes.
- Keep axis picking simple and stable.

## Implementation

- The gizmo now uses one cylinder shaft and one cone tip per axis.
- The X, Y, and Z axes are rendered with dedicated VTK actors.
- The actors are placed in a foreground renderer that shares the main camera.
- The foreground renderer does not preserve the main scene depth buffer, so the axes remain visible on top of the 3D parts.
- Axis labels are rendered in the same foreground layer and use the axis color.
- No continuous camera observer is used. The gizmo is refreshed only on scene/selection changes and after wheel zoom bursts.

## Main file changed

- `src/laserprog_studio/window.py`

## Notes

The solution intentionally avoids PyVista/VTK depth-test hacks because they are not exposed as a stable high-level PyVista option. A separate foreground renderer is more predictable for this use case.
