# Pass121 — Selection actors and clamped overlay drag guard

## Overlay corner drag fix

Draggable Tool Core overlays now handle viewport-corner clamping without building
up a hidden cursor/window offset.

When a movable overlay reaches a viewport edge or corner, the Qt adapter clamps
its visible position and immediately rebases the drag anchor to that clamped
position. This prevents the user from pushing the cursor beyond the overlay,
releasing, then appearing to drag the overlay from beside the painted window.

The adapter also refuses drag starts when Qt reports a press inside an oversized
or stale child-widget rectangle but outside the visible overlay frame.

## Selection actor contract

Tool Core now exposes a shared `ToolActor` contract:

- `ActorInteraction.FIXED`: visible actor, no click/selection/grab behavior.
- `ActorInteraction.SELECTABLE`: click selects it; Shift-click adds it to the
  current selection.
- `ActorInteraction.GRABBABLE`: selectable, and movable only after selection.

Supported actor geometry is declared with `ActorKind`: point, line, circle, arc,
polyline and custom. Hit-testing for points, lines, circles and chained curves is
centralized in `SelectionManager`, so future tools do not need to reimplement
selection distance logic.

## Diagnostic demo

The Tool Core Diagnostic panel now includes **Selection demo**. It builds fixed,
selectable and grabbable points/lines plus a selectable circle through the shared
actor API.

Workflow:

1. click **Selection demo**;
2. click a selectable actor to select it;
3. Shift-click to multi-select;
4. drag a selected grabbable actor to move all selected grabbable actors;
5. selectable-only actors remain selected but do not move.

## Tests

Added `tests/test_pass121_selection_actor_contract.py`.

The full suite passes:

`493 passed, 3 skipped`.
