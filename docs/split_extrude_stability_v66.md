# v66 — Split rotation stability and Extrude Down hole preservation

## Split Modifier

- Rotation handles now use a stable drag baseline, similar in spirit to the Transform Rotate tool: the drag is measured from the grab start instead of being accumulated from a handle that is redrawn every frame.
- Only two useful tilts remain: `Tilt U` and `Tilt V`.
- Rotation snap can be toggled with `Snap rotation`.
- Snap is enabled by default and intentionally not persisted, so test/stress runs cannot package a disabled default.
- Overlay/inspector Cancel exits the tool even when no preview exists.

## Extrude Down

- Cross-section contour reconstruction no longer unions filled nested rings.
- Holes are reconstructed as real polygon interiors before generating vertical support walls and the bottom cap.
- A face/section with an internal hole now extrudes down as a closed solid that preserves the hole instead of becoming only an outer envelope.

## Tests

Added regression coverage for:

- Split Cancel without preview.
- Split rotation snap toggle labels/metadata.
- Extrude Down on a closed box section with a square hole.
