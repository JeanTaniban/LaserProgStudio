# Pass 253 — Projected Drawing overlay foreground layer fix

## Trigger

The v85 deep diagnostics confirmed that Plan Tracer 2D and Texture Projection still had no visible overlay even though the Projected Drawing 2D backend was active.

## Diagnostic conclusion

The failing state was no longer a missing API binding:

```text
generated primitives -> ProjectedDrawingManager -> ProjectedDrawing2D renderer -> VTK actors
OK                   -> OK                      -> OK                         -> OK
```

The v85 report showed Plan Tracer with:

- `visible: True`
- `actors: 6`
- `handles: 6`
- `live_vtk_present_actors: 6`
- `live_vtk_visible_actors: 6`
- `last_projection_invalid_points: 0`
- `last_projection_outside_points: 0`
- `likely_breakpoint: unknown_viewport_composition`

That points to viewport composition: `vtkActor2D` props attached to the main PyVista renderer were present and visible from VTK's point of view, but were not actually composed into the user's Windows/VTK viewport.

Texture Projection showed the same class of state: Projected Drawing data existed (`batches`, `handles`, `world_points`) but the overlay was not visible. Therefore the bug was in the shared Projected Drawing 2D presentation layer, not in Plan Tracer or Texture Projection individually.

## State machines

### Broken v85 state

```text
Tool opens
  -> ToolContext backend bound
  -> ProjectedDrawingManager receives handles/batches
  -> ProjectedDrawing2D creates vtkActor2D props
  -> props are added to main renderer
  -> props report present=True and visible=True
  -> Qt/PyVista composition does not show them
```

### Fixed v86 state

```text
Tool opens
  -> ToolContext backend bound
  -> ProjectedDrawingManager receives handles/batches
  -> ProjectedDrawing2D asks owner for foreground overlay renderer
  -> owner._ensure_gizmo_overlay_renderer() creates/repairs layer-1 renderer
  -> vtkActor2D props are added to layer-1 foreground renderer
  -> projection still uses the main renderer camera
  -> render request composites foreground overlay above the 3D scene
```

## Code change

`src/laserprog_studio/application/projected_drawing_2d.py`

- Added `_foreground_renderer()`.
- `_ensure_renderer()` now prefers the existing layered foreground renderer exposed by `owner._ensure_gizmo_overlay_renderer()`.
- Projection still uses `_main_renderer()` so camera math and world-to-display projection remain tied to the actual 3D scene.
- If the foreground layer is unavailable, the backend falls back to the previous main-renderer behavior.

This shares the proven Transform Gizmo visibility path instead of inventing a second overlay stack.

## Tests

Added/updated targeted coverage:

- `test_projected_drawing_uses_layered_foreground_renderer_when_available`
- existing reattach test still passes
- Plan Tracer projected drawing migration tests pass
- Texture Projection projected drawing migration tests pass

Validation commands:

```text
python -m pytest tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_uses_layered_foreground_renderer_when_available tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_reattaches_cached_actors_after_renderer_prop_clear tests/test_pass306_texture_projection_projected_drawing_migration.py tests/test_pass1024_plan_tracer_projected_drawing_migration.py -q
python scripts/quality_gate.py
```

## Notes

This intentionally avoids rolling back the Creator API migration. The fix completes the rendering side by moving Projected Drawing 2D to the same foreground-layer model already used by the visible Transform Gizmo.
