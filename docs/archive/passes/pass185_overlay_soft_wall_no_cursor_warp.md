# Pass 185 - Overlay soft-wall drag without cursor warping

## Why

Warping the operating-system cursor during an overlay drag caused visible stutter and could leave the application in a bad mouse-capture state after focus changes. Qt also documents that explicit mouse grabs make one widget receive all mouse events until release and warns that mouse grabbing can lock input, so overlay drag must avoid that path for normal operation.

## Direction

Overlay drag is native runtime behavior. A tool declares overlays through `ctx.overlay`; it must not move Qt widgets, warp the cursor, grab the mouse, or resolve collisions locally.

The runtime now uses a **soft-wall** policy:

1. move the overlay with a direct `QWidget.move(...)` fast path;
2. clamp it against the viewport and other overlays;
3. when blocked, stop the overlay and rebase the drag origin to absorb the blocked pointer delta;
4. never call cursor warping during drag;
5. defensively release stale grabs on focus loss / hide / release.

The cursor may physically leave the rectangle while the overlay is blocked, but there is no hidden payback distance: reversing direction moves the overlay immediately. This gives a clean wall feeling without jitter or platform capture bugs.
