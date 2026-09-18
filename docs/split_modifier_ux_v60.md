# v60 — Split Modifier UX stabilisation

This pass fixes the v58/v59 Split Modifier migration regressions reported during product use.

## Behaviour changes

- The split plane offset is clamped to the selected model projected bounds along the active plane normal.
- Inspector `offset_mm` and `plane_size_mm` values are refreshed after programmatic drag/clamp updates.
- The displayed plane footprint is derived from the selected model in-plane extent, not from the old global diagonal heuristic.
- The native Projected Drawing handle is attached to the split plane center. There is no floating handle offset anymore.
- The cut location is highlighted with orange intersection segments where the split plane crosses the selected triangles.
- The Split mini overlay is compact: reset/preview/apply/cancel buttons plus one metric line with offset and total triangle count.
- Creator overlay windows are synchronized immediately after a tool opens or reopens, instead of waiting for a later viewport interaction.

## Tests

Added `tests/test_pass1060_split_modifier_ux_regression.py` for:

- offset clamping during drag;
- center-attached handle;
- visible cut line;
- plane size derived from model extent;
- compact overlay contract;
- immediate overlay sync after tool open;
- visible inspector refresh after native drag updates.
