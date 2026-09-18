# Pass 282 — Plan Tracer overlay review

## Goal
Polish the Plan Tracer 2D floating toolbar so it reads as one professional CAD overlay instead of a dense strip of isolated buttons.

## Changes
- The Plan Tracer toolbox is now truly top-centered with no inherited cursor offset.
- Toolbar separators are inserted only at semantic section boundaries: drawing modes stay together, actions are separated.
- The toolbar glass, badge rim and selected tool glow were softened so the active mode remains clear without overpowering the viewport.
- Added regression coverage for the top-center placement and section separator behavior.

## Validation
- `PYTHONPATH=src:tests pytest -q tests/test_pass206_plan_tracer_professional_overlay.py tests/test_pass262_plan_tracer_qt_toolbar_materialization.py tests/test_pass264_plan_tracer_compact_ui_selection_feedback.py tests/test_pass278_plan_tracer_global_shortcuts_toolbar_alignment.py tests/test_pass279_plan_tracer_overlay_exit_camera.py tests/test_pass282_plan_tracer_overlay_review.py`
