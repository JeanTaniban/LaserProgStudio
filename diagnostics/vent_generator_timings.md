# Vent Generator diagnostic report

- reason: manual
- exported_at: 2026-08-20T22:02:35
- mode: ADD
- plane_locked: True
- waypoints: 0
- segments: 0
- selected_index: None
- pointer_drag_active: False
- pointer_drag_mode: None

## Scene cache

- version: 1
- valid: True
- scope: snap
- points: 0
- segments: 0
- bounds: 0
- extra_targets: 0
- tool_points: 0
- tool_segments: 0
- ui_targets: 0

## Most expensive counters by total time

| counter | count | total ms | avg ms | p95 ms | max ms |
|---|---:|---:|---:|---:|---:|
| `vent.ui.sync_report` | 1 | 0.114 | 0.114 | 0.114 | 0.114 |
| `vent.ui.sync_view_feedback` | 1 | 0.086 | 0.086 | 0.086 | 0.086 |
| `vent.ui.refresh_state` | 1 | 0.060 | 0.060 | 0.060 | 0.060 |
| `scene_cache.rebuild.total` | 1 | 0.046 | 0.046 | 0.046 | 0.046 |
| `scene_cache.rebuild.collect_document_meshes` | 1 | 0.015 | 0.015 | 0.015 | 0.015 |
| `vent.feedback.snapshot.route_visuals` | 1 | 0.009 | 0.009 | 0.009 | 0.009 |
| `scene_cache.mesh.collect_objects` | 1 | 0.008 | 0.008 | 0.008 | 0.008 |
| `scene_cache.rebuild.collect_sketch` | 1 | 0.001 | 0.001 | 0.001 | 0.001 |
| `scene_cache.rebuild.collect_selection` | 1 | 0.001 | 0.001 | 0.001 | 0.001 |
| `scene_cache.rebuild.collect_scene` | 1 | 0.000 | 0.000 | 0.000 | 0.000 |

## Worst jitter by p95

| counter | count | p95 ms | max ms | last ms |
|---|---:|---:|---:|---:|
| `vent.ui.sync_report` | 1 | 0.114 | 0.114 | 0.114 |
| `vent.ui.sync_view_feedback` | 1 | 0.086 | 0.086 | 0.086 |
| `vent.ui.refresh_state` | 1 | 0.060 | 0.060 | 0.060 |
| `scene_cache.rebuild.total` | 1 | 0.046 | 0.046 | 0.046 |
| `scene_cache.rebuild.collect_document_meshes` | 1 | 0.015 | 0.015 | 0.015 |
| `vent.feedback.snapshot.route_visuals` | 1 | 0.009 | 0.009 | 0.009 |
| `scene_cache.mesh.collect_objects` | 1 | 0.008 | 0.008 | 0.008 |
| `scene_cache.rebuild.collect_sketch` | 1 | 0.001 | 0.001 | 0.001 |
| `scene_cache.rebuild.collect_selection` | 1 | 0.001 | 0.001 | 0.001 |
| `scene_cache.rebuild.collect_scene` | 1 | 0.000 | 0.000 | 0.000 |

## Slow events

- no slow event above profiler threshold

## Values and gauges

- `render.full`: 1
- `scene_cache.bounds`: 0
- `scene_cache.extra_targets`: 0
- `scene_cache.mesh.collect_objects.avg_ms`: 0.007992000064405147
- `scene_cache.mesh.collect_objects.count`: 1
- `scene_cache.mesh.collect_objects.last_ms`: 0.007992000064405147
- `scene_cache.mesh.collect_objects.max_ms`: 0.007992000064405147
- `scene_cache.mesh.collect_objects.p95_ms`: 0.007992000064405147
- `scene_cache.mesh.objects`: 0
- `scene_cache.points`: 0
- `scene_cache.rebuild.calls`: 1
- `scene_cache.rebuild.collect_document_meshes.avg_ms`: 0.015331999748013914
- `scene_cache.rebuild.collect_document_meshes.count`: 1
- `scene_cache.rebuild.collect_document_meshes.last_ms`: 0.015331999748013914
- `scene_cache.rebuild.collect_document_meshes.max_ms`: 0.015331999748013914
- `scene_cache.rebuild.collect_document_meshes.p95_ms`: 0.015331999748013914
- `scene_cache.rebuild.collect_scene.avg_ms`: 0.0002800002221192699
- `scene_cache.rebuild.collect_scene.count`: 1
- `scene_cache.rebuild.collect_scene.last_ms`: 0.0002800002221192699
- `scene_cache.rebuild.collect_scene.max_ms`: 0.0002800002221192699
- `scene_cache.rebuild.collect_scene.p95_ms`: 0.0002800002221192699
- `scene_cache.rebuild.collect_selection.avg_ms`: 0.0008609999895270448
- `scene_cache.rebuild.collect_selection.count`: 1
- `scene_cache.rebuild.collect_selection.last_ms`: 0.0008609999895270448
- `scene_cache.rebuild.collect_selection.max_ms`: 0.0008609999895270448
- `scene_cache.rebuild.collect_selection.p95_ms`: 0.0008609999895270448
- `scene_cache.rebuild.collect_sketch.avg_ms`: 0.0013519997992261779
- `scene_cache.rebuild.collect_sketch.count`: 1
- `scene_cache.rebuild.collect_sketch.last_ms`: 0.0013519997992261779
- `scene_cache.rebuild.collect_sketch.max_ms`: 0.0013519997992261779
- `scene_cache.rebuild.collect_sketch.p95_ms`: 0.0013519997992261779
- `scene_cache.rebuild.total.avg_ms`: 0.045897999825683655
- `scene_cache.rebuild.total.count`: 1
- `scene_cache.rebuild.total.last_ms`: 0.045897999825683655
- `scene_cache.rebuild.total.max_ms`: 0.045897999825683655
- `scene_cache.rebuild.total.p95_ms`: 0.045897999825683655
- `scene_cache.segments`: 0
- `scene_cache.version`: 1
- `vent.feedback.snapshot.route_visuals.avg_ms`: 0.009304000286647351
- `vent.feedback.snapshot.route_visuals.count`: 1
- `vent.feedback.snapshot.route_visuals.last_ms`: 0.009304000286647351
- `vent.feedback.snapshot.route_visuals.max_ms`: 0.009304000286647351
- `vent.feedback.snapshot.route_visuals.p95_ms`: 0.009304000286647351
- `vent.ui.refresh_state.avg_ms`: 0.0596290001340094
- `vent.ui.refresh_state.count`: 1
- `vent.ui.refresh_state.last_ms`: 0.0596290001340094
- `vent.ui.refresh_state.max_ms`: 0.0596290001340094
- `vent.ui.refresh_state.p95_ms`: 0.0596290001340094
- `vent.ui.sync_report.avg_ms`: 0.11390000008759671
- `vent.ui.sync_report.count`: 1
- `vent.ui.sync_report.last_ms`: 0.11390000008759671
- `vent.ui.sync_report.max_ms`: 0.11390000008759671
- `vent.ui.sync_report.p95_ms`: 0.11390000008759671
- `vent.ui.sync_view_feedback.avg_ms`: 0.08613800036982866
- `vent.ui.sync_view_feedback.count`: 1
- `vent.ui.sync_view_feedback.last_ms`: 0.08613800036982866
- `vent.ui.sync_view_feedback.max_ms`: 0.08613800036982866
- `vent.ui.sync_view_feedback.p95_ms`: 0.08613800036982866
