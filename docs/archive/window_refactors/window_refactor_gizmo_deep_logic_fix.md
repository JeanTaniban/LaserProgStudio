# Window refactor gizmo deep logic fix

This pass keeps the refactored `window.py` / `controllers` / `ui` structure and fixes the transform-gizmo visibility regression without returning to the monolithic file.

## Problem

Selection was working again, but the transform gizmos remained invisible in `T`, `R`, and `S` modes.

The failure path was not the Qt light overlay. The light overlay is a QWidget overlay; the transform gizmo is VTK geometry rendered through PyVista/VTK. They share state, but they do not share the same renderer.

## Logic fix

`update_gizmo()` now uses the selected mesh list as the source of truth instead of treating `active_index` as a hard visibility gate.

The explicit visibility rule is:

- `N` hides the gizmo;
- `T`, `R`, and `S` can show it;
- at least one selected mesh is required;
- modal tools/previews temporarily hide transform gizmos.

The function now logs concise state transitions:

- `[GIZMO] hidden ...`
- `[GIZMO] visible ...`
- `[GIZMO] no_actors_created ...`

This makes future regressions diagnosable directly from the UI log.

## Renderer fix

The previous hotfix mirrored the exact same `vtkActor` into both the overlay renderer and the main renderer, and also disabled actor bounds with `SetUseBounds(False)`.

That was fragile:

- the overlay renderer contains only gizmo actors, so disabling all actor bounds can lead to bad clipping-range computation;
- sharing the same actor object between the VTK overlay renderer and PyVista's main renderer makes actor ownership/removal ambiguous during scene rebuilds.

The corrected implementation now:

- keeps a real VTK layer-1 overlay renderer;
- keeps actor bounds enabled;
- creates separate actor instances for overlay and main-renderer fallback;
- adds the fallback actor through `plotter.add_actor()` when available;
- tracks overlay/fallback actors separately using `__overlay` and `__main` keys;
- keeps picking working by registering both actor instances to the same logical axis.

## Files changed

- `src/laserprog_studio/controllers/gizmo_overlay.py`
- `src/laserprog_studio/controllers/gizmo_view.py`
- `scripts/verify_refactor_structure.py`
