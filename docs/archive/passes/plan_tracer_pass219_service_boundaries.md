# Pass219 — Plan Tracer service-boundary repair

## Goal

Continue the Plan Tracer 2D repair after the first service split.  The previous
pass removed mixin inheritance, but still left a mixin-like implementation smell:
service methods could call arbitrary methods on `self` through the tool shell and
the shell contained a large delegate block.

## Changes

- Removed `_PlanTrace2DService.__getattr__` forwarding to the tool shell.
- Added an explicit `self.services` composition root for service collaboration.
- Replaced cross-service calls such as `self._render(...)` with explicit calls
  such as `self.services.rendering._render(...)`.
- Removed the large `PlanTrace2DCreatorTool` delegate dump.
- Kept only narrow compatibility shims used by older tests/scripts:
  - `_set_active_tool(...)`
  - `_state_invariant_issues(...)`
  - `_compile_and_sync_sketch(...)`
  - `apply_metric_value(...)`
  - `resolve_drag_positions(...)`
- Replaced wildcard constant imports in Plan Tracer services with explicit
  imports.
- Added public metric geometry exports in `tool_api.metrics` so Plan Tracer no
  longer imports `tool_core.metrics.geometry` directly.
- Added `tool_api.planar_drawing.sample_plan_arc_xy(...)` so the snap/display
  service no longer imports `tool_core.geometry` directly.

## Architectural rule

The Plan Tracer shell is now only the Creator lifecycle/event shell.  Feature
logic belongs to services.  Cross-service dependencies must be visible at the
call site through `self.services.<service>`; do not add new shell delegate methods
or service `__getattr__` forwarding.

## Validation

- `tests/test_pass219_plan_tracer_service_boundaries.py`
- Plan Tracer focused suite: `94 passed`
- Full test suite: see release notes for the final pass bundle.
