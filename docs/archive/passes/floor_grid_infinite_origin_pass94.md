# Pass 94 - Infinite-style floor grid and origin marker

This pass reworks the 3D floor grid display.

## Changes

- Replaced the single flat grid actor with layered grid actors:
  - thin minor lines;
  - clearer major lines every fifth visible grid step;
  - dedicated X and Y axis lines;
  - a circular origin marker with a crosshair;
  - screen-facing labels for `O 0,0`, `+X`, and `+Y` when PyVista labels are available.
- The grid extent now always includes both the current scene bounds and the world origin.
- The grid span is intentionally much larger than the object bounds so the workplane reads as an infinite grid in normal use.
- Large scenes automatically increase the visible minor step to keep the actor count bounded and responsive.
- Grid actor removal now handles the new multi-actor representation as well as old single-actor grids.

## Validation

Added tests covering:

- origin inclusion even when the scene is offset;
- separation of minor lines, major lines, axes, and origin marker;
- major grid spacing policy.
