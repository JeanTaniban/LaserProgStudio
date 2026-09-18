# Pass221 — Plan Tracer coordinate and snap-target split

## Goal

Continue the Plan Tracer structure cleanup after the service-boundary pass.  The
main issue left by Pass220 was that `snap.py` still owned too much central logic:
coordinate conversion, live snap-target export, cursor updates and drag snapping.
This pass reduces that concentration without changing the user workflow.

## Changes

- Added `tooling/plan_trace_2d/coordinate_mapper.py`.
  - Owns display-world ↔ semantic-world ↔ sketch-XY conversions.
  - Owns arc sampling in display space.
  - Provides `add_or_reuse_point_from_display_world(...)` for drawing and dimension placement.
- Added `tooling/plan_trace_2d/snap_targets.py`.
  - Owns live point/line/arc/circle/anchor snap-target construction.
  - Keeps cursor/drag code in `snap.py` focused on interaction instead of scene-target export.
- Updated drawing, dimensions and sketch-sync services to use `services.coordinates` instead of reaching through `services.snap` for conversion helpers.
- Promoted `tool_api.planar_drawing`, `tool_api.dimensions` and `tool_api.metrics` from compatibility domains to active public API domains, matching the Tool Creator documentation.

## Result

`PlanTrace2DSnapService` is now focused on:

- anchor hover/pick;
- cursor update;
- drawing press routing;
- shift constraints;
- snap-aware drag resolution.

`PlanTrace2DCoordinateMapper` is now the single place for the Plan Tracer plane-depth contract.

## Validation

- Full test suite: `830 passed, 3 skipped, 81 warnings`.
- Added `tests/test_pass221_plan_tracer_coordinate_split.py`.
- Existing Plan Tracer regression tests continue to pass.
