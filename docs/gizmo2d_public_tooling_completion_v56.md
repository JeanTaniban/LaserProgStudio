# v56 — Completion of public Gizmo 2D tooling migration

This pass finishes the built-in tooling migration away from direct `tool_core`
imports for Projected Drawing / Gizmo 2D related tools.

## Migrated areas

- `tooling/gizmo_catalog_benchmark.py`
  - now imports Projected Drawing declarations from `tool_api.projected_drawing`.
  - benchmark datasets still use the packed public primitives (`point_cloud`,
    `segment_batch`, `face_batch`) so dense scenes stay efficient.

- `tooling/plan_trace_2d/editable_source.py`
  - now imports sketch and dimension contracts from public facades:
    `tool_api.sketch` and `tool_api.dimensions`.

- `tooling/plan_trace_2d/snap_targets.py`
  - now obtains projection-cache signatures through `tool_api.scene`.
  - arc screen bounds now use the public Plan 2D arc sampler instead of reaching
    into `tool_core.geometry`.

## Public API additions

- `tool_api.plan2d.dimensions.DimensionStyle` is exported publicly because
  serialized Plan 2D dimensions need to reconstruct their display style.
- `tool_api.scene.projection_cache_signature(ctx)` wraps the internal cache
  signature for high-frequency snap/projection invalidation.

## Packaging guard

`settings/studio_tool_parameters.json` was reset to safe packaged defaults. In
particular:

- Plan Tracer keeps `smart_snap` enabled by default.
- Plan Tracer includes a valid `grid_step` packaged value.
- Texture Projection no longer ships with a test-local image path.

## Verification

- `python scripts/audit_tool_migration.py --strict`
  - `Forbidden imports: 0`
- Focused regression tests:
  - Projected Drawing benchmark
  - Gizmo 2D migration audit
  - Plan 2D API structure
  - Plan Tracer service boundaries/final structure
  - Plan Tracer editable/apply/snap/pattern/motif regressions
  - Packaged Plan Tracer safe defaults

A full `pytest -q -x` still stops on the older contradictory transform renderer
lifecycle test (`test_pass1013_transform_renderer_has_explicit_leak_free_lifecycle`).
That test asks for `clear_creator_viewport_ui` inside `transform_gizmo_renderer.py`,
while the newer `test_pass1016_transform_renderer_never_calls_generic_creator_cleanup`
requires the opposite. This v56 patch does not modify that subsystem.
