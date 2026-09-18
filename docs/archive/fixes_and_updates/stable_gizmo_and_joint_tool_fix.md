# Stable gizmo refresh and joint tool cleanup

## Gizmo refresh rollback

Live gizmo rebuilds during transform drags and free orbit were removed because rebuilding VTK overlay actors while the mouse moves can create visible stutter.

Current behavior:

- Translation, rotation, and scale render the mesh live while dragging.
- The transform overlay is rebuilt at the end of the drag.
- The scale frame still adapts to the camera, but only after the camera action is finished or after a zoom burst.
- Wheel zoom keeps a delayed refresh, not a refresh on every wheel event.

This keeps the UI responsive while preserving accurate overlay placement after each action.

## Joint tool transform blocking

The joint tool now behaves like the other preview tools:

- Transform overlay actors are removed when the tool opens.
- Transform button state remains memorized but unavailable while the tool is active.
- Any pending gizmo press/drag/highlight is cancelled when a tool opens.
- Leaving the joint tool clears the A/B selection.

This prevents transform gizmos from appearing or being usable while staging joints.
