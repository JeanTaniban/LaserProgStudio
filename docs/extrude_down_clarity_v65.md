# v65 — Extrude Down clarity pass

Extrude Down now follows the Split v64 UX rule of showing a single, stable plane control, but it deliberately stays Z-only.

## Product rule

Extrude Down is a vertical support operation. The support plane is always horizontal and the generated geometry is extruded down to `Ground Z`. Tilt controls were not added because a tilted support plane would imply a different geometry operation than the current `extrude_selected_meshes_down` backend.

## Changes

- The Projected Drawing handle is attached to the centre of the support plane instead of floating above it.
- The projected overlay marks the true cut contour with a thicker orange segment batch.
- The plane face is tagged as `horizontal_only`; the handle is tagged as `vertical_only` and `attached_to_plane_center`.
- The inspector exposes clear Z nudges: `Z -1 mm`, `Z +1 mm`, `Mid`.
- Dragging the handle updates both `Plane Z` and `Plane height`, then requests a visible inspector refresh.
- Programmatic Z edits are clamped slightly inside the selected model bounds so the preflight does not land on an invalid equality edge.
- Apply from the overlay or inspector now performs Preview if needed, commits the preview, and closes the tool.
- The mini overlay is compact: one metric line plus Preview / Apply / Cancel buttons.

## Tests

Covered by `tests/test_pass1065_extrude_down_clarity.py` plus the existing Extrude Down and Split regression suites.
