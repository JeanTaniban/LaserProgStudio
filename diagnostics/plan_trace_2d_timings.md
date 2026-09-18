# Plan Tracer 2D diagnostic report

- reason: tool_close
- exported_at: 2026-08-21T08:37:38
- active_tool: line
- phase: draw
- plane_locked: True
- input_diagnostics: /mnt/data/v178check/LaserProg_v178_PlanTracerInteractionPerformance/diagnostics/plan_trace_input_debug.jsonl
- projected_overlay_diagnostics: /mnt/data/v178check/LaserProg_v178_PlanTracerInteractionPerformance/diagnostics/projected_overlay_debug.jsonl
- selection_length_diagnostics: /mnt/data/v178check/LaserProg_v178_PlanTracerInteractionPerformance/diagnostics/plan_trace_selection_length_debug.jsonl
- selection_length_summary: /mnt/data/v178check/LaserProg_v178_PlanTracerInteractionPerformance/diagnostics/plan_trace_selection_length_debug.md

## Sketch

- points: 2
- lines: 1
- arcs: 0
- beziers: 0
- circles: 0
- faces: 0
- dimensions: 0
- suppressed_faces: 0

## Scene cache

- version: 2
- valid: True
- scope: snap
- points: 0
- segments: 0
- bounds: 0
- extra_targets: 0
- tool_points: 0
- tool_segments: 0
- ui_targets: 0

## Projected Drawing 2D renderer

- sync_count: 12
- compile_count: 0
- projection_count: 0
- cache_hit_count: 0
- incremental_update_count: 0
- vector_projection_count: 0
- scalar_projection_count: 0
- scalar_fallback_count: 0
- last_projection_backend: none
- last_projection_invalid_points: 0
- last_projection_outside_points: 0
- last_sync_ms: 0.07339900002989452
- owner_tool: plan_trace
- revision: -1
- visible: True
- batches: 0
- actors: 0
- handles: 0
- texts: 0
- batches_by_kind: {}
- world_points: 0
- cells: 0
- renderer_reattach_count: 0
- last_renderer_reattached_actors: 0
- live_actor_audit: {'renderer_id': None, 'stored_renderer_id': None, 'batch_visuals': 0, 'handle_visuals': 0, 'text_visuals': 0, 'present': 0, 'missing': 0, 'unknown': 0, 'visible': 0, 'hidden': 0, 'samples': []}

## Overlay pipeline state

- tool_sketch_generated_items: 3
- projected_renderer_actor_objects: 0
- projected_batches: 0
- projected_handles: 0
- live_vtk_present_actors: 0
- live_vtk_missing_actors: 0
- live_vtk_visible_actors: 0
- likely_breakpoint: generation_or_bridge

## Most expensive counters by total time

| counter | count | total ms | avg ms | p95 ms | max ms |
|---|---:|---:|---:|---:|---:|
| `plan_trace.event.total` | 3 | 14.849 | 4.950 | 7.112 | 7.112 |
| `plan_trace.event.mouse_press.total` | 3 | 14.830 | 4.943 | 7.106 | 7.106 |
| `plan_trace.event.mouse_press.draw_press` | 2 | 10.637 | 5.318 | 6.985 | 6.985 |
| `plan_trace.draw_press.total` | 2 | 10.616 | 5.308 | 6.971 | 6.971 |
| `plan_trace.draw_press.line` | 2 | 5.492 | 2.746 | 3.862 | 3.862 |
| `plan_trace.surface.pick_press` | 1 | 3.861 | 3.861 | 3.861 | 3.861 |
| `plan_trace.render` | 4 | 3.777 | 0.944 | 1.062 | 1.062 |
| `plan_trace.lifecycle.open` | 1 | 3.547 | 3.547 | 3.547 | 3.547 |
| `plan_trace.cursor.update` | 2 | 2.944 | 1.472 | 1.706 | 1.706 |
| `plan_trace.cursor.actor_sync` | 2 | 0.940 | 0.470 | 0.496 | 0.496 |
| `plan2d.actor_visuals.full_interaction` | 5 | 0.824 | 0.165 | 0.440 | 0.440 |
| `plan_trace.cursor.register_cursor` | 2 | 0.809 | 0.405 | 0.428 | 0.428 |
| `plan_trace.sketch.actor_visual_sync` | 1 | 0.475 | 0.475 | 0.475 | 0.475 |
| `plan_trace.cursor.pending_preview` | 2 | 0.454 | 0.227 | 0.435 | 0.435 |
| `plan_trace.cursor.smart_snap` | 2 | 0.442 | 0.221 | 0.278 | 0.278 |
| `plan2d.smart_snap.total` | 2 | 0.404 | 0.202 | 0.260 | 0.260 |
| `plan_trace.cursor.targets` | 2 | 0.388 | 0.194 | 0.195 | 0.195 |
| `plan2d.smart_snap.manager` | 2 | 0.226 | 0.113 | 0.131 | 0.131 |
| `plan_trace.sketch.compile_kernel` | 1 | 0.203 | 0.203 | 0.203 | 0.203 |
| `plan2d.smart_snap.alignment` | 1 | 0.144 | 0.144 | 0.144 | 0.144 |
| `plan_trace.snap_targets.build_live_targets` | 2 | 0.142 | 0.071 | 0.074 | 0.074 |
| `plan_trace.snap.near_query.total` | 2 | 0.134 | 0.067 | 0.067 | 0.067 |
| `snap.manager.targets_to_results` | 2 | 0.087 | 0.043 | 0.050 | 0.050 |
| `snap.targets_to_results.total` | 2 | 0.075 | 0.038 | 0.044 | 0.044 |
| `plan_trace.lifecycle.open.scene_cache_rebuild` | 1 | 0.073 | 0.073 | 0.073 | 0.073 |
| `scene_cache.rebuild.total` | 1 | 0.066 | 0.066 | 0.066 | 0.066 |
| `plan_trace.cursor.sync_actor_visuals` | 2 | 0.062 | 0.031 | 0.034 | 0.034 |
| `scene_cache.snap.near_query.total` | 2 | 0.051 | 0.026 | 0.038 | 0.038 |
| `plan2d.smart_snap.alignment.extra_cache` | 1 | 0.038 | 0.038 | 0.038 | 0.038 |
| `plan2d.smart_snap.alignment.scene_cache` | 1 | 0.038 | 0.038 | 0.038 | 0.038 |

