# Pass 183 - Native overlay no-overlap policy and fast drag

## Problem

Stacking multiple translucent Qt child overlays on top of each other produced
paint artifacts: the overlay below could be repainted in vertical strips and
could temporarily lose reliable drag hit-testing. Overlay dragging also felt
heavier than necessary because the adapter invalidated parent repaint regions and
updated declarative specs on every mouse move.

## Direction

Creator overlays are runtime-owned UI. Tool authors declare `OverlayWindowSpec`
objects; they do not manage Qt widgets, z-order, repaint regions, drag capture or
collision handling.

The native overlay runtime now uses this policy:

1. draggable Creator overlays must not overlap other visible overlays;
2. during drag, the widget follows the pointer through direct `QWidget.move(...)`;
3. no parent repaint loop is forced on every mouse move;
4. the declarative manager position is committed on release;
5. if clamping or collision separation changes the requested position, the drag
   anchor is rebased so there is no hidden cursor/widget gap.

This favors reliable interaction and stable performance over trying to support
arbitrary translucent widget stacking.

## Implementation

- Added `tool_core.overlay.placement` with a testable rectangle solver.
- `QtOverlayAdapter` applies the solver while placing and dragging overlays.
- Mouse move drag no longer calls parent `update(...)` for old/new geometries.
- The manager state is not rebuilt/synced on every drag move; release commits the
  final position.

## Public API impact

No new tool-level API is required. Existing overlay declarations continue to work
and receive the native behavior automatically.
