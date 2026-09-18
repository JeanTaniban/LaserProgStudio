# v64 — Split Modifier two-axis tilt UX

The Split Modifier rotation UI was simplified after the Projected Drawing migration.

## Product rule

A split plane only needs two rotations that change the cut normal. Twisting the plane around its own normal does not change the cut, so the old `Rz`/twist control is no longer exposed in the inspector or as a projected handle.

## Inspector

The Plane section now exposes:

- `Offset` in millimetres;
- `Tilt U` in degrees;
- `Tilt V` in degrees;
- `Plane size` in millimetres;
- `Tolerance` in millimetres.

The Orientation section adds snap buttons:

- `U -5°`, `U +5°`;
- `V -5°`, `V +5°`;
- `Reset`.

The existing quick plane buttons `XY`, `YZ`, and `XZ` remain available.

## Projected handles

Only two rotation handles are drawn:

- `modifier_split:rotate_x` / `Tilt U`;
- `modifier_split:rotate_y` / `Tilt V`.

They are stable lever handles placed on the plane edge. Dragging a handle changes the plane normal with 5° snaps and then redraws the handle from the updated plane; the handle is not meant to be moved as geometry.

## Implementation notes

Internally, the settings still use `rx_deg` and `ry_deg` for compatibility with presets and serialized tool preferences. `rz_deg` remains supported in the low-level settings parser for backward compatibility, but the Split tool no longer exposes or updates it as a user-facing control.