## Worst jitter by p95

| counter | count | p95 ms | max ms | last ms |
|---|---:|---:|---:|---:|
| `plan_trace.event.total` | 3 | 7.112 | 7.112 | 7.112 |
| `plan_trace.event.mouse_press.total` | 3 | 7.106 | 7.106 | 7.106 |
| `plan_trace.event.mouse_press.draw_press` | 2 | 6.985 | 6.985 | 6.985 |
| `plan_trace.draw_press.total` | 2 | 6.971 | 6.971 | 6.971 |
| `plan_trace.draw_press.line` | 2 | 3.862 | 3.862 | 3.862 |
| `plan_trace.surface.pick_press` | 1 | 3.861 | 3.861 | 3.861 |
| `plan_trace.lifecycle.open` | 1 | 3.547 | 3.547 | 3.547 |
| `plan_trace.cursor.update` | 2 | 1.706 | 1.706 | 1.706 |
| `plan_trace.render` | 4 | 1.062 | 1.062 | 0.943 |
| `plan_trace.cursor.actor_sync` | 2 | 0.496 | 0.496 | 0.443 |
| `plan_trace.sketch.actor_visual_sync` | 1 | 0.475 | 0.475 | 0.475 |
| `plan2d.actor_visuals.full_interaction` | 5 | 0.440 | 0.440 | 0.440 |
| `plan_trace.cursor.pending_preview` | 2 | 0.435 | 0.435 | 0.435 |
| `plan_trace.cursor.register_cursor` | 2 | 0.428 | 0.428 | 0.381 |
| `plan_trace.cursor.smart_snap` | 2 | 0.278 | 0.278 | 0.278 |
| `plan2d.smart_snap.total` | 2 | 0.260 | 0.260 | 0.260 |
| `plan_trace.sketch.compile_kernel` | 1 | 0.203 | 0.203 | 0.203 |
| `plan_trace.cursor.targets` | 2 | 0.195 | 0.195 | 0.195 |
| `plan2d.smart_snap.alignment` | 1 | 0.144 | 0.144 | 0.144 |
| `plan2d.smart_snap.manager` | 2 | 0.131 | 0.131 | 0.095 |

## Slow events

- no slow event above profiler threshold

## Values and gauges

