# Architecture / tool polish pass 27 — Traceur de plan hardening

This pass applies the lessons learned while polishing the audio vent tool to the
`plan_trace` tool.

## User-facing changes

- ADD and MOD edits are now constrained so the trace does not become self-crossing while the pointer is dragged.
- If the requested point would create an invalid segment/polygon, the effective point is clamped to the closest safe location and the requested raw point is shown in red by the preview service.
- Double-click closure now validates the final closing edge before marking the polygon as closed. Invalid closure reports a clear message instead of silently creating an unsafe draft.
- The trace preview is clearer: larger point handles, dedicated start/end handles, a subtle closing hint, selected-point highlight, and a translucent fill after closure.

## Architecture changes

- `planar_tools/polygon_constraints.py` contains UI-independent validation and clamp logic for polygon edits.
- `PlanarPolygonDraft` exposes `close_validation_result()`, `open_trace_validation_result()` and `clamp_point_candidate()` so controllers and tests use the same contract.
- `application/planar_pick_service.py` moves low-level VTK first-hit picking out of `PlanarToolController`.
- `PlanarPreviewService` owns the improved polygon gizmo/preview rendering, keeping drawing code out of the controller.

The result keeps all source files below the large-file audit threshold and keeps the planar tools on the controller/service architecture rather than adding new mixins.
