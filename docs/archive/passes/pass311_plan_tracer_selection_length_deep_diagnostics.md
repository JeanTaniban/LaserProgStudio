# Pass 311 — Plan Tracer selected-length deep diagnostics

## Goal

Stop inferring the selected-length failure from headless tests. Observe the real runtime boundary between viewport selection, exact path measurement, headless inspector state and the live Qt label.

## Added probes

- `SelectionManager.hit_test`: complete candidate table and winner.
- `PlanTrace2DSelectionService`: incoming Shift-click, selection mutation and report synchronisation.
- `measure_selected_path`: per-actor acceptance/rejection and exact result.
- `PlanTrace2DOverlayService`: computed display value, report cache decisions and inspector write result.
- `InspectorManager`: requested/validated value and revision changes.
- `LiveDeclarativeToolPanelWidget`: whether a refresh was called and why it rebuilt, synced or did nothing.
- `InspectorPanelQtAdapter`: actual Qt field creation and `QLabel` text before/after sync.

## Diagnostic outputs

- `diagnostics/plan_trace_selection_length_debug.jsonl`
- `diagnostics/plan_trace_selection_length_debug.md`

All probes are gated by the global debug mode. No selection behavior or measurement policy is intentionally changed in this pass.
