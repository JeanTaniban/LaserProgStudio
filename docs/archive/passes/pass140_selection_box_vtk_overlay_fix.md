# Pass140 – Selection box VTK overlay fix

## Problem

The Pass139 no-blackout fix replaced the full-screen transparent selection
box with a small moving QWidget. That avoided the black OpenGL viewport on some
Qt/VTK compositions, but the old rectangle could still remain visible because
QVTK/QOpenGL widgets do not always repaint the previous child-widget region
between mouse-move events.

## Fix

`SelectionBoxOverlay` now prefers a VTK display-coordinate overlay:

- two persistent `vtkActor2D` actors, one fill and one outline;
- display-coordinate `vtkPolyDataMapper2D`;
- point arrays updated in place during drag;
- no Qt transparent full-screen overlay;
- no add/remove actor churn during mouse move;
- no stale Qt backing-store pixels.

A QWidget fallback still exists for non-VTK test or utility parents. In that
fallback, the old geometry is hidden and repainted synchronously before the
widget moves.

## Interaction rule

Creator API Lab box selection remains **Shift + left mouse drag** only. A plain
left drag remains available for the camera orbit.
