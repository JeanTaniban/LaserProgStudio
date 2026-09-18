# Plan Tracer selected-length diagnostic

- reason: tool_close
- generated_at: 2026-08-21 08:37:38
- jsonl: /mnt/data/v178check/LaserProg_v178_PlanTracerInteractionPerformance/diagnostics/plan_trace_selection_length_debug.jsonl
- event_count: 26
- likely_breakpoint: selection_event_not_received

## Current selection

- ids: []
- actors: []

## Inspector manager

- snapshot: {'available': True, 'panel_id': 'plan_trace_2d.panel', 'owner_tool': 'plan_trace', 'value': '—', 'revision': 23, 'layout_revision': 1, 'value_revision': 22, 'state_revision': 2}

## Sketch counts

- points: 2
- lines: 1
- arcs: 0
- circles: 0

## Stage counts

- `inspector.manager.write`: 1
- `measurement.begin`: 6
- `measurement.done`: 6
- `overlay.inspector_write.done`: 1
- `overlay.inspector_write.skipped_cache`: 5
- `overlay.selection_length.computed`: 6
- `session.start`: 1

## Last event by important stage

### `selection.event.begin`

```json
{}
```

### `selection.hit_test.done`

```json
{}
```

### `selection.mutation.done`

```json
{}
```

### `measurement.done`

```json
{
  "at_s": 2320.955934,
  "evaluations": [],
  "inspector": {
    "available": true,
    "layout_revision": 1,
    "owner_tool": "plan_trace",
    "panel_id": "plan_trace_2d.panel",
    "revision": 21,
    "state_revision": 2,
    "value": "—",
    "value_revision": 20
  },
  "result": null,
  "selection": {
    "actors": [],
    "available": true,
    "count": 0,
    "ids": []
  },
  "seq": 24,
  "stage": "measurement.done"
}
```

### `overlay.selection_length.computed`

```json
{
  "at_s": 2320.956075,
  "display_value": "—",
  "inspector": {
    "available": true,
    "layout_revision": 1,
    "owner_tool": "plan_trace",
    "panel_id": "plan_trace_2d.panel",
    "revision": 21,
    "state_revision": 2,
    "value": "—",
    "value_revision": 20
  },
  "selected_path": null,
  "selection": {
    "actors": [],
    "available": true,
    "count": 0,
    "ids": []
  },
  "selection_text": "0 selected",
  "selection_total": 0,
  "seq": 25,
  "stage": "overlay.selection_length.computed"
}
```

### `inspector.manager.write`

```json
{
  "allow_readonly": true,
  "at_s": 2320.934911,
  "changed": false,
  "field_id": "plan_trace_2d.selection_length",
  "notify": false,
  "panel_id": "plan_trace_2d.panel",
  "panel_owner_tool": "plan_trace",
  "previous": "—",
  "requested": "—",
  "revision_after": 3,
  "revision_before": 3,
  "seq": 5,
  "stage": "inspector.manager.write",
  "validated": "—",
  "value_revision_after": 2,
  "value_revision_before": 2
}
```

### `inspector.qt.refresh.begin`

```json
{}
```

### `inspector.qt.sync_field`

```json
{}
```

### `inspector.qt.refresh.end`

```json
{}
```

## Recent timeline

