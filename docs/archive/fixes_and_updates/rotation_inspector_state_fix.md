# Rotation inspector state fix

This update changes the transform inspector contract.

## Previous behavior

Rotation and scale fields were treated like global gizmo deltas. That caused wrong values to remain visible when selecting another part, and repeated rotations could make the fields impossible to use as a reliable reset target.

## New behavior

- Position fields display the active part center in millimeters.
- Rotation fields display the active part rotation state for the current session.
- Size fields display the active part world bounds dimensions in millimeters.
- Rotation and size values are no longer shared between parts.
- Dragging a rotation ring updates only the active part rotation state.
- Typing `0, 0, 0` in rotation and pressing Apply rotates the part back to its session zero orientation.
- Typing new Size values scales the active part to those bounds dimensions.

## Implementation notes

Each mesh can carry internal session-only transform metadata:

- `_lps_rotation_quat`
- `_lps_rotation_euler_deg`

The quaternion is used for stable rotation math. The Euler tuple is used only for inspector display/editing.

When the inspector fields are unchanged, Apply keeps the exact stored quaternion instead of rebuilding it from Euler values. This avoids reinterpreting complex drag histories and prevents silent extra rotation.
