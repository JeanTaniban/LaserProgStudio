# Window refactor gizmo visibility fix

This fix keeps the extracted `window.py` / `controllers` / `ui` structure and targets a regression where selection worked again but transform gizmos were still invisible.

## Root cause addressed

After the refactor, the selection path correctly called `update_gizmo()`, but the visual gizmo actors still depended entirely on the foreground VTK renderer layer. On some QtInteractor / VTK builds, extra renderer layers can be lost or not painted reliably after `plotter.clear()`, widget reparenting, or render-window layer changes. In that failure mode the actors exist in Python, but nothing visible appears in the viewport.

## Fix

- `GizmoOverlayMixin` still creates the layer-1 foreground renderer.
- The render-window layer count is now forced before attaching the overlay renderer.
- Gizmo actors are mirrored into the main renderer as a fallback, so the arrows/rings remain visible even if the overlay layer is not painted.
- Gizmo clearing now removes actors from both the overlay renderer and the main renderer.
- Gizmo picking now tries both the overlay renderer and the main renderer.
- `window.py` exposes explicit `set_transform_mode()` and `update_gizmo()` bridges while leaving the implementations in the extracted modules.
- Keyboard shortcuts `N`, `T`, `R`, `S` now select None / Translate / Rotate / Scale directly.

## Files changed

- `src/laserprog_studio/window.py`
- `src/laserprog_studio/controllers/gizmo_overlay.py`
- `src/laserprog_studio/controllers/interaction.py`
- `scripts/verify_refactor_structure.py`
