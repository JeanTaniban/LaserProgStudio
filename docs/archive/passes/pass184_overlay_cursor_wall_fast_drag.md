# Pass 184 - Native overlay soft-wall fast drag

## Goal

Make draggable Creator overlays feel fluid while keeping the native no-overlap rule.

## Runtime policy

During live overlay drag the Qt adapter no longer runs the general placement solver. It uses a cheap hard-wall constraint:

1. try the requested position;
2. try a one-axis slide if one axis is free;
3. otherwise keep the previous visible position.

When the requested pointer movement is blocked by the viewport or another overlay, the runtime applies a soft-wall rebase so the blocked pointer delta is absorbed without warping the OS cursor. This avoids hidden cursor/window distance and makes leaving the wall immediate and predictable.

Diagnostics are sampled during mouse move events instead of recorded for every event, while press/release remain fully recorded. The drag hot path still avoids layout rebuilds, manager syncs and parent repaint loops.

## API direction

Tool authors only declare overlays through `ctx.overlay`. Overlay drag, collision avoidance, soft-wall rebasing, z-order and final position commit are native runtime behavior and must not be reimplemented by tools.
