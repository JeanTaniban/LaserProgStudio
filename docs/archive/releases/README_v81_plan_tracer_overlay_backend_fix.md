# LaserProg v81 — Plan Tracer projected overlay backend repair

This build fixes a regression introduced during the Projected Drawing API boundary cleanup: Plan Tracer 2D could populate its projected drawing state, but the live Qt/VTK overlay renderer was not always rebound when a `ToolContext` received its application owner after construction.

## Fixed

- Restored Plan Tracer 2D projected viewport overlay materialization.
- Added `ToolContext.attach_owner(owner)` for late owner attachment.
- Added `ToolContext.ensure_live_projected_drawing_backend()`.
- Updated Creator runtime and transform gizmo runtime to use the new owner-attachment helper.
- Added a lazy repair path in `ProjectedDrawingManager._render_tool_now()` for older code that still assigns `ctx.owner = owner` directly.
- Kept the architecture direction: `tool_core.projected_drawing` still does not import `application.projected_drawing_2d` directly.

## Validation

- Projected Drawing live backend regression tests: OK.
- Plan Tracer projected drawing migration tests: OK.
- `python scripts/quality_gate.py`: OK.
