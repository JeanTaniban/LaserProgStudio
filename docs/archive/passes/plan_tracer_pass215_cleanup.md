# Pass 215 — Plan Tracer cleanup and documentation

## Goal

Stabilize the API/tool split after the curve-topology pass without adding a new
feature-heavy drawing mode.

## Done

- Added `tool_core.sketch.validation` as a separate validation module.
- Compiler now attaches compact validation notes to `SketchCompileResult`.
- Fixed `delete_arc_cascade(...)` so dimensions attached to generated companion
  lines are removed deterministically and no stale `line_id` local is used.
- Added architecture documentation for the Plan Tracer sketch kernel.
- Updated Plan Tracer docs to reflect that curve intersections are now part of
  the topology kernel rather than a future limitation.

## Intentional boundaries

- No Qt/PyVista logic was added to the sketch kernel.
- Validation reports issues, but it does not reject open sketches or unused
  construction points.
- The Plan Tracer remains an API consumer; it should not own face solving,
  dimension layout or snap-priority policy.
