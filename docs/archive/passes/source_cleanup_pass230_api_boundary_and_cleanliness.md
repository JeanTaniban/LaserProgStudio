# Source cleanup pass 230 — API boundary and architecture inspection

## Goal

Make a low-risk cleanliness pass without changing user-facing behavior, document the package interactions, and continue the migration away from compatibility APIs.

## Changes

- `tool_core.projected_drawing` no longer imports `application.projected_drawing_2d` directly. The application renderer is now injected through `ProjectedDrawingManager.bind_renderer_backend(...)`.
- `application.projected_drawing_2d.bind_projected_drawing_2d_backend(ctx)` owns the Qt/VTK renderer binding for live contexts.
- Creator runtime and the native transform gizmo install that backend when they attach a `ToolContext` to a real window.
- `ToolContext(owner=...)` keeps a small compatibility bootstrap for direct diagnostic/test contexts; this is now the only warning in the API boundary audit.
- Plan Tracer editable-source serialization now imports dimensions from the owned `tool_api.plan2d.dimensions` domain instead of the legacy top-level `tool_api.dimensions` compatibility facade.
- Added `scripts/audit_api_boundaries.py` to make old/new API coupling visible and enforce the critical boundary in strict mode.
- Updated the static refactor verifier so it reflects the current `window.py` render bridges instead of failing on stale expectations.
- Updated `scripts/quality_gate.py` to run the API boundary audit and to clean generated runtime diagnostics before the product-tree guard.
- Removed generated runtime diagnostic files from the package tree. The `diagnostics/` folder now ships empty except `.gitkeep`.
- Added `docs/architecture_interactions_v74.drawio` as a draw.io XML map of the current package interactions.

## API migration status

- Built-in tool migration audit: 17 built-in tools, 17 Creator runtimes, 0 hook-only runtimes, 0 forbidden imports.
- API boundary audit: 524 Python files scanned, 1794 internal imports, 0 critical boundary issues, 1 warning.
  - Warning: `src/laserprog_studio/tool_core/context.py` imports `laserprog_studio.application.projected_drawing_2d` for direct `ToolContext(owner=...)` live-renderer compatibility.
- Remaining compatibility facades still exist where they are public/stable imports, but Plan Tracer no longer uses the legacy top-level dimension facade in `editable_source.py`.

## Package interaction summary

- `tooling->tool_api`: 177 imports
- `tool_api->tool_core`: 82 imports
- `controllers->application`: 42 imports
- `application->studio_log`: 39 imports
- `controllers->_window_deps`: 23 imports
- `tooling->geometry_ops`: 21 imports
- `application->app_context`: 20 imports
- `tooling->planar_tools`: 19 imports
- `ui->_window_deps`: 18 imports
- `application->tooling`: 15 imports
- `runtime_state->application`: 15 imports
- `application->geometry_ops`: 14 imports
- `application->project`: 14 imports
- `geometry_ops->domain`: 14 imports

## Current cleanup debt

- Large files above 800 lines: 23
- Legacy wording hotspots: 15 files
- Transition/compatibility wording hotspots: 15 files

Largest files to target next:

- 2409 lines — `src/laserprog_studio/tooling/plan_trace_2d/patterns.py`
- 2076 lines — `src/laserprog_studio/tooling/plan_trace_2d_tool.py`
- 1679 lines — `src/laserprog_studio/application/projected_drawing_2d.py`
- 1569 lines — `src/laserprog_studio/tooling/_texture_projection_projector.py`
- 1505 lines — `src/laserprog_studio/tool_core/projected_drawing.py`
- 1428 lines — `src/laserprog_studio/tooling/split_tool.py`
- 1393 lines — `src/laserprog_studio/tool_core/overlay/qt_layout.py`
- 1317 lines — `src/laserprog_studio/tooling/plan_trace_2d/snap.py`
- 1299 lines — `src/laserprog_studio/tooling/plan_trace_2d/motif_overlay.py`
- 1185 lines — `src/laserprog_studio/controllers/interaction.py`

## Recommended next passes

1. Split `tooling/plan_trace_2d/patterns.py` by pattern family and preview/runtime responsibilities.
2. Split `tooling/plan_trace_2d_tool.py` into lifecycle, event routing, apply/export, and panel-state orchestration modules.
3. Extract the pure batch compiler/projection helpers out of `application/projected_drawing_2d.py`, keeping only the Qt/VTK adapter there.
4. Remove the remaining `ToolContext(owner=...)` renderer-bootstrap warning once tests and diagnostics bind the renderer explicitly through an application adapter.
5. Remove remaining Plan2D compatibility imports after `tool_api.plan2d.sketch` exposes the raw migration types currently still needed by built-in Plan Tracer code.

## Validation

- `python scripts/quality_gate.py` → OK.
- Focused projected drawing renderer test file: 22 passed / 1 remaining failure in the Gizmo Catalog registry path (`TOOL_GIZMO_CATALOG` resolves to `None` in that isolated test).
- `scripts/product_tree_guard.py` is clean after generated diagnostic artifacts are removed.
