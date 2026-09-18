# Pass 253 — Projected/Creator overlay deep diagnostics

Context: v83/v84 did not restore the missing overlay in Plan Tracer 2D or Texture Projection. This pass intentionally avoids another blind fix and instruments the entire shared overlay pipeline.

## Added diagnostics

All events are written only when debug diagnostics are enabled:

- `diagnostics/projected_overlay_debug.jsonl`
- enriched `diagnostics/plan_trace_2d_timings.md/json`

The JSONL now records:

1. ToolContext owner/backend binding
2. ProjectedDrawingManager mutations and render notifications
3. renderer backend entry/exit
4. state token decisions: full sync / camera-only / noop / reattach
5. manager snapshot primitive counts and samples
6. Creator preview/gizmo counts
7. PyVista actor-map counts and matching `creator_ui_<tool>_` actor names
8. VTK renderer prop counts when available
9. projected drawing actor live-membership audit
10. handle projection samples
11. batch projection samples and backend selection
12. ToolCoreDiagScenePainter persistent actor creation/update/cache-detach events
13. Creator UI fallback path decisions
14. clear/remove paths that can silently remove overlay actors

## Added pipeline summary

The Plan Tracer timing report now includes an `Overlay pipeline state` section:

```text
generated -> manager -> renderer -> live VTK actors -> visible/projection
```

It also estimates a `likely_breakpoint`:

- `generation_or_bridge`
- `vtk_attachment_or_visibility`
- `projection_or_depth_or_visibility`
- `unknown_viewport_composition`

## Validation

- `python -m pytest tests/test_pass1024_plan_tracer_projected_drawing_migration.py tests/test_pass1058_modifier_projected_drawing_2d.py tests/test_pass252_overlay_state_machine_repair.py tests/test_pass306_texture_projection_projected_drawing_migration.py -q` → 15 passed
- `python scripts/quality_gate.py` → OK

One broader catalog test from `test_pass1021_projected_drawing_2d_api.py` still fails because `TOOL_GIZMO_CATALOG` is not registered in this package snapshot; that was not introduced by this diagnostics pass and is unrelated to Plan Tracer / Texture Projection overlay instrumentation.
