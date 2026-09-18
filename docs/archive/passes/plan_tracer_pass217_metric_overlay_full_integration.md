# Plan Tracer P217 — Full metric overlay integration

## Goal

Finish the metric-edit base started in P216 without turning the tool or API into
a monolith.  Metric input remains a temporary placement workflow, not a permanent
constraint solver.

## Implemented

- Added `tool_core.metrics.geometry`, a UI-free helper module for rebuilding
  draft geometry from metric values.
- Added metric sessions for:
  - rectangle: `Width`, `Height`;
  - half-circle: `Radius`, `Diameter`, `Angle`;
  - arc: `Radius`, `Angle`.
- Kept the public API facade in `tool_api.metrics` small; tools consume typed
  sessions and the API builds the overlay window.
- The Qt overlay adapter now renders enabled text/number fields as editable
  `QLineEdit` widgets and notifies the active tool through
  `on_overlay_field_changed(...)`.
- Plan Tracer now accepts overlay field commits and rebuilds the active draft
  from its clean base snapshot.
- Metric edit is integrated for:
  - Line: length / angle;
  - Rectangle: width / height;
  - Circle: radius / diameter;
  - Half-circle: radius / diameter / angle;
  - Arc: radius / angle.
- Starting another viewport action or changing tool mode implicitly validates the
  current metric draft, while Escape still cancels and restores the base snapshot.
- Validation creates a single undo action for the accepted placement.

## Architecture notes

The new metric code is split intentionally:

- `tool_core/metrics/types.py`: typed field/session primitives.
- `tool_core/metrics/parser.py`: units and parsing.
- `tool_core/metrics/session.py`: standard field presets by shape.
- `tool_core/metrics/geometry.py`: pure 2D reconstruction helpers.
- `tool_api/metrics.py`: compact public facade and overlay builder.

The Plan Tracer stores only the placement draft references and base snapshot; it
never mutates already-compiled topology in place when a metric changes.  Instead,
it restores the snapshot, reapplies the draft spec, recompiles, and refreshes the
visuals.

## Validation

- Full test suite: `819 passed, 3 skipped`.
- `compileall` OK on `src` and `tests`.

## Remaining risks

- The Qt field editing path is now wired, but visual testing in the real app is
  still required for keyboard focus, tab order, and field sizing.
- Arc radius/angle editing uses a stable minor-arc reconstruction.  This is good
  enough for the first integrated metric pass, but future work should expose arc
  direction/major-arc intent explicitly.
