"""Geometry helpers for native overlay placement.

The Qt adapter keeps the actual widgets as plain child widgets, but overlap
policy must be deterministic and testable without importing PySide.  This module
contains the small rectangle solver used by the runtime to keep draggable
Creator overlays from stacking on top of each other.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayRect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return int(self.x) + int(self.w)

    @property
    def bottom(self) -> int:
        return int(self.y) + int(self.h)

    def moved(self, x: int, y: int) -> "OverlayRect":
        return OverlayRect(int(x), int(y), int(self.w), int(self.h))

    def expanded(self, gap: int) -> "OverlayRect":
        gap = max(0, int(gap))
        return OverlayRect(int(self.x) - gap, int(self.y) - gap, int(self.w) + 2 * gap, int(self.h) + 2 * gap)

    def intersects(self, other: "OverlayRect") -> bool:
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )


def clamp_overlay_position(
    x: int,
    y: int,
    size: tuple[int, int],
    viewport_size: tuple[int, int],
    *,
    margin: int = 12,
) -> tuple[int, int]:
    """Clamp an overlay top-left position inside a viewport."""
    w, h = int(size[0]), int(size[1])
    vw, vh = int(viewport_size[0]), int(viewport_size[1])
    margin = int(margin)
    max_x = max(margin, vw - w - margin)
    max_y = max(margin, vh - h - margin)
    return max(margin, min(int(x), max_x)), max(margin, min(int(y), max_y))


def avoid_overlay_overlap(
    x: int,
    y: int,
    size: tuple[int, int],
    blockers: list[OverlayRect] | tuple[OverlayRect, ...],
    viewport_size: tuple[int, int],
    *,
    margin: int = 12,
    gap: int = 8,
    max_iterations: int = 8,
) -> tuple[int, int]:
    """Return a nearby non-overlapping top-left position.

    The solver is intentionally small and deterministic.  It resolves collisions
    by applying the minimum translation needed to separate the moving rectangle
    from the first blocking rectangle it intersects, clamps the result back into
    the viewport, and repeats a few times for chains of overlays.  This is cheap
    enough to run during overlay drag and avoids the repaint artifacts caused by
    translucent Qt child widgets covering each other.
    """
    if not blockers:
        return clamp_overlay_position(x, y, size, viewport_size, margin=margin)

    width, height = int(size[0]), int(size[1])
    x, y = clamp_overlay_position(x, y, (width, height), viewport_size, margin=margin)
    rect = OverlayRect(x, y, width, height)
    expanded_blockers = [blocker.expanded(gap) for blocker in blockers]

    for _ in range(max(1, int(max_iterations))):
        moved = False
        for blocker in expanded_blockers:
            if not rect.intersects(blocker):
                continue
            # Four possible separating translations.  Choose the smallest
            # movement; on ties prefer vertical movement because horizontal
            # mouse motion is common when users drag palettes along a toolbar.
            candidates = [
                (blocker.x - rect.right, 0),
                (blocker.right - rect.x, 0),
                (0, blocker.y - rect.bottom),
                (0, blocker.bottom - rect.y),
            ]
            dx, dy = min(candidates, key=lambda item: (abs(item[0]) + abs(item[1]), 0 if item[0] == 0 else 1))
            nx, ny = clamp_overlay_position(rect.x + dx, rect.y + dy, (width, height), viewport_size, margin=margin)
            if (nx, ny) == (rect.x, rect.y):
                # If the minimum translation is blocked by a viewport edge,
                # evaluate edge-clamped alternatives around the blocker and keep
                # the closest valid one.
                alternatives: list[tuple[int, int]] = []
                raw = [
                    (blocker.x - width - gap, rect.y),
                    (blocker.right + gap, rect.y),
                    (rect.x, blocker.y - height - gap),
                    (rect.x, blocker.bottom + gap),
                    (margin, rect.y),
                    (int(viewport_size[0]) - width - margin, rect.y),
                    (rect.x, margin),
                    (rect.x, int(viewport_size[1]) - height - margin),
                ]
                for ax, ay in raw:
                    cx, cy = clamp_overlay_position(ax, ay, (width, height), viewport_size, margin=margin)
                    candidate = OverlayRect(cx, cy, width, height)
                    if all(not candidate.intersects(other) for other in expanded_blockers):
                        alternatives.append((cx, cy))
                if alternatives:
                    nx, ny = min(alternatives, key=lambda pos: abs(pos[0] - rect.x) + abs(pos[1] - rect.y))
                else:
                    # The viewport is too crowded.  Keep the clamped requested
                    # position rather than jittering endlessly.
                    return int(rect.x), int(rect.y)
            rect = rect.moved(nx, ny)
            moved = True
            break
        if not moved:
            return int(rect.x), int(rect.y)
    return int(rect.x), int(rect.y)


def constrain_overlay_drag_position(
    requested_x: int,
    requested_y: int,
    previous_x: int,
    previous_y: int,
    size: tuple[int, int],
    blockers: list[OverlayRect] | tuple[OverlayRect, ...],
    viewport_size: tuple[int, int],
    *,
    margin: int = 12,
    gap: int = 8,
) -> tuple[int, int]:
    """Constrain a live overlay drag without solver-induced jumps.

    This function is the hot path used while the user is dragging an overlay.
    Unlike :func:`avoid_overlay_overlap`, it does not try to find a nearby free
    placement by pushing the window around a blocker.  It behaves like a hard
    wall: first try the requested position, then a single-axis slide, then keep
    the previous position.  This keeps Qt child-widget dragging smooth and makes
    soft-wall rebasing predictable when the runtime hits a viewport edge or another
    overlay.
    """
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        return int(previous_x), int(previous_y)

    requested_x, requested_y = clamp_overlay_position(
        requested_x, requested_y, (width, height), viewport_size, margin=margin
    )
    previous_x, previous_y = clamp_overlay_position(
        previous_x, previous_y, (width, height), viewport_size, margin=margin
    )
    expanded_blockers = [blocker.expanded(gap) for blocker in blockers]

    def valid(x: int, y: int) -> bool:
        rect = OverlayRect(int(x), int(y), width, height)
        return all(not rect.intersects(blocker) for blocker in expanded_blockers)

    if valid(requested_x, requested_y):
        return int(requested_x), int(requested_y)

    # Keep natural sliding along walls/other overlays.  Try the axis with the
    # largest pointer movement first; this feels better on diagonal drags.
    dx = abs(int(requested_x) - int(previous_x))
    dy = abs(int(requested_y) - int(previous_y))
    candidates = (
        ((requested_x, previous_y), (previous_x, requested_y))
        if dx >= dy
        else ((previous_x, requested_y), (requested_x, previous_y))
    )
    for cx, cy in candidates:
        cx, cy = clamp_overlay_position(cx, cy, (width, height), viewport_size, margin=margin)
        if valid(cx, cy):
            return int(cx), int(cy)

    return int(previous_x), int(previous_y)


def pointer_inside_overlay_rect(
    pointer_x: int,
    pointer_y: int,
    rect: OverlayRect,
    *,
    tolerance: int = 0,
) -> bool:
    """Return whether a pointer is still inside an overlay rectangle.

    This is part of the native overlay-drag contract.  The runtime does not warp
    the OS cursor when an overlay hits a viewport edge or another overlay.  If a
    constrained drag lets the pointer leave the real overlay rectangle, the drag
    must be cancelled instead of preserving a stale grab offset.
    """
    tolerance = max(0, int(tolerance))
    x = int(pointer_x)
    y = int(pointer_y)
    return (
        int(rect.x) - tolerance <= x < int(rect.right) + tolerance
        and int(rect.y) - tolerance <= y < int(rect.bottom) + tolerance
    )
