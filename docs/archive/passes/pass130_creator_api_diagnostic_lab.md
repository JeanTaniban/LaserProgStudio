# Pass130 — Creator API Diagnostic Lab

Pass130 turns the Tool Core Diagnostic tool into a focused validation lab for the public Creator API.

## What changed

- The right diagnostic panel is now centered on the Creator API Lab instead of a collection of older isolated demos.
- The panel exposes enum-style controls for:
  - actor kind: point, line, circle, arc, polyline;
  - actor interaction: fixed, selectable, grabbable;
  - move preset: +X, -X, +Y, -Y, +X+Y.
- The visible diagnostic actions are now:
  - API Lab;
  - Add actor;
  - Delete selected;
  - Move selected;
  - Select all;
  - API tests;
  - API benchmark;
  - Full validation;
  - Clear.
- The interactive viewport path now uses `tool_api` actor factories, the owner-scoped actor registry, public selection/grab helpers, scene cache, smart snap, previews and gizmos.
- Old diagnostic entry points remain importable for regression tests, but they are no longer the visible workflow.

## API validation coverage

The new lab verifies:

- creation of all actor kinds through `tool_api.actors`;
- fixed/selectable/grabbable behaviour;
- point and line selection in the viewport;
- Shift-style multi-selection through the common selection manager;
- movement of selected grabbable actors;
- deletion through the actor registry;
- smart snap with tool/UI targets;
- scene cache rebuild/invalidation;
- cleanup of actors, gizmos, previews and snap targets;
- benchmark timing for add/remove, hit-test, move, snap and visual declaration.

## Production rendering policy

The lab keeps the production rendering rules explicit:

- no remove/add actor churn during interaction;
- point actors go through persistent gizmo handles;
- lines/arcs/circles/polylines are rendered as batched preview linework;
- text is not part of raw mouse-move updates;
- light render is used during movement;
- full validation combines API tests, API benchmark and GUI/gizmo benchmark.

## Tests

Pass130 adds `tests/test_pass130_creator_api_diagnostic_lab.py`.

Full suite after the pass:

```txt
534 passed, 3 skipped
```


## Pass132 placement clarification

`Add actor` now places the selected actor at the world origin by default. Explicit setup and benchmark scenes can still pass custom positions.
