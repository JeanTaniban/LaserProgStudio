# Pass111 - Viewport guides and diagnostic gizmo contrast

## Goal

Fix two usability issues reported after Pass110:

- diagnostic handles/guides were too close to white, making them unreadable on a white/bright viewport;
- the grid/workspace guides were only initialized through scene rebuilds, so a brand-new empty scene could remain visually blank until the first object was added.

## Changes

- Reworked official Tool Core point palettes with darker, high-contrast fixed/grabbable/hover/grabbed/selected colors.
- Changed diagnostic guide rings/crosses to use style-owned guide colors instead of hardcoded white/black.
- Kept diagnostic guide rendering batched and persistent; guides are split by style color without going back to an actor-per-handle model.
- Changed diagnostic linework to a dark slate color so lines remain visible on the bright viewport background.
- Added `initialize_empty_viewport_guides()` to the floor grid UI layer.
- The empty viewport now sets a soft off-white background, builds the grid, sets a safe empty-scene camera, and renders without waiting for a mesh.
- `_post_start()` now calls the empty viewport initializer before the initial render.
- The plotter background is also set immediately after the QtInteractor is created.

## Validation

- Targeted Tool Core / diagnostic / floor grid tests passed.
- Python compilation for `src` and `tests` passed.
- A full test run was started with `-x`; it reached 62% with no new failure before timeout.
