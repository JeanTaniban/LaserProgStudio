# Pass225 — Plan 2D API ownership

## Goal

Move the Plan 2D API from a package-shaped facade to real ownership while
keeping the older import paths compatible.

## Changes

- `tool_api.plan2d.plane` now owns plane picking, raycast anchoring, local XY
  conversion, semantic/display conversion and `Plan2DCoordinateMapper`.
- `tool_api.plan2d.snap` now owns Plan 2D snap result contracts, cursor style
  semantics and angle/square constraint helpers.
- `tool_api.plan2d.actors` now owns the official Plan 2D actor declarations,
  visual metadata, circle/arc sampling previews and cursor/anchor registration.
- `tool_api.plan2d.dimensions` and `tool_api.plan2d.metrics` now own their
  public facades directly.
- `tool_api.planar_drawing`, `tool_api.dimensions` and `tool_api.metrics` are
  now thin compatibility modules that re-export the Plan 2D owners.
- Plan Tracer imports metric and dimension APIs through `tool_api.plan2d`, not
  the legacy top-level facades.

## Tests

- Added `tests/test_pass225_plan2d_api_ownership.py`.
- Full suite: `843 passed, 3 skipped, 81 warnings`.
