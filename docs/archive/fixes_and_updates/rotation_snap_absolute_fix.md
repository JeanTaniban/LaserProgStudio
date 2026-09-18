# Rotation snap absolute fix

The rotation snap now targets the absolute inspector angle of the selected part instead of the relative mouse drag delta.

Previous behavior:

- a part already rotated to 15 deg could snap to 15 / 60 / 105 deg;
- the inspector could show values such as 15.5216 or 0.376 when the user expected 0 deg.

New behavior:

- the raw mouse drag still produces a delta angle;
- the code computes `start_angle + delta` for the active rotation axis;
- that absolute value is snapped to the configured angle step;
- the snapped absolute value is converted back to the delta that must be applied to the mesh.

Example:

- start angle: 15.5 deg;
- target snap: 0 deg;
- applied mesh delta: -15.5 deg;
- inspector result: 0 deg.

This keeps the visible inspector values aligned with the snap grid: 0 / 45 / 90 / 135 / 180 / etc.
