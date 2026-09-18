# Rotation snap and inspector update

## Goal

Improve transform feedback and add a first version of rotation snapping.

## Inspector fixes

The transform inspector now highlights the row that matches the active transform mode:

- Translate highlights Position X/Y/Z.
- Rotate highlights Rotation X/Y/Z.
- Scale highlights Size X/Y/Z.

During a gizmo drag, the active value is also written live in the inspector:

- Rotate writes the current angle in degrees on the active axis.
- Scale writes the current factor on the active axis.
- Translate still updates the center position as before.

Rotation and scale gizmos already apply geometry directly to the mesh vertices. To avoid accidentally applying the same value a second time with the numeric Apply button, LaserProg detects unchanged gizmo display values and neutralizes them before applying any manual position change.

## Rotation snap V1

The transform panel now includes:

- Rotation snap toggle.
- Angle step in degrees.
- Angle tolerance in degrees.

Default behavior:

- Step: 45 deg.
- Tolerance: 5 deg.

With the default step, the gizmo can snap to common angles such as 45, 90, 135 and 180 degrees.

## Scope

This first version only affects rotation gizmo drags. Translation snap and scale are unchanged.
