# Creator API Diagnostic Lab

The Tool Core Diagnostic panel is the live validation tool for the public Creator API.

Use it to verify that a creator tool can:

1. declare actors through the public API;
2. choose interaction policy explicitly;
3. select and drag points or lines;
4. use smart snap and scene cache;
5. clean all transient state;
6. stay within the production rendering budget.

## Actor controls

The lab exposes enum controls for:

- `point`;
- `line`;
- `circle`;
- `arc`;
- `polyline`.

Each actor can be:

- `fixed` — visual only;
- `selectable` — can be clicked and selected;
- `grabbable` — can be selected and moved.

## Actions

- **API Lab** resets and opens the lab scene.
- **Add actor** creates the selected actor kind with the selected interaction policy.
- **Delete selected** removes selected lab actors through the actor registry.
- **Move selected** moves only selected grabbable actors.
- **Select all** selects every selectable lab actor.
- **API tests** runs the headless Creator API self-test suite.
- **API benchmark** runs focused API timing checks.
- **Full validation** runs API tests, API benchmark and the GUI/gizmo benchmark.
- **Clear** removes lab-owned actors, previews, gizmos and snap targets.

## Rule

The diagnostic itself must use the public `tool_api` path. If a lab feature needs to reach directly into Qt/PyVista/tool-core internals, the Creator API is missing a public capability.


## Pass132 placement clarification

`Add actor` now places the selected actor at the world origin by default. Explicit setup and benchmark scenes can still pass custom positions.
