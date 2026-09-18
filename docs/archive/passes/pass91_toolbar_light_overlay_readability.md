# Pass 91 — Toolbar and Light UI transform overlay readability

## Goal
Improve the visibility and stability of the top toolbar icons and the compact Light UI transform overlay.

## Changes
- Removed the startup splash text `Preparing boolean engine...` while keeping boolean backend warmup active.
- Enlarged configurable top-toolbar buttons from 56 px to 68 px and icon rendering from 34 px to 46 px.
- Increased top toolbar margins, spacing, palette button size, trash button size, and scroll area height so Qt has enough space to render the larger icons without clipping.
- Reworked the compact Light UI transform overlay:
  - `X`, position, rotation and scale controls now live in a fixed-width left cluster.
  - The overlay uses a stable preferred width, so the left cluster no longer shifts when position/rotation/scale changes the right-side fields.
  - Transform overlay buttons are larger and use larger icons.
  - Axis fields use fixed widths to prevent mode-dependent layout drift.
  - Overlay labels, separator and buttons have clearer contrast and stronger borders.
- Normalized every toolbar/transform PNG icon to a consistent visual box, brighter strokes and thicker lines.

## Notes
The boolean backend warmup still starts in the background; only the visible boot-status text was removed.
