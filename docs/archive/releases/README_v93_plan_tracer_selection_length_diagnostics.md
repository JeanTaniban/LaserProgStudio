# LaserProg v93 — Plan Tracer selected-length deep diagnostics

This build intentionally does not claim another selection fix. It instruments the complete Windows runtime path used by `Shift + click` edge selection so the next diagnostic capture identifies the first failing stage.

## New files

- `diagnostics/plan_trace_selection_length_debug.jsonl`
- `diagnostics/plan_trace_selection_length_debug.md`

They are generated only when **Preferences → Diagnostics debug mode** is enabled.

## Instrumented pipeline

1. Plan Tracer receives the Shift-click event.
2. Every hit-test candidate is recorded with screen distance, hit radius, role, semantic priority and sketch entity id.
3. The winning actor is recorded.
4. Selection contents before and after mutation are recorded.
5. Every selected actor is evaluated by the length calculator, including explicit rejection reasons.
6. The computed value sent by the Plan Tracer overlay is recorded.
7. The value stored by `InspectorManager` and its revision counters are recorded.
8. The refresh of the live Qt inspector is recorded.
9. The actual text of the `QLabel` displaying `Selected length` is recorded before and after synchronisation.

The Markdown summary includes a `likely_breakpoint` classification and a recent timeline.

## Capture procedure

1. Enable **Diagnostics debug mode** in Preferences.
2. Restart LaserProg.
3. Open Plan Tracer 2D and reproduce the issue with two or more polyline segments.
4. Close Plan Tracer normally so the final summary is exported.
5. Send the two new diagnostic files, `plan_trace_input_debug.jsonl`, and the normal application log.
