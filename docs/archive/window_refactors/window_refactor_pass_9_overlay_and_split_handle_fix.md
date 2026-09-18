# Window refactor pass 9 — transform overlay and split handle fix

## Changes

- Separated two UI concepts that were incorrectly coupled:
  - **Application Light UI**: both left and right side panes are collapsed.
  - **Transform overlay mode**: the right inspector is collapsed, regardless of the left pane.
- The Light UI toolbar button now tracks only the full Light UI state.
- The transform overlay now appears when the right inspector is closed, even if the left project/parts panel remains open.
- Tool open/close restore now preserves the previous compact splitter layout instead of always restoring `[0, center, 0]`.
- Rebuilt the split-plane handle from explicit `Cylinder + Cone` primitives rather than `pyvista.Arrow(scale=...)`.

## Why

`pyvista.Arrow(scale=handle_len, shaft_radius=..., tip_radius=...)` scales the whole source after applying radii. Passing world-space radii and a numeric scale therefore multiplies the arrow width again, which caused the oversized yellow mushroom shape.

The split handle now uses explicit world dimensions, camera-derived length, and much thinner radii.

## Guard rails

Static tests now verify:

- Light UI still requires both side panes to be collapsed.
- Transform overlay depends only on the right inspector.
- Tool lifecycle restores the saved compact splitter state.
- Split-plane handle no longer uses the old oversized `pv.Arrow(... scale=handle_len ...)` path.
