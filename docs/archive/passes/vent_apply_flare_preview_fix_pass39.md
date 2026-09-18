# EVT Pass39 — Apply state and embouchure preview fix

This pass fixes two regressions found after the rectangular EVT refactor.

## Apply / Valider button

The EVT editor now uses a lightweight preview and intentionally does not stage a mesh while the user is drawing. The global Apply button was still mostly synchronized by preview-mesh creation, so it could remain disabled even when the rectangular vent draft itself was valid.

The planar controller now explicitly refreshes the preview button state after EVT draft changes: waypoint add/delete/move, mode changes, reset, and parameter changes. `Apply` still creates the final mesh only at commit time.

## Embouchure / flare

The rectangular EVT workflow no longer needs a separate double-click finalization step. The current last waypoint is treated as the outlet immediately, so `Sortie` and `Les deux` embouchure modes are active as soon as a valid path has at least two points.

The visual preview and smart snap also use the same variable-width footprint as Apply: inlet/outlet flares widen the drawn outer and inner contours instead of only affecting the final mesh.

## Files touched

- `src/laserprog_studio/application/planar_tool_controller.py`
- `src/laserprog_studio/application/planar_preview_service.py`
- `src/laserprog_studio/application/planar_report_service.py`
- `src/laserprog_studio/planar_tools/vent_flare.py`
- `src/laserprog_studio/planar_tools/vent_model.py`
- `src/laserprog_studio/planar_tools/vent_preview_snap.py`
- `src/laserprog_studio/ui/vent_tool_panel.py`
- flare regression tests updated for the no-finalization workflow

Validation: `261 passed, 3 skipped`.
