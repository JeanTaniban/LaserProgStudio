# Split plane modifier refinement

This update refines the CUT modifier workflow.

## Changes

- CUT can only be opened when at least one target mesh is selected.
- The CUT button is disabled when there is no valid target selection.
- The split plane is now centered on the current target selection by default.
- The position UI has been simplified to a single `Forward offset` value.
- `Forward offset = 0` means the plane is exactly at the selection/group center.
- The yellow handle moves the plane only along its forward/normal axis.
- Changing the selected target while CUT is open recenters the plane and resets the offset to `0` while preserving the plane rotation.
- The forward offset is clamped to the selected mesh/group projected extent so the plane cannot be moved outside the target with the offset control or the handle.
- The yellow forward handle has been made much thinner so it is closer to the transform translation gizmo style.

## Constraint model

The offset limit is intentionally simple and robust: all selected vertices are projected on the current plane normal relative to the selection center. The offset is clamped between the minimum and maximum projected values.
