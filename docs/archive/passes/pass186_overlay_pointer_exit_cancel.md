# Pass 186 - Overlay pointer-exit drag cancel

## Problem

Soft-wall overlay drag no longer warps the OS cursor, which fixed stutter and stale platform mouse-grab issues. However, a constrained overlay can remain blocked against a viewport edge or another overlay while Qt continues to route mouse-move events from the original button press. If the pointer leaves the visible overlay rectangle in that state, the runtime would keep a stale pointer/anchor offset.

## Direction

The Creator overlay runtime keeps the no-warp rule. It does not try to clamp the operating-system cursor. Instead, a constrained drag is cancelled as soon as the pointer leaves the real overlay rectangle.

## Runtime contract

During native overlay drag:

1. the overlay moves through the direct `QWidget.move(...)` fast path;
2. live placement is constrained by viewport and overlay blockers;
3. when constrained, the runtime checks whether the pointer is still inside the dragged overlay rectangle;
4. if the pointer is outside, the runtime cancels the drag, commits the current position, clears drag offsets and swallows the matching release event;
5. tools never implement this logic locally.

This avoids cursor warping, avoids hidden offset accumulation, and keeps the next click/drag clean.
