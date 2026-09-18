# Pass 77 - Tool UI English cleanup

This pass cleans the right-side Tool panel UX across fabrication tools, surface tools, planar tools, and modifiers.

## Changes

- Tool panels now use concise English labels and status messages.
- Long workflow notes were removed from the panels and kept in Help documents instead.
- Joint builder, Vent generator, Plan tracer, Relief, Simplify, Hollow, Extrude down, Repair, Materials, Texture projection, Box, Cavity volume and Primitives now use compact default statuses.
- Controller reports and operation errors shown in the Tool panel were translated to English.
- Box and cavity-volume reports now use English naming.
- Added regression coverage to keep tool-panel strings short and English.

## Validation

- `351 passed, 3 skipped`
