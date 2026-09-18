# Live gizmo refresh update

This update makes transform gizmos refresh during active interactions instead of only after the interaction ends.

## Changes

- Added a throttled live gizmo refresh path.
- The refresh is only active during user interactions:
  - free orbit with left drag,
  - right-drag pan,
  - wheel zoom,
  - translation gizmo drag,
  - rotation gizmo drag,
  - scale gizmo drag.
- The adaptive scale frame can now switch visible faces while orbiting, not only after releasing the mouse.
- Translation, rotation, and scale gizmos now stay attached to the selected part while it moves or changes size.

## Performance notes

No permanent camera observer is used. The gizmo is rebuilt with a small throttle during interaction bursts, so the UI avoids the previous heavy camera-observer slowdown while still updating often enough to feel connected to the object.
