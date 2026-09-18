# Plan Tracer pass 218 — service structure cleanup

Goal: continue the Plan Tracer 2D architecture cleanup after the initial file
split by removing the mixin inheritance chain and making feature boundaries
explicit.

## Changes

- Replaced `PlanTrace2DCreatorTool(...many mixins..., CreatorTool)` with a
  single `PlanTrace2DCreatorTool(CreatorTool)` shell.
- Added `tooling/plan_trace_2d/services.py` as the composition root.
- Converted the former focused mixin classes into service classes:
  overlay, selection, snap, sketch sync, drawing, metrics, dimensions, history,
  mode state and rendering.
- Kept the shell responsible for lifecycle hooks, event routing and public
  runtime callbacks.
- Cleaned the service module imports so each service only imports the API/types
  it actually needs.
- Updated the Plan Tracer documentation to define the service split as the
  expected structure for future work.

## Why this matters

The previous split reduced the size of `plan_trace_2d_tool.py`, but it still
used a long inherited mixin chain.  That made method ownership unclear and made
future edits likely to reintroduce hidden dependencies through `self`.

The new structure is still intentionally conservative: behavior is not rewritten
and the existing tests remain the safety net.  This pass is a structural cleanup,
not a feature repair pass.

## Validation

- Targeted Plan Tracer / sketch / metric tests: `121 passed, 1 skipped`.
- Full test suite: `819 passed, 3 skipped, 81 warnings`.
- Architecture audit: Plan Tracer files are below the large-file threshold and
  no `PlanTrace2D*Mixin` classes remain.
