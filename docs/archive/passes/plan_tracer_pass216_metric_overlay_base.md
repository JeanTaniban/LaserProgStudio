# Pass P216 — Plan Tracer metric overlay base

## Goal

Start the live metric-input foundation without turning the Creator API or Plan Tracer into a monolith.

This pass introduces a temporary **Metric Edit** step after visual placement:

1. first click places the construction anchor;
2. pointer movement/snaps stay focused on visual placement;
3. second click creates provisional geometry and compiles topology;
4. a compact metric overlay appears at the top of the viewport below the drawing toolbar;
5. `Validate` commits the provisional geometry as one undoable command;
6. `Cancel` restores the pre-placement snapshot.

## Architecture

New modules:

- `tool_core/metrics/types.py` — typed fields and session state;
- `tool_core/metrics/parser.py` — length/angle parsing and formatting;
- `tool_core/metrics/session.py` — common metric sessions such as line and circle;
- `tool_api/metrics.py` — small public facade for Creator tools.

The metric system is intentionally temporary and separate from persistent `Dimension` entities and future driving constraints.

## Plan Tracer integration

Implemented for the base pass:

- Line: `Length` + `Angle` session after the second click;
- Circle: `Radius` + `Diameter` session after the second click;
- top-center metric overlay with `Validate` / `Cancel` buttons;
- transaction snapshot stored before the second click;
- `Validate` records one command from that snapshot to the current compiled state;
- `Cancel` restores the snapshot;
- a tool-facing `apply_metric_value(...)` hook exists for the next UI-field callback pass.

## Remaining work

- connect Qt text-field editing callbacks to `apply_metric_value(...)`;
- extend the same transaction pattern to Rectangle, Half-circle and Arc;
- add keyboard workflow: Enter validate, Escape cancel, Tab next field;
- add optional `Create dimension from metric` later, without mixing metrics with constraints.