- `plan2d.actor_visuals.changed_last`: 2
- `plan2d.actor_visuals.dirty_bridge`: 6
- `plan2d.actor_visuals.dirty_bridge_handles_last`: 2
- `plan2d.actor_visuals.dirty_bridge_previews_last`: 0
- `plan2d.actor_visuals.full_interaction.avg_ms`: 0.16483640001752065
- `plan2d.actor_visuals.full_interaction.calls`: 5
- `plan2d.actor_visuals.full_interaction.count`: 5
- `plan2d.actor_visuals.full_interaction.last_ms`: 0.4397620000418101
- `plan2d.actor_visuals.full_interaction.max_ms`: 0.4397620000418101
- `plan2d.actor_visuals.full_interaction.p95_ms`: 0.4397620000418101
- `plan2d.actor_visuals.position_only_last`: 0
- `plan2d.guide_cache.extra.build.avg_ms`: 0.021111000023665838
- `plan2d.guide_cache.extra.build.count`: 1
- `plan2d.guide_cache.extra.build.last_ms`: 0.021111000023665838
- `plan2d.guide_cache.extra.build.max_ms`: 0.021111000023665838
- `plan2d.guide_cache.extra.build.p95_ms`: 0.021111000023665838
- `plan2d.guide_cache.extra.misses`: 1
- `plan2d.guide_cache.extra.points`: 2
- `plan2d.guide_cache.extra.targets`: 2
- `plan2d.guide_cache.scene.build.avg_ms`: 0.007270000423886813
- `plan2d.guide_cache.scene.build.count`: 1
- `plan2d.guide_cache.scene.build.last_ms`: 0.007270000423886813
- `plan2d.guide_cache.scene.build.max_ms`: 0.007270000423886813
- `plan2d.guide_cache.scene.build.p95_ms`: 0.007270000423886813
- `plan2d.guide_cache.scene.collect_targets.avg_ms`: 0.005788000180473318
- `plan2d.guide_cache.scene.collect_targets.count`: 1
- `plan2d.guide_cache.scene.collect_targets.last_ms`: 0.005788000180473318
- `plan2d.guide_cache.scene.collect_targets.max_ms`: 0.005788000180473318
- `plan2d.guide_cache.scene.collect_targets.p95_ms`: 0.005788000180473318
- `plan2d.guide_cache.scene.misses`: 1
- `plan2d.guide_cache.scene.object_scope.filtered`: 0
- `plan2d.guide_cache.scene.points`: 0
- `plan2d.guide_cache.scene.targets`: 0
- `plan2d.smart_snap.alignment.avg_ms`: 0.1437830001123075
- `plan2d.smart_snap.alignment.count`: 1
- `plan2d.smart_snap.alignment.extra_cache.avg_ms`: 0.038466999740194296
- `plan2d.smart_snap.alignment.extra_cache.count`: 1
- `plan2d.smart_snap.alignment.extra_cache.last_ms`: 0.038466999740194296
- `plan2d.smart_snap.alignment.extra_cache.max_ms`: 0.038466999740194296
- `plan2d.smart_snap.alignment.extra_cache.p95_ms`: 0.038466999740194296
- `plan2d.smart_snap.alignment.intersection_candidate.avg_ms`: 0.00683999996908824
- `plan2d.smart_snap.alignment.intersection_candidate.count`: 1
- `plan2d.smart_snap.alignment.intersection_candidate.last_ms`: 0.00683999996908824
- `plan2d.smart_snap.alignment.intersection_candidate.max_ms`: 0.00683999996908824
- `plan2d.smart_snap.alignment.intersection_candidate.p95_ms`: 0.00683999996908824
- `plan2d.smart_snap.alignment.last_ms`: 0.1437830001123075
- `plan2d.smart_snap.alignment.max_ms`: 0.1437830001123075
- `plan2d.smart_snap.alignment.nearest_axes.avg_ms`: 0.01433200031897286
- `plan2d.smart_snap.alignment.nearest_axes.count`: 1
- `plan2d.smart_snap.alignment.nearest_axes.last_ms`: 0.01433200031897286
- `plan2d.smart_snap.alignment.nearest_axes.max_ms`: 0.01433200031897286
- `plan2d.smart_snap.alignment.nearest_axes.p95_ms`: 0.01433200031897286
- `plan2d.smart_snap.alignment.p95_ms`: 0.1437830001123075
- `plan2d.smart_snap.alignment.project.avg_ms`: 0.0029650000215042382
- `plan2d.smart_snap.alignment.project.count`: 1
- `plan2d.smart_snap.alignment.project.last_ms`: 0.0029650000215042382
- `plan2d.smart_snap.alignment.project.max_ms`: 0.0029650000215042382
- `plan2d.smart_snap.alignment.project.p95_ms`: 0.0029650000215042382
- `plan2d.smart_snap.alignment.radius.avg_ms`: 0.002383000264671864
- `plan2d.smart_snap.alignment.radius.count`: 1
- `plan2d.smart_snap.alignment.radius.last_ms`: 0.002383000264671864
- `plan2d.smart_snap.alignment.radius.max_ms`: 0.002383000264671864
- `plan2d.smart_snap.alignment.radius.p95_ms`: 0.002383000264671864
- `plan2d.smart_snap.alignment.scene_cache.avg_ms`: 0.038207000216061715
- `plan2d.smart_snap.alignment.scene_cache.count`: 1
- `plan2d.smart_snap.alignment.scene_cache.last_ms`: 0.038207000216061715
- `plan2d.smart_snap.alignment.scene_cache.max_ms`: 0.038207000216061715
- `plan2d.smart_snap.alignment.scene_cache.p95_ms`: 0.038207000216061715
- `plan2d.smart_snap.alignment_candidates`: 1
- `plan2d.smart_snap.alignment_hits`: 1
- `plan2d.smart_snap.alignment_targets`: 3
- `plan2d.smart_snap.calls`: 2
- `plan2d.smart_snap.extra_targets`: 3
- `plan2d.smart_snap.grid.manager_ignored`: 1
- `plan2d.smart_snap.last_alignment_candidates`: 1
- `plan2d.smart_snap.manager.avg_ms`: 0.11295749982309644
- `plan2d.smart_snap.manager.count`: 2
- `plan2d.smart_snap.manager.last_ms`: 0.09493099969404284
- `plan2d.smart_snap.manager.max_ms`: 0.13098399995215004
- `plan2d.smart_snap.manager.p95_ms`: 0.13098399995215004
- `plan2d.smart_snap.prepare_targets.avg_ms`: 0.00030999990485724993
- `plan2d.smart_snap.prepare_targets.count`: 2
- `plan2d.smart_snap.prepare_targets.last_ms`: 0.0003199997991032433
- `plan2d.smart_snap.prepare_targets.max_ms`: 0.0003199997991032433
- `plan2d.smart_snap.prepare_targets.p95_ms`: 0.0003199997991032433
- `plan2d.smart_snap.total.avg_ms`: 0.2019190001192328
- `plan2d.smart_snap.total.count`: 2
- `plan2d.smart_snap.total.last_ms`: 0.25965500026359223
- `plan2d.smart_snap.total.max_ms`: 0.25965500026359223
- `plan2d.smart_snap.total.p95_ms`: 0.25965500026359223
- `plan_trace.cursor.actor_sync.avg_ms`: 0.4698169998391677
- `plan_trace.cursor.actor_sync.count`: 2
- `plan_trace.cursor.actor_sync.last_ms`: 0.4434679999576474
- `plan_trace.cursor.actor_sync.max_ms`: 0.496165999720688
- `plan_trace.cursor.actor_sync.p95_ms`: 0.496165999720688
- `plan_trace.cursor.align_targets`: 3
- `plan_trace.cursor.constraint.avg_ms`: 0.0020380002752062865
- `plan_trace.cursor.constraint.count`: 2
- `plan_trace.cursor.constraint.last_ms`: 0.0019230001271353103
- `plan_trace.cursor.constraint.max_ms`: 0.0021530004232772626
- `plan_trace.cursor.constraint.p95_ms`: 0.0021530004232772626
- `plan_trace.cursor.moves`: 2
- `plan_trace.cursor.near_targets`: 3
- `plan_trace.cursor.pending_preview.avg_ms`: 0.22723199981555808
- `plan_trace.cursor.pending_preview.count`: 2
- `plan_trace.cursor.pending_preview.last_ms`: 0.4349849996287958
- `plan_trace.cursor.pending_preview.max_ms`: 0.4349849996287958
- `plan_trace.cursor.pending_preview.p95_ms`: 0.4349849996287958
- `plan_trace.cursor.project.avg_ms`: 0.007877000143707846
- `plan_trace.cursor.project.count`: 2
- `plan_trace.cursor.project.last_ms`: 0.007541000286437338
- `plan_trace.cursor.project.max_ms`: 0.008213000000978354
- `plan_trace.cursor.project.p95_ms`: 0.008213000000978354
- `plan_trace.cursor.register_cursor.avg_ms`: 0.40455549992657325
- `plan_trace.cursor.register_cursor.count`: 2
- `plan_trace.cursor.register_cursor.last_ms`: 0.3806849999818951
- `plan_trace.cursor.register_cursor.max_ms`: 0.4284259998712514
- `plan_trace.cursor.register_cursor.p95_ms`: 0.4284259998712514
- `plan_trace.cursor.smart_snap.avg_ms`: 0.22122799987300823
- `plan_trace.cursor.smart_snap.count`: 2
- `plan_trace.cursor.smart_snap.last_ms`: 0.2781129996947129
- `plan_trace.cursor.smart_snap.max_ms`: 0.2781129996947129
- `plan_trace.cursor.smart_snap.p95_ms`: 0.2781129996947129
- `plan_trace.cursor.sync_actor_visuals.avg_ms`: 0.031155999977272586
- `plan_trace.cursor.sync_actor_visuals.count`: 2
- `plan_trace.cursor.sync_actor_visuals.last_ms`: 0.03424099986659712
- `plan_trace.cursor.sync_actor_visuals.max_ms`: 0.03424099986659712
- `plan_trace.cursor.sync_actor_visuals.p95_ms`: 0.03424099986659712
- `plan_trace.cursor.sync_report.avg_ms`: 0.007646000312888646
- `plan_trace.cursor.sync_report.count`: 2
- `plan_trace.cursor.sync_report.last_ms`: 0.002383000264671864
- `plan_trace.cursor.sync_report.max_ms`: 0.012909000361105427
- `plan_trace.cursor.sync_report.p95_ms`: 0.012909000361105427
- `plan_trace.cursor.targets.avg_ms`: 0.1939774997481436
- `plan_trace.cursor.targets.count`: 2
- `plan_trace.cursor.targets.last_ms`: 0.19475899989629397
- `plan_trace.cursor.targets.max_ms`: 0.19475899989629397
- `plan_trace.cursor.targets.p95_ms`: 0.19475899989629397
- `plan_trace.cursor.update.avg_ms`: 1.4722035002705525
- `plan_trace.cursor.update.count`: 2
- `plan_trace.cursor.update.last_ms`: 1.7056800002137606
- `plan_trace.cursor.update.max_ms`: 1.7056800002137606
- `plan_trace.cursor.update.p95_ms`: 1.7056800002137606
- `plan_trace.diagnostic.enabled`: 1
- `plan_trace.draw_press.line.avg_ms`: 2.7460324999992736
- `plan_trace.draw_press.line.count`: 2
- `plan_trace.draw_press.line.last_ms`: 3.8618769999629876
- `plan_trace.draw_press.line.max_ms`: 3.8618769999629876
- `plan_trace.draw_press.line.p95_ms`: 3.8618769999629876
- `plan_trace.draw_press.record_history.avg_ms`: 0.013459000001603272
- `plan_trace.draw_press.record_history.count`: 1
- `plan_trace.draw_press.record_history.last_ms`: 0.013459000001603272
- `plan_trace.draw_press.record_history.max_ms`: 0.013459000001603272
- `plan_trace.draw_press.record_history.p95_ms`: 0.013459000001603272
- `plan_trace.draw_press.snapshot.avg_ms`: 0.010100000054080738
- `plan_trace.draw_press.snapshot.count`: 2
- `plan_trace.draw_press.snapshot.last_ms`: 0.009463999958825298
- `plan_trace.draw_press.snapshot.max_ms`: 0.010736000149336178
- `plan_trace.draw_press.snapshot.p95_ms`: 0.010736000149336178
- `plan_trace.draw_press.tool.line`: 2
- `plan_trace.draw_press.total.avg_ms`: 5.308122500082391
- `plan_trace.draw_press.total.count`: 2
- `plan_trace.draw_press.total.last_ms`: 6.971399000121892
- `plan_trace.draw_press.total.max_ms`: 6.971399000121892
- `plan_trace.draw_press.total.p95_ms`: 6.971399000121892
- `plan_trace.event.mouse_press`: 3
- `plan_trace.event.mouse_press.draw_press.avg_ms`: 5.318307499919683
- `plan_trace.event.mouse_press.draw_press.count`: 2
- `plan_trace.event.mouse_press.draw_press.last_ms`: 6.98498900010236
- `plan_trace.event.mouse_press.draw_press.max_ms`: 6.98498900010236
- `plan_trace.event.mouse_press.draw_press.p95_ms`: 6.98498900010236
- `plan_trace.event.mouse_press.total.avg_ms`: 4.943454999950821
- `plan_trace.event.mouse_press.total.count`: 3
- `plan_trace.event.mouse_press.total.last_ms`: 7.105588999820611
- `plan_trace.event.mouse_press.total.max_ms`: 7.105588999820611
- `plan_trace.event.mouse_press.total.p95_ms`: 7.105588999820611
- `plan_trace.event.total.avg_ms`: 4.949634666597073
- `plan_trace.event.total.count`: 3
- `plan_trace.event.total.last_ms`: 7.11154800001168
- `plan_trace.event.total.max_ms`: 7.11154800001168
- `plan_trace.event.total.p95_ms`: 7.11154800001168
- `plan_trace.lifecycle.open.avg_ms`: 3.547079999862035
- `plan_trace.lifecycle.open.count`: 1
- `plan_trace.lifecycle.open.last_ms`: 3.547079999862035
- `plan_trace.lifecycle.open.max_ms`: 3.547079999862035
- `plan_trace.lifecycle.open.p95_ms`: 3.547079999862035
- `plan_trace.lifecycle.open.scene_cache_rebuild.avg_ms`: 0.07290899975487264
- `plan_trace.lifecycle.open.scene_cache_rebuild.count`: 1
- `plan_trace.lifecycle.open.scene_cache_rebuild.last_ms`: 0.07290899975487264
- `plan_trace.lifecycle.open.scene_cache_rebuild.max_ms`: 0.07290899975487264
- `plan_trace.lifecycle.open.scene_cache_rebuild.p95_ms`: 0.07290899975487264
- `plan_trace.modify.selection_api_event.avg_ms`: 0.000475999968330143
- `plan_trace.modify.selection_api_event.count`: 2
- `plan_trace.modify.selection_api_event.last_ms`: 0.00042100009522982873
- `plan_trace.modify.selection_api_event.max_ms`: 0.0005309998414304573
- `plan_trace.modify.selection_api_event.p95_ms`: 0.0005309998414304573
- `plan_trace.render.avg_ms`: 0.9442835000754712
- `plan_trace.render.count`: 4
- `plan_trace.render.last_ms`: 0.94347000003836
- `plan_trace.render.max_ms`: 1.0615950000101293
- `plan_trace.render.p95_ms`: 1.0615950000101293
- `plan_trace.sketch.actor_visual_sync.avg_ms`: 0.4747349998979189
- `plan_trace.sketch.actor_visual_sync.count`: 1
- `plan_trace.sketch.actor_visual_sync.last_ms`: 0.4747349998979189
- `plan_trace.sketch.actor_visual_sync.max_ms`: 0.4747349998979189
- `plan_trace.sketch.actor_visual_sync.p95_ms`: 0.4747349998979189
- `plan_trace.sketch.changed_actors`: 2
- `plan_trace.sketch.compile_cache_misses`: 1
- `plan_trace.sketch.compile_kernel.avg_ms`: 0.20328200025687693
- `plan_trace.sketch.compile_kernel.count`: 1
- `plan_trace.sketch.compile_kernel.last_ms`: 0.20328200025687693
- `plan_trace.sketch.compile_kernel.max_ms`: 0.20328200025687693
- `plan_trace.sketch.compile_kernel.p95_ms`: 0.20328200025687693
- `plan_trace.snap.build_screen_index.avg_ms`: 0.015502999985983479
- `plan_trace.snap.build_screen_index.count`: 2
- `plan_trace.snap.build_screen_index.last_ms`: 0.01667500009716605
- `plan_trace.snap.build_screen_index.max_ms`: 0.01667500009716605
- `plan_trace.snap.build_screen_index.p95_ms`: 0.01667500009716605
- `plan_trace.snap.index_cells`: 8
- `plan_trace.snap.index_fallback_targets`: 0
- `plan_trace.snap.index_targets`: 3
- `plan_trace.snap.last_near_index_candidates`: 2
- `plan_trace.snap.last_near_targets`: 2
- `plan_trace.snap.near_fallback_targets`: 0
- `plan_trace.snap.near_index_candidates`: 3
- `plan_trace.snap.near_queries`: 2
- `plan_trace.snap.near_query.cells.avg_ms`: 0.00305499997921288
- `plan_trace.snap.near_query.cells.count`: 2
- `plan_trace.snap.near_query.cells.last_ms`: 0.0030950000109442044
- `plan_trace.snap.near_query.cells.max_ms`: 0.0030950000109442044
- `plan_trace.snap.near_query.cells.p95_ms`: 0.0030950000109442044
- `plan_trace.snap.near_query.materialize.avg_ms`: 0.001637499963180744
- `plan_trace.snap.near_query.materialize.count`: 2
- `plan_trace.snap.near_query.materialize.last_ms`: 0.001641999915591441
- `plan_trace.snap.near_query.materialize.max_ms`: 0.001641999915591441
- `plan_trace.snap.near_query.materialize.p95_ms`: 0.001641999915591441
- `plan_trace.snap.near_query.total.avg_ms`: 0.06716449979649042
- `plan_trace.snap.near_query.total.count`: 2
- `plan_trace.snap.near_query.total.last_ms`: 0.06691899989164085
- `plan_trace.snap.near_query.total.max_ms`: 0.06740999970133998
- `plan_trace.snap.near_query.total.p95_ms`: 0.06740999970133998
- `plan_trace.snap.near_targets`: 3
- `plan_trace.snap.rebuild_reason.initial`: 2
- `plan_trace.snap.screen_index_misses`: 2
- `plan_trace.snap_targets.anchors`: 1
- `plan_trace.snap_targets.arc_segments`: 0
- `plan_trace.snap_targets.arcs`: 0
- `plan_trace.snap_targets.bezier_segments`: 0
- `plan_trace.snap_targets.beziers`: 0
- `plan_trace.snap_targets.build.anchor.avg_ms`: 0.015127000096981646
- `plan_trace.snap_targets.build.anchor.count`: 2
- `plan_trace.snap_targets.build.anchor.last_ms`: 0.01034500019159168
- `plan_trace.snap_targets.build.anchor.max_ms`: 0.019909000002371613
- `plan_trace.snap_targets.build.anchor.p95_ms`: 0.019909000002371613
- `plan_trace.snap_targets.build.arcs.avg_ms`: 0.0002950000634882599
- `plan_trace.snap_targets.build.arcs.count`: 2
- `plan_trace.snap_targets.build.arcs.last_ms`: 0.00032000025385059416
- `plan_trace.snap_targets.build.arcs.max_ms`: 0.00032000025385059416
- `plan_trace.snap_targets.build.arcs.p95_ms`: 0.00032000025385059416
- `plan_trace.snap_targets.build.beziers.avg_ms`: 0.000475999968330143
- `plan_trace.snap_targets.build.beziers.count`: 2
- `plan_trace.snap_targets.build.beziers.last_ms`: 0.0003209997885278426
- `plan_trace.snap_targets.build.beziers.max_ms`: 0.0006310001481324434
- `plan_trace.snap_targets.build.beziers.p95_ms`: 0.0006310001481324434
- `plan_trace.snap_targets.build.circles.avg_ms`: 0.0003149998519802466
- `plan_trace.snap_targets.build.circles.count`: 2
- `plan_trace.snap_targets.build.circles.last_ms`: 0.0002299998413946014
- `plan_trace.snap_targets.build.circles.max_ms`: 0.0003999998625658918
- `plan_trace.snap_targets.build.circles.p95_ms`: 0.0003999998625658918
- `plan_trace.snap_targets.build.lines.avg_ms`: 0.0004304999947635224
- `plan_trace.snap_targets.build.lines.count`: 2
- `plan_trace.snap_targets.build.lines.last_ms`: 0.0004809999154531397
- `plan_trace.snap_targets.build.lines.max_ms`: 0.0004809999154531397
- `plan_trace.snap_targets.build.lines.p95_ms`: 0.0004809999154531397
- `plan_trace.snap_targets.build.points.avg_ms`: 0.008306999916385394
- `plan_trace.snap_targets.build.points.count`: 2
- `plan_trace.snap_targets.build.points.last_ms`: 0.01625400000193622
- `plan_trace.snap_targets.build.points.max_ms`: 0.01625400000193622
- `plan_trace.snap_targets.build.points.p95_ms`: 0.01625400000193622
- `plan_trace.snap_targets.build_live_targets.avg_ms`: 0.07098049991327571
- `plan_trace.snap_targets.build_live_targets.count`: 2
- `plan_trace.snap_targets.build_live_targets.last_ms`: 0.07355899970207247
- `plan_trace.snap_targets.build_live_targets.max_ms`: 0.07355899970207247
- `plan_trace.snap_targets.build_live_targets.p95_ms`: 0.07355899970207247
- `plan_trace.snap_targets.circles`: 0
- `plan_trace.snap_targets.fast_signature.avg_ms`: 0.0013764999948762124
- `plan_trace.snap_targets.fast_signature.count`: 2
- `plan_trace.snap_targets.fast_signature.last_ms`: 0.0011910001376236323
- `plan_trace.snap_targets.fast_signature.max_ms`: 0.0015619998521287926
- `plan_trace.snap_targets.fast_signature.p95_ms`: 0.0015619998521287926
- `plan_trace.snap_targets.fast_signature_misses`: 2
- `plan_trace.snap_targets.lines`: 0
- `plan_trace.snap_targets.points`: 1
- `plan_trace.snap_targets.rebuilds`: 2
- `plan_trace.snap_targets.structural_signature.avg_ms`: 0.01071599990609684
- `plan_trace.snap_targets.structural_signature.count`: 2
- `plan_trace.snap_targets.structural_signature.last_ms`: 0.010214999747404363
- `plan_trace.snap_targets.structural_signature.max_ms`: 0.011217000064789318
- `plan_trace.snap_targets.structural_signature.p95_ms`: 0.011217000064789318
- `plan_trace.snap_targets.structural_signature_misses`: 2
- `plan_trace.snap_targets.total`: 2
- `plan_trace.surface.pick_press.avg_ms`: 3.861276999941765
- `plan_trace.surface.pick_press.count`: 1
- `plan_trace.surface.pick_press.last_ms`: 3.861276999941765
- `plan_trace.surface.pick_press.max_ms`: 3.861276999941765
- `plan_trace.surface.pick_press.p95_ms`: 3.861276999941765
- `render.full`: 1
- `scene_cache.bounds`: 0
- `scene_cache.extra_targets`: 0
- `scene_cache.mesh.collect_objects.avg_ms`: 0.009023000075103482
- `scene_cache.mesh.collect_objects.count`: 1
- `scene_cache.mesh.collect_objects.last_ms`: 0.009023000075103482
- `scene_cache.mesh.collect_objects.max_ms`: 0.009023000075103482
- `scene_cache.mesh.collect_objects.p95_ms`: 0.009023000075103482
- `scene_cache.mesh.objects`: 0
- `scene_cache.points`: 0
- `scene_cache.rebuild.calls`: 1
- `scene_cache.rebuild.collect_document_meshes.avg_ms`: 0.01777600027708104
- `scene_cache.rebuild.collect_document_meshes.count`: 1
- `scene_cache.rebuild.collect_document_meshes.last_ms`: 0.01777600027708104
- `scene_cache.rebuild.collect_document_meshes.max_ms`: 0.01777600027708104
- `scene_cache.rebuild.collect_document_meshes.p95_ms`: 0.01777600027708104
- `scene_cache.rebuild.collect_scene.avg_ms`: 0.0024739997570577543
- `scene_cache.rebuild.collect_scene.count`: 1
- `scene_cache.rebuild.collect_scene.last_ms`: 0.0024739997570577543
- `scene_cache.rebuild.collect_scene.max_ms`: 0.0024739997570577543
- `scene_cache.rebuild.collect_scene.p95_ms`: 0.0024739997570577543
- `scene_cache.rebuild.collect_selection.avg_ms`: 0.0026940001589537133
- `scene_cache.rebuild.collect_selection.count`: 1
- `scene_cache.rebuild.collect_selection.last_ms`: 0.0026940001589537133
- `scene_cache.rebuild.collect_selection.max_ms`: 0.0026940001589537133
- `scene_cache.rebuild.collect_selection.p95_ms`: 0.0026940001589537133
- `scene_cache.rebuild.collect_sketch.avg_ms`: 0.002874000074370997
- `scene_cache.rebuild.collect_sketch.count`: 1
- `scene_cache.rebuild.collect_sketch.last_ms`: 0.002874000074370997
- `scene_cache.rebuild.collect_sketch.max_ms`: 0.002874000074370997
- `scene_cache.rebuild.collect_sketch.p95_ms`: 0.002874000074370997
- `scene_cache.rebuild.total.avg_ms`: 0.0658369999655406
- `scene_cache.rebuild.total.count`: 1
- `scene_cache.rebuild.total.last_ms`: 0.0658369999655406
- `scene_cache.rebuild.total.max_ms`: 0.0658369999655406
- `scene_cache.rebuild.total.p95_ms`: 0.0658369999655406
- `scene_cache.segments`: 0
- `scene_cache.snap.index_cells`: 0
- `scene_cache.snap.index_fallback`: 0
- `scene_cache.snap.index_targets`: 0
- `scene_cache.snap.near_query.total.avg_ms`: 0.025677999929030193
- `scene_cache.snap.near_query.total.count`: 2
- `scene_cache.snap.near_query.total.last_ms`: 0.013549999948736513
- `scene_cache.snap.near_query.total.max_ms`: 0.03780599990932387
- `scene_cache.snap.near_query.total.p95_ms`: 0.03780599990932387
- `scene_cache.snap.projection.has_camera`: 0
- `scene_cache.snap.projection.has_owner_plotter`: 0
- `scene_cache.snap.projection.has_viewport_plotter`: 0
- `scene_cache.snap.projection_signature_changed`: 0
- `scene_cache.snap.rebuild_reason.initial`: 1
- `scene_cache.snap.rebuild_reason.last`: hit
- `scene_cache.snap.rebuild_screen_index.avg_ms`: 0.004768000053445576
- `scene_cache.snap.rebuild_screen_index.count`: 1
- `scene_cache.snap.rebuild_screen_index.last_ms`: 0.004768000053445576
- `scene_cache.snap.rebuild_screen_index.max_ms`: 0.004768000053445576
- `scene_cache.snap.rebuild_screen_index.p95_ms`: 0.004768000053445576
- `scene_cache.snap.screen_index_hits`: 1
- `scene_cache.snap.screen_index_misses`: 1
- `scene_cache.snap.structure_signature_changed`: 0
- `scene_cache.version`: 2
- `snap.manager.filtered_candidates`: 1
- `snap.manager.object_scope.filtered_scene_targets`: 0
- `snap.manager.object_scope.scene_targets`: 0
- `snap.manager.providers.avg_ms`: 0.0002655001480889041
- `snap.manager.providers.count`: 2
- `snap.manager.providers.last_ms`: 0.00027000032787327655
- `snap.manager.providers.max_ms`: 0.00027000032787327655
- `snap.manager.providers.p95_ms`: 0.00027000032787327655
- `snap.manager.queries`: 2
- `snap.manager.raw_candidates`: 1
- `snap.manager.target_pool`: 3
- `snap.manager.targets_to_results.avg_ms`: 0.04345999991528515
- `snap.manager.targets_to_results.count`: 2
- `snap.manager.targets_to_results.last_ms`: 0.036734999866894213
- `snap.manager.targets_to_results.max_ms`: 0.05018499996367609
- `snap.manager.targets_to_results.p95_ms`: 0.05018499996367609
- `snap.targets_to_results.arcs`: 0
- `snap.targets_to_results.circles`: 0
- `snap.targets_to_results.classify.avg_ms`: 0.000785999873187393
- `snap.targets_to_results.classify.count`: 2
- `snap.targets_to_results.classify.last_ms`: 0.0007710000318184029
- `snap.targets_to_results.classify.max_ms`: 0.000800999714556383
- `snap.targets_to_results.classify.p95_ms`: 0.000800999714556383
- `snap.targets_to_results.curve_intersections.avg_ms`: 0.0009414998203283176
- `snap.targets_to_results.curve_intersections.count`: 2
- `snap.targets_to_results.curve_intersections.last_ms`: 0.0008419997357123066
- `snap.targets_to_results.curve_intersections.max_ms`: 0.0010409999049443286
- `snap.targets_to_results.curve_intersections.p95_ms`: 0.0010409999049443286
- `snap.targets_to_results.direct_snaps.avg_ms`: 0.009418999752597301
- `snap.targets_to_results.direct_snaps.count`: 2
- `snap.targets_to_results.direct_snaps.last_ms`: 0.00401599982069456
- `snap.targets_to_results.direct_snaps.max_ms`: 0.014821999684500042
- `snap.targets_to_results.direct_snaps.p95_ms`: 0.014821999684500042
- `snap.targets_to_results.results`: 1
- `snap.targets_to_results.segment_intersections.avg_ms`: 0.0008860001798893791
- `snap.targets_to_results.segment_intersections.count`: 2
- `snap.targets_to_results.segment_intersections.last_ms`: 0.0006910004231031053
- `snap.targets_to_results.segment_intersections.max_ms`: 0.0010809999366756529
- `snap.targets_to_results.segment_intersections.p95_ms`: 0.0010809999366756529
- `snap.targets_to_results.segments`: 0
- `snap.targets_to_results.targets`: 3
- `snap.targets_to_results.total.avg_ms`: 0.03755050011022831
- `snap.targets_to_results.total.count`: 2
- `snap.targets_to_results.total.last_ms`: 0.031166000098892255
- `snap.targets_to_results.total.max_ms`: 0.04393500012156437
- `snap.targets_to_results.total.p95_ms`: 0.04393500012156437

## Files to send

Send `diagnostics/plan_trace_selection_length_debug.jsonl`, `diagnostics/plan_trace_selection_length_debug.md`, `diagnostics/plan_trace_2d_timings.md`, `diagnostics/plan_trace_2d_timings.json`, `diagnostics/plan_trace_2d_timings.csv`, `diagnostics/plan_trace_input_debug.jsonl`, and the normal app log.
