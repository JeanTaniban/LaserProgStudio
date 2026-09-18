# Pass 252 — Projected Drawing overlay scene rebuild reattach

## Problem

Plan Tracer 2D and Texture Projection could stop displaying their 2D overlay after the API boundary cleanup and projected drawing backend migration.

The v82 diagnostics proved that the tools were still alive and that the Projected Drawing backend was bound, but the visible overlay could be missing after a normal 3D scene rebuild:

- Plan Tracer had live projected handle primitives.
- Texture Projection opened through Creator UI.
- The renderer store and sync loop were active.
- The 3D scene was rebuilt after picking / tool changes.

## Root cause

The application-side `ProjectedDrawingOverlay2D` caches VTK `vtkActor2D` instances for speed. A PyVista / VTK scene rebuild can clear renderer props directly without calling the projected overlay dispose path.

After that happens:

1. The Python overlay renderer still has cached `_visuals`, `_handle_visuals`, and `_text_visuals`.
2. The Projected Drawing manager still has live primitives.
3. The cached actor objects are no longer attached to the current VTK renderer.
4. The no-op / camera-only fast path sees the same registry revision and camera signature, so it does not rebuild the actors.
5. Result: Plan Tracer 2D / Texture Projection appear to have no overlay although their internal state is still valid.

## Fix

Added a renderer membership repair path in `application/projected_drawing_2d.py`:

- Detect whether cached actors are still attached to the live renderer.
- Support both real VTK renderers (`GetViewProps`) and test fake renderers (`renderer.actors`).
- Re-add missing cached batch actors, handle actors, and text actors.
- Mark cached geometry as projection-dirty after reattachment.
- Invalidate projection signature so a fresh projection can happen.
- Request a render even if the normal sync path would otherwise be a no-op.
- Add diagnostics:
  - `renderer.reattach_missing_actors`
  - `renderer_reattach_count`
  - `last_renderer_reattached_actors`

## Regression test

Added `test_projected_drawing_reattaches_cached_actors_after_renderer_prop_clear`.

The test simulates a global scene rebuild by clearing `renderer.actors` directly, then confirms that a normal `sync_from_manager(force=False)` reattaches the cached projected overlay actors without requiring a registry revision change.

## Validation

- `python -m pytest tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_reattaches_cached_actors_after_renderer_prop_clear tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_renderer_reprojects_on_each_vtk_frame_without_recreating_actors tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_lazy_repairs_plain_owner_assignment -q` → OK
- `python -m pytest tests/test_pass306_texture_projection_projected_drawing_migration.py tests/test_pass1024_plan_tracer_projected_drawing_migration.py tests/test_pass1058_modifier_projected_drawing_2d.py -q` → OK
- `python scripts/quality_gate.py` → OK

## Notes

This fix does not roll back the API boundary cleanup. It completes the migration by making the new application renderer resilient to renderer prop clears performed outside the Projected Drawing backend.