```jsonl
{"at_s": 2320.933115, "reason": "plan_trace_tool_open", "seq": 1, "sketch_counts": {"arcs": 0, "circles": 0, "lines": 0, "points": 0}, "stage": "session.start"}
{"actor_ids": [], "at_s": 2320.934438, "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 2, "state_revision": 2, "value": "—", "value_revision": 1}, "owner_tool": "plan_trace", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 2, "stage": "measurement.begin"}
{"at_s": 2320.934546, "evaluations": [], "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 2, "state_revision": 2, "value": "—", "value_revision": 1}, "result": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 3, "stage": "measurement.done"}
{"at_s": 2320.934639, "display_value": "—", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 2, "state_revision": 2, "value": "—", "value_revision": 1}, "selected_path": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "selection_text": "0 selected", "selection_total": 0, "seq": 4, "stage": "overlay.selection_length.computed"}
{"allow_readonly": true, "at_s": 2320.934911, "changed": false, "field_id": "plan_trace_2d.selection_length", "notify": false, "panel_id": "plan_trace_2d.panel", "panel_owner_tool": "plan_trace", "previous": "—", "requested": "—", "revision_after": 3, "revision_before": 3, "seq": 5, "stage": "inspector.manager.write", "validated": "—", "value_revision_after": 2, "value_revision_before": 2}
{"at_s": 2320.934984, "before": "—", "cache_after": "—", "field_id": "plan_trace_2d.selection_length", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 3, "state_revision": 2, "value": "—", "value_revision": 2}, "requested": "—", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 6, "stage": "overlay.inspector_write.done", "validated": "—"}
{"actor_ids": [], "at_s": 2320.938806, "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 6, "state_revision": 2, "value": "—", "value_revision": 5}, "owner_tool": "plan_trace", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 7, "stage": "measurement.begin"}
{"at_s": 2320.938919, "evaluations": [], "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 6, "state_revision": 2, "value": "—", "value_revision": 5}, "result": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 8, "stage": "measurement.done"}
{"at_s": 2320.939011, "display_value": "—", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 6, "state_revision": 2, "value": "—", "value_revision": 5}, "selected_path": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "selection_text": "0 selected", "selection_total": 0, "seq": 9, "stage": "overlay.selection_length.computed"}
{"at_s": 2320.939196, "cached": "—", "field_id": "plan_trace_2d.selection_length", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 9, "state_revision": 2, "value": "—", "value_revision": 8}, "requested": "—", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 10, "stage": "overlay.inspector_write.skipped_cache"}
{"actor_ids": [], "at_s": 2320.941172, "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 12, "state_revision": 2, "value": "—", "value_revision": 11}, "owner_tool": "plan_trace", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 11, "stage": "measurement.begin"}
{"at_s": 2320.941293, "evaluations": [], "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 12, "state_revision": 2, "value": "—", "value_revision": 11}, "result": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 12, "stage": "measurement.done"}
{"at_s": 2320.941391, "display_value": "—", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 12, "state_revision": 2, "value": "—", "value_revision": 11}, "selected_path": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "selection_text": "0 selected", "selection_total": 0, "seq": 13, "stage": "overlay.selection_length.computed"}
{"at_s": 2320.941564, "cached": "—", "field_id": "plan_trace_2d.selection_length", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 13, "state_revision": 2, "value": "—", "value_revision": 12}, "requested": "—", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 14, "stage": "overlay.inspector_write.skipped_cache"}
{"actor_ids": [], "at_s": 2320.945749, "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 17, "state_revision": 2, "value": "—", "value_revision": 16}, "owner_tool": "plan_trace", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 15, "stage": "measurement.begin"}
{"at_s": 2320.945867, "evaluations": [], "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 17, "state_revision": 2, "value": "—", "value_revision": 16}, "result": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 16, "stage": "measurement.done"}
{"at_s": 2320.946016, "display_value": "—", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 17, "state_revision": 2, "value": "—", "value_revision": 16}, "selected_path": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "selection_text": "0 selected", "selection_total": 0, "seq": 17, "stage": "overlay.selection_length.computed"}
{"at_s": 2320.946221, "cached": "—", "field_id": "plan_trace_2d.selection_length", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 18, "state_revision": 2, "value": "—", "value_revision": 17}, "requested": "—", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 18, "stage": "overlay.inspector_write.skipped_cache"}
{"actor_ids": [], "at_s": 2320.950987, "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 19, "state_revision": 2, "value": "—", "value_revision": 18}, "owner_tool": "plan_trace", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 19, "stage": "measurement.begin"}
{"at_s": 2320.951106, "evaluations": [], "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 19, "state_revision": 2, "value": "—", "value_revision": 18}, "result": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 20, "stage": "measurement.done"}
{"at_s": 2320.9512, "display_value": "—", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 19, "state_revision": 2, "value": "—", "value_revision": 18}, "selected_path": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "selection_text": "0 selected", "selection_total": 0, "seq": 21, "stage": "overlay.selection_length.computed"}
{"at_s": 2320.951428, "cached": "—", "field_id": "plan_trace_2d.selection_length", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 20, "state_revision": 2, "value": "—", "value_revision": 19}, "requested": "—", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 22, "stage": "overlay.inspector_write.skipped_cache"}
{"actor_ids": [], "at_s": 2320.95577, "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 21, "state_revision": 2, "value": "—", "value_revision": 20}, "owner_tool": "plan_trace", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 23, "stage": "measurement.begin"}
{"at_s": 2320.955934, "evaluations": [], "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 21, "state_revision": 2, "value": "—", "value_revision": 20}, "result": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 24, "stage": "measurement.done"}
{"at_s": 2320.956075, "display_value": "—", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 21, "state_revision": 2, "value": "—", "value_revision": 20}, "selected_path": null, "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "selection_text": "0 selected", "selection_total": 0, "seq": 25, "stage": "overlay.selection_length.computed"}
{"at_s": 2320.956279, "cached": "—", "field_id": "plan_trace_2d.selection_length", "inspector": {"available": true, "layout_revision": 1, "owner_tool": "plan_trace", "panel_id": "plan_trace_2d.panel", "revision": 21, "state_revision": 2, "value": "—", "value_revision": 20}, "requested": "—", "selection": {"actors": [], "available": true, "count": 0, "ids": []}, "seq": 26, "stage": "overlay.inspector_write.skipped_cache"}
```
