# Pass112 — Tool Core gizmo shapes and camera-size update modes

## Goal

The Tool Core Diagnostic handle demo now focuses on one readable size (`S`) and compares styles instead of comparing handle scale. This avoids visual noise while still testing the shared gizmo layer deeply.

## Added handle styles

Official point styles now include:

- `solid`
- `ring`
- `target`
- `diamond`
- `square`
- `arrow`
- `axis`
- `chevron`
- `triad`

The new shapes are drawn as persistent line-batch guides around the point handle. They are not rebuilt by clearing the viewport; their PolyData is updated in place.

## Camera-size update modes

The diagnostic panel includes a button:

- `Camera size: end`
- `Camera size: live`

`end` updates the world-space guide size once after the camera movement ends. This is the safer default.

`live` refreshes the guide geometry during camera motion through the existing throttled gizmo refresh path. This tests whether continuous updates are acceptable on the current machine.

## Performance rule

Future production tools should not own this behavior themselves. They should expose persistent handles through Tool Core and let the shared layer update hover/grab state, position, and camera-dependent world size.
