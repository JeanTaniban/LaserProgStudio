# Plan Tracer 2D compact command rail refactor

The Plan Tracer floating UI was converted from an oversized sectioned ribbon into a compact command rail.

Key changes:

- The toolbar shell height is derived from the same constants used by the Qt layout.
- Section and button widths use natural label-aware sizes instead of scaling every group to fill unused space.
- The active mode pill is smaller and no longer dominates the viewport.
- Buttons paint as compact cells with visible hit targets, larger readable captions and no ellipsis.
- The Plan Tracer inspector text was shortened and action buttons are stacked vertically instead of crammed into one row.
- Read-only inspector values now wrap, which keeps long status messages readable in the narrow right panel.

This pass deliberately removes the failed large-ribbon direction from the previous iteration. The goal is a clean CAD-style contextual HUD that does not fight the existing top toolbar or steal too much viewport space.
