# Duplicate Pivot and Folding Snap — v148

## Scope

This pass corrects two interaction contracts. It does not change prefab file
formats, Folding persistence, mesh deformation, or generated sketch topology.

## Duplicate prefab pivot

Prefab creation now has three strictly ordered states:

1. select the source sketch geometry;
2. click the pivot in the viewport;
3. enter the prefab name in the dedicated modal.

The pivot state uses an instruction-only `OverlayWindowSpec`. It deliberately
contains no buttons. The normal Duplicate command deck is also hidden while the
name modal is open, leaving only the action relevant to the current state.
Escape remains available as the standard way to cancel the current step.

### Invariants

- `capture_payload` remains `None` until a pivot click is received;
- the name modal is never visible during pivot capture;
- no Apply/Done-style action can bypass the pivot;
- after the pivot click, the payload and pivot are captured before the name
  modal is shown.

## Folding hinge-axis placement

`PLACE_START` and `PLACE_END` now resolve pointer positions through the public
Plan 2D API:

1. intersect the pointer ray with the selected face plane;
2. query `plan2d.smart_snap_on_plan(...)`;
3. during `PLACE_END`, apply the official 45° constraint when Shift is held;
4. clamp the final point back to the face plane;
5. render it with `plan2d.register_plan_cursor(...)`.

The previous local yellow cursor primitive was removed. The official cursor
exposes the same semantic styles used by Plan Tracer, including free, vertex,
edge, midpoint, intersection, center, quadrant, angle and grid feedback.

### Invariants

- preview and click call the same point resolver;
- Shift affects both live preview and committed endpoint;
- the pending hinge interval terminates at the resolved cursor position;
- cursor metadata reflects the active snap or angle constraint;
- Folding imports only the public `tool_api.plan2d` boundary.

## Regression coverage

The focused Duplicate/Folding suite contains 68 passing tests. New v148 cases
verify:

- the pivot prompt contains one instruction and no buttons;
- the name modal appears only after pivot capture;
- Folding consumes Smart Snap results and renders the official cursor;
- Shift constrains both the hover endpoint and committed axis.
