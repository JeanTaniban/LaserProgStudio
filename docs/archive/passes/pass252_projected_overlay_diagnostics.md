# Pass 252 — Projected Overlay Diagnostics

## Context

Plan Tracer 2D still had no visible overlay after the projected drawing backend rebind fix. The existing Plan Tracer timing report proved that input and sketch state were alive, but it did not expose the live `ProjectedDrawingOverlay2D` backend lifecycle. The missing information was whether projected drawing primitives disappeared before the backend, during VTK actor creation, or during world-to-display projection.

## Changes

- Added `laserprog_studio.diagnostics.projected_overlay_debug`.
- Added `diagnostics/projected_overlay_debug.jsonl`, gated by debug mode.
- Added events for:
  - ToolContext owner attachment.
  - projected drawing backend binding.
  - renderer store creation.
  - renderer attach/missing states.
  - sync snapshots and sync results.
  - VTK actor creation success/failure/exception.
  - Plan Tracer render before/after/exception.
  - projection scalar fallback.
- Added renderer snapshots to `plan_trace_2d_timings.md/json`.
- Added projected drawing metrics to the Plan Tracer profiler/audit:
  - actors, handles, texts, batches, cells, world points;
  - projected points/handles/texts;
  - projection backend;
  - invalid/outside projected points;
  - sync path counters.
- Added the diagnostic file to the “Files to send” list in the Plan Tracer report.

## Safety fallback

The projected 2D renderer now detects a suspicious projection case: vectorized VTK camera projection reports all points invalid or offscreen for a small overlay batch, while the owner-provided scalar `_world_to_display()` projection remains valid. In that case, it automatically falls back to scalar projection and records a `projection.scalar_fallback` event.

This is intentionally narrow: it should not change normal behavior, but it can recover overlays when the renderer/camera matrix is stale or mismatched.

## Validation

- `python -m pytest tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_renderer_reprojects_on_each_vtk_frame_without_recreating_actors tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_projection_falls_back_when_vector_projection_is_offscreen tests/test_pass1024_plan_tracer_projected_drawing_migration.py -q` → 7 passed.
- `python scripts/quality_gate.py` → OK.

## Next diagnostic package to request

After reproducing the no-overlay bug in Plan Tracer 2D with debug mode enabled, request:

- `diagnostics/projected_overlay_debug.jsonl`
- `diagnostics/plan_trace_2d_timings.md`
- `diagnostics/plan_trace_2d_timings.json`
- `diagnostics/plan_trace_input_debug.jsonl`
- normal app log
