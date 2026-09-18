# v62 — Split Modifier Apply and rotation handles

## Objective

This patch stabilises the Split modifier after the Projected Drawing 2D migration.

## Behaviour changes

- `Apply` from the Split mini overlay or inspector now performs the complete user flow:
  1. generate the preview if it does not already exist;
  2. commit the preview to the document;
  3. close the Split tool.
- The host/global Apply path remains compatible with the normal Creator lifecycle.
- The Split plane now exposes three projected ring handles:
  - X tilt handle;
  - Y tilt handle;
  - Z twist/orientation handle.
- Rotation handle drags update `rx_deg`, `ry_deg` or `rz_deg` in the inspector, switch the preset to `custom`, recompute the plane size, clamp the offset inside the selected model, and redraw the projected plane immediately.
- The translation handle remains attached to the centre of the plane and still clamps the offset inside the selected model bounds.

## Regression coverage

Added tests cover:

- rotation handles are present, projected and grabbable;
- dragging a rotation handle updates the inspector and marks the preset custom;
- inspector/overlay Apply auto-generates a preview, commits it, and requests tool close.
