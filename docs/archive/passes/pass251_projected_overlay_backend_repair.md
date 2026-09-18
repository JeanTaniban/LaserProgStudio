# Pass 251 — Projected Drawing overlay backend repair

## User issue

Plan Tracer 2D no longer showed its projected viewport overlay after the API boundary cleanup that moved the Qt/VTK renderer out of `tool_core.projected_drawing`.

## Root cause

Before the API boundary cleanup, `ProjectedDrawingManager._render_tool_now()` imported the application renderer directly every time it had to sync. After the cleanup, the renderer backend became injectable through `bind_projected_drawing_2d_backend(ctx)`.

That was architecturally cleaner, but incomplete for one runtime path: some `ToolContext` instances are created headlessly first, then receive the Qt owner later. A plain `ctx.owner = owner` does not rerun `ToolContext.__post_init__()`, so the Projected Drawing 2D renderer could remain unbound. In that state, Plan Tracer still populated `ctx.projected_drawing`, but no live VTK/Qt overlay was materialized.

## Fix

- Added `ToolContext.attach_owner(owner)`.
- Added `ToolContext.ensure_live_projected_drawing_backend()`.
- Updated Creator runtime and transform gizmo runtime to use `attach_owner()` instead of raw owner assignment plus duplicated backend-binding code.
- Added a lazy safety repair in `ProjectedDrawingManager._render_tool_now()`:
  - if a live owner exists but no renderer backend is bound,
  - the manager asks the context to install its live backend,
  - then retries the sync.
- The Tool Core boundary remains intact: `tool_core.projected_drawing` still does not import the application renderer directly.

## Regression tests

Added tests covering:

- a `ToolContext` created without owner, then repaired through `attach_owner(owner)`;
- compatibility with older code that still does `ctx.owner = owner` directly.

## Validation

- `python -m pytest tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_renderer_reprojects_on_each_vtk_frame_without_recreating_actors tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_backend_binds_when_owner_is_attached_after_context_creation tests/test_pass1021_projected_drawing_2d_api.py::test_projected_drawing_lazy_repairs_plain_owner_assignment tests/test_pass1024_plan_tracer_projected_drawing_migration.py -q`
  - `8 passed`
- `python scripts/quality_gate.py`
  - `Quality gate OK`

## Remaining note

The API-boundary audit still reports one warning for `tool_core/context.py` because `ToolContext` intentionally owns the compatibility bootstrap for `ToolContext(owner=...)`. This is acceptable and much safer than reintroducing application imports into `tool_core.projected_drawing`.
