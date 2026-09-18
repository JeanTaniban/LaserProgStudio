# LaserProg Studio — application performance audit

Reason: `process_exit`

## Session
| Generated | Elapsed s | Python | Platform | PID | Slow threshold ms |
| --- | --- | --- | --- | --- | --- |
| 2026-08-21 08:44:31 | 1.830 | 3.13.5 | Linux-6.18.35-x86_64-with-glibc2.41 | 4079 | 16.000 |

## Top timers by total time
| Timer | Count | Total ms | Avg ms | P50 ms | P95 ms | P99 ms | Max ms | Last ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| toolctx.plan_trace.event.total | 34 | 153.284 | 4.508 | 3.196 | 11.221 | 15.214 | 15.214 | 1.835 |
| toolctx.plan_trace.event.mouse_press.total | 29 | 148.509 | 5.121 | 3.496 | 11.220 | 15.208 | 15.208 | 5.517 |
| toolctx.plan_trace.event.mouse_press.draw_press | 17 | 108.571 | 6.387 | 3.651 | 11.086 | 15.077 | 15.077 | 5.397 |
| toolctx.plan_trace.draw_press.total | 17 | 108.198 | 6.365 | 3.643 | 11.070 | 15.063 | 15.063 | 5.385 |
| toolctx.plan_trace.draw_press.rectangle | 14 | 63.278 | 4.520 | 1.664 | 7.932 | 12.338 | 12.338 | 7.103 |
| plan_trace.apply.mesh.boolean_ready_extrusion | 9 | 62.807 | 6.979 | 0.869 | 30.796 | 30.796 | 30.796 | 23.054 |
| toolctx.plan_trace.lifecycle.open | 12 | 45.719 | 3.810 | 3.297 | 5.834 | 9.140 | 9.140 | 2.964 |
| toolctx.plan_trace.surface.pick_press | 12 | 36.521 | 3.043 | 2.730 | 4.036 | 4.060 | 4.060 | 4.060 |
| sketch.compile.total | 28 | 33.566 | 1.199 | 0.622 | 3.396 | 3.435 | 3.435 | 1.261 |
| toolctx.plan_trace.render | 57 | 32.615 | 0.572 | 0.424 | 0.919 | 1.103 | 5.395 | 0.332 |
| toolctx.plan_trace.sketch.compile_kernel | 12 | 31.392 | 2.616 | 0.629 | 8.090 | 12.030 | 12.030 | 8.090 |
| sketch.compile.solve_faces | 28 | 29.599 | 1.057 | 0.485 | 3.281 | 3.287 | 3.287 | 1.158 |
| toolctx.plan_trace.cursor.update | 18 | 29.352 | 1.631 | 1.610 | 2.100 | 2.228 | 2.228 | 1.630 |
| sketch.face_solver.build_faces | 25 | 16.748 | 0.670 | 0.157 | 2.550 | 2.631 | 2.631 | 0.752 |
| toolctx.plan2d.actor_visuals.full_interaction | 56 | 11.333 | 0.202 | 0.152 | 0.537 | 1.043 | 1.668 | 0.292 |
| toolctx.plan_trace.cursor.register_cursor | 19 | 7.988 | 0.420 | 0.384 | 0.625 | 0.706 | 0.706 | 0.361 |
| toolctx.plan_trace.cursor.actor_sync | 17 | 7.855 | 0.462 | 0.450 | 0.515 | 0.517 | 0.517 | 0.436 |
| toolctx.plan_trace.sketch.actor_visual_sync | 12 | 5.349 | 0.446 | 0.485 | 0.587 | 0.591 | 0.591 | 0.494 |
| toolctx.plan2d.smart_snap.total | 19 | 5.311 | 0.280 | 0.285 | 0.351 | 0.355 | 0.355 | 0.222 |
| toolctx.plan_trace.cursor.smart_snap | 17 | 5.034 | 0.296 | 0.305 | 0.344 | 0.381 | 0.381 | 0.241 |
| toolctx.plan_trace.native.select.total | 3 | 4.538 | 1.513 | 1.539 | 1.583 | 1.583 | 1.583 | 1.417 |
| toolctx.plan_trace.cursor.targets | 17 | 4.408 | 0.259 | 0.220 | 0.399 | 0.715 | 0.715 | 0.221 |
| toolctx.plan_trace.draw_press.line | 2 | 4.187 | 2.093 | 1.225 | 2.962 | 2.962 | 2.962 | 2.962 |
| toolctx.plan_trace.drag.resolve_positions.total | 1 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 |
| toolctx.plan_trace.cursor.pending_preview | 17 | 3.904 | 0.230 | 0.044 | 0.491 | 0.787 | 0.787 | 0.371 |
| sketch.face_solver.source_curves | 28 | 3.752 | 0.134 | 0.108 | 0.269 | 0.594 | 0.594 | 0.140 |
| toolctx.plan_trace.motif.union_footprint | 3 | 3.182 | 1.061 | 0.925 | 1.480 | 1.480 | 1.480 | 0.925 |
| sketch.face_solver.polygonize | 27 | 3.178 | 0.118 | 0.108 | 0.218 | 0.281 | 0.281 | 0.121 |
| toolctx.plan2d.smart_snap.alignment | 19 | 2.401 | 0.126 | 0.128 | 0.158 | 0.172 | 0.172 | 0.107 |
| toolctx.plan2d.smart_snap.manager | 19 | 2.299 | 0.121 | 0.125 | 0.160 | 0.163 | 0.163 | 0.095 |
| toolctx.plan_trace.event.mouse_move.total | 1 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 |
| toolctx.plan_trace.snap_targets.build_live_targets | 19 | 2.271 | 0.119 | 0.078 | 0.205 | 0.567 | 0.567 | 0.074 |
| toolctx.plan_trace.event.mouse_move.update_cursor | 1 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 |
| toolctx.plan_trace.drag.cursor_actor | 1 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 |
| toolctx.plan_trace.event.key_press.total | 1 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 |
| sketch.face_solver.containment | 25 | 1.772 | 0.071 | 0.038 | 0.169 | 0.169 | 0.169 | 0.071 |
| toolctx.plan_trace.cursor.sync_actor_visuals | 19 | 1.683 | 0.089 | 0.034 | 0.056 | 1.073 | 1.073 | 0.035 |
| toolctx.plan_trace.lifecycle.open.scene_cache_rebuild | 12 | 1.539 | 0.128 | 0.093 | 0.126 | 0.500 | 0.500 | 0.089 |
| toolctx.plan_trace.draw_press.place_point | 1 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 |
| toolctx.plan_trace.snap.near_query.total | 19 | 1.458 | 0.077 | 0.072 | 0.100 | 0.114 | 0.114 | 0.066 |
| toolctx.plan_trace.drag.sync_moved_points | 1 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 |
| toolctx.scene_cache.rebuild.total | 12 | 1.028 | 0.086 | 0.084 | 0.096 | 0.116 | 0.116 | 0.081 |
| toolctx.plan_trace.snap_targets.build.anchor | 19 | 0.889 | 0.047 | 0.022 | 0.065 | 0.486 | 0.486 | 0.010 |
| toolctx.snap.manager.targets_to_results | 19 | 0.755 | 0.040 | 0.036 | 0.042 | 0.098 | 0.098 | 0.034 |
| toolctx.plan2d.smart_snap.alignment.extra_cache | 19 | 0.753 | 0.040 | 0.035 | 0.078 | 0.091 | 0.091 | 0.034 |
| toolctx.plan_trace.cursor.modify_fast_actor_sync | 1 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 |
| toolctx.snap.targets_to_results.total | 19 | 0.645 | 0.034 | 0.030 | 0.036 | 0.091 | 0.091 | 0.029 |
| toolctx.plan_trace.drag.smart_snap | 1 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 |
| sketch.compile.validation | 28 | 0.515 | 0.018 | 0.017 | 0.034 | 0.038 | 0.038 | 0.018 |
| toolctx.scene_cache.snap.near_query.total | 19 | 0.496 | 0.026 | 0.015 | 0.041 | 0.048 | 0.048 | 0.014 |
| toolctx.plan2d.smart_snap.alignment.scene_cache | 19 | 0.482 | 0.025 | 0.014 | 0.041 | 0.045 | 0.045 | 0.012 |
| toolctx.plan2d.guide_cache.extra.build | 19 | 0.445 | 0.023 | 0.019 | 0.063 | 0.075 | 0.075 | 0.019 |
| toolctx.plan_trace.event.mouse_release.total | 3 | 0.424 | 0.141 | 0.129 | 0.169 | 0.169 | 0.169 | 0.126 |
| sketch.compile.rebuild_polylines | 28 | 0.409 | 0.015 | 0.014 | 0.028 | 0.032 | 0.032 | 0.007 |
| toolctx.plan_trace.cursor.modify_local_snap | 1 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 |
| toolctx.scene_cache.rebuild.collect_document_meshes | 12 | 0.376 | 0.031 | 0.031 | 0.036 | 0.043 | 0.043 | 0.029 |
| toolctx.plan_trace.snap.build_screen_index | 19 | 0.374 | 0.020 | 0.017 | 0.037 | 0.041 | 0.041 | 0.016 |
| sketch.compile.insert_line_intersections | 28 | 0.356 | 0.013 | 0.014 | 0.025 | 0.050 | 0.050 | 0.001 |
| sketch.compile.merge_duplicate_points | 28 | 0.351 | 0.013 | 0.012 | 0.019 | 0.029 | 0.029 | 0.009 |
| toolctx.plan_trace.cursor.modify_near_targets | 1 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 |

## Top timers by p95
| Timer | Count | Total ms | Avg ms | P50 ms | P95 ms | P99 ms | Max ms | Last ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plan_trace.apply.mesh.boolean_ready_extrusion | 9 | 62.807 | 6.979 | 0.869 | 30.796 | 30.796 | 30.796 | 23.054 |
| toolctx.plan_trace.event.total | 34 | 153.284 | 4.508 | 3.196 | 11.221 | 15.214 | 15.214 | 1.835 |
| toolctx.plan_trace.event.mouse_press.total | 29 | 148.509 | 5.121 | 3.496 | 11.220 | 15.208 | 15.208 | 5.517 |
| toolctx.plan_trace.event.mouse_press.draw_press | 17 | 108.571 | 6.387 | 3.651 | 11.086 | 15.077 | 15.077 | 5.397 |
| toolctx.plan_trace.draw_press.total | 17 | 108.198 | 6.365 | 3.643 | 11.070 | 15.063 | 15.063 | 5.385 |
| toolctx.plan_trace.sketch.compile_kernel | 12 | 31.392 | 2.616 | 0.629 | 8.090 | 12.030 | 12.030 | 8.090 |
| toolctx.plan_trace.draw_press.rectangle | 14 | 63.278 | 4.520 | 1.664 | 7.932 | 12.338 | 12.338 | 7.103 |
| toolctx.plan_trace.lifecycle.open | 12 | 45.719 | 3.810 | 3.297 | 5.834 | 9.140 | 9.140 | 2.964 |
| toolctx.plan_trace.surface.pick_press | 12 | 36.521 | 3.043 | 2.730 | 4.036 | 4.060 | 4.060 | 4.060 |
| toolctx.plan_trace.drag.resolve_positions.total | 1 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 |
| sketch.compile.total | 28 | 33.566 | 1.199 | 0.622 | 3.396 | 3.435 | 3.435 | 1.261 |
| sketch.compile.solve_faces | 28 | 29.599 | 1.057 | 0.485 | 3.281 | 3.287 | 3.287 | 1.158 |
| toolctx.plan_trace.draw_press.line | 2 | 4.187 | 2.093 | 1.225 | 2.962 | 2.962 | 2.962 | 2.962 |
| sketch.face_solver.build_faces | 25 | 16.748 | 0.670 | 0.157 | 2.550 | 2.631 | 2.631 | 0.752 |
| toolctx.plan_trace.event.mouse_move.total | 1 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 |
| toolctx.plan_trace.cursor.update | 18 | 29.352 | 1.631 | 1.610 | 2.100 | 2.228 | 2.228 | 1.630 |
| toolctx.plan_trace.event.mouse_move.update_cursor | 1 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 |
| toolctx.plan_trace.drag.cursor_actor | 1 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 |
| toolctx.plan_trace.event.key_press.total | 1 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 |
| toolctx.plan_trace.native.select.total | 3 | 4.538 | 1.513 | 1.539 | 1.583 | 1.583 | 1.583 | 1.417 |
| toolctx.plan_trace.motif.union_footprint | 3 | 3.182 | 1.061 | 0.925 | 1.480 | 1.480 | 1.480 | 0.925 |
| toolctx.plan_trace.draw_press.place_point | 1 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 |
| toolctx.plan_trace.drag.sync_moved_points | 1 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 |
| toolctx.plan_trace.render | 57 | 32.615 | 0.572 | 0.424 | 0.919 | 1.103 | 5.395 | 0.332 |
| toolctx.plan_trace.cursor.modify_fast_actor_sync | 1 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 |
| toolctx.plan_trace.drag.smart_snap | 1 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 |
| toolctx.plan_trace.cursor.register_cursor | 19 | 7.988 | 0.420 | 0.384 | 0.625 | 0.706 | 0.706 | 0.361 |
| toolctx.plan_trace.sketch.actor_visual_sync | 12 | 5.349 | 0.446 | 0.485 | 0.587 | 0.591 | 0.591 | 0.494 |
| toolctx.plan2d.actor_visuals.full_interaction | 56 | 11.333 | 0.202 | 0.152 | 0.537 | 1.043 | 1.668 | 0.292 |
| toolctx.plan_trace.cursor.actor_sync | 17 | 7.855 | 0.462 | 0.450 | 0.515 | 0.517 | 0.517 | 0.436 |
| toolctx.plan_trace.cursor.pending_preview | 17 | 3.904 | 0.230 | 0.044 | 0.491 | 0.787 | 0.787 | 0.371 |
| toolctx.plan_trace.cursor.targets | 17 | 4.408 | 0.259 | 0.220 | 0.399 | 0.715 | 0.715 | 0.221 |
| toolctx.plan_trace.cursor.modify_local_snap | 1 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 |
| toolctx.plan2d.smart_snap.total | 19 | 5.311 | 0.280 | 0.285 | 0.351 | 0.355 | 0.355 | 0.222 |
| toolctx.plan_trace.cursor.smart_snap | 17 | 5.034 | 0.296 | 0.305 | 0.344 | 0.381 | 0.381 | 0.241 |
| toolctx.plan_trace.cursor.modify_near_targets | 1 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 |
| sketch.face_solver.source_curves | 28 | 3.752 | 0.134 | 0.108 | 0.269 | 0.594 | 0.594 | 0.140 |
| sketch.face_solver.polygonize | 27 | 3.178 | 0.118 | 0.108 | 0.218 | 0.281 | 0.281 | 0.121 |
| toolctx.plan_trace.snap_targets.build_live_targets | 19 | 2.271 | 0.119 | 0.078 | 0.205 | 0.567 | 0.567 | 0.074 |
| toolctx.plan_trace.event.mouse_release.total | 3 | 0.424 | 0.141 | 0.129 | 0.169 | 0.169 | 0.169 | 0.126 |
| sketch.face_solver.containment | 25 | 1.772 | 0.071 | 0.038 | 0.169 | 0.169 | 0.169 | 0.071 |
| toolctx.plan2d.smart_snap.manager | 19 | 2.299 | 0.121 | 0.125 | 0.160 | 0.163 | 0.163 | 0.095 |
| toolctx.plan2d.smart_snap.alignment | 19 | 2.401 | 0.126 | 0.128 | 0.158 | 0.172 | 0.172 | 0.107 |
| toolctx.plan_trace.lifecycle.open.scene_cache_rebuild | 12 | 1.539 | 0.128 | 0.093 | 0.126 | 0.500 | 0.500 | 0.089 |
| toolctx.plan_trace.snap.near_query.total | 19 | 1.458 | 0.077 | 0.072 | 0.100 | 0.114 | 0.114 | 0.066 |
| toolctx.scene_cache.rebuild.total | 12 | 1.028 | 0.086 | 0.084 | 0.096 | 0.116 | 0.116 | 0.081 |
| toolctx.plan2d.smart_snap.alignment.extra_cache | 19 | 0.753 | 0.040 | 0.035 | 0.078 | 0.091 | 0.091 | 0.034 |
| toolctx.plan_trace.snap_targets.build.anchor | 19 | 0.889 | 0.047 | 0.022 | 0.065 | 0.486 | 0.486 | 0.010 |
| toolctx.plan2d.guide_cache.extra.build | 19 | 0.445 | 0.023 | 0.019 | 0.063 | 0.075 | 0.075 | 0.019 |
| toolctx.plan_trace.cursor.sync_actor_visuals | 19 | 1.683 | 0.089 | 0.034 | 0.056 | 1.073 | 1.073 | 0.035 |
| toolctx.plan_trace.snap_targets.build.points | 19 | 0.249 | 0.013 | 0.015 | 0.043 | 0.044 | 0.044 | 0.017 |
| toolctx.snap.manager.targets_to_results | 19 | 0.755 | 0.040 | 0.036 | 0.042 | 0.098 | 0.098 | 0.034 |
| toolctx.scene_cache.snap.near_query.total | 19 | 0.496 | 0.026 | 0.015 | 0.041 | 0.048 | 0.048 | 0.014 |
| toolctx.plan2d.smart_snap.alignment.scene_cache | 19 | 0.482 | 0.025 | 0.014 | 0.041 | 0.045 | 0.045 | 0.012 |
| toolctx.plan_trace.snap.build_screen_index | 19 | 0.374 | 0.020 | 0.017 | 0.037 | 0.041 | 0.041 | 0.016 |
| toolctx.scene_cache.rebuild.collect_document_meshes | 12 | 0.376 | 0.031 | 0.031 | 0.036 | 0.043 | 0.043 | 0.029 |
| toolctx.snap.targets_to_results.total | 19 | 0.645 | 0.034 | 0.030 | 0.036 | 0.091 | 0.091 | 0.029 |
| sketch.compile.validation | 28 | 0.515 | 0.018 | 0.017 | 0.034 | 0.038 | 0.038 | 0.018 |
| toolctx.plan_trace.snap_targets.build.lines | 19 | 0.084 | 0.004 | 0.001 | 0.034 | 0.040 | 0.040 | 0.001 |
| sketch.compile.rebuild_polylines | 28 | 0.409 | 0.015 | 0.014 | 0.028 | 0.032 | 0.032 | 0.007 |

## Top timers by call count
| Timer | Count | Total ms | Avg ms | P50 ms | P95 ms | P99 ms | Max ms | Last ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| toolctx.plan_trace.render | 57 | 32.615 | 0.572 | 0.424 | 0.919 | 1.103 | 5.395 | 0.332 |
| toolctx.plan2d.actor_visuals.full_interaction | 56 | 11.333 | 0.202 | 0.152 | 0.537 | 1.043 | 1.668 | 0.292 |
| toolctx.plan_trace.event.total | 34 | 153.284 | 4.508 | 3.196 | 11.221 | 15.214 | 15.214 | 1.835 |
| toolctx.plan_trace.event.mouse_press.total | 29 | 148.509 | 5.121 | 3.496 | 11.220 | 15.208 | 15.208 | 5.517 |
| sketch.compile.insert_line_intersections | 28 | 0.356 | 0.013 | 0.014 | 0.025 | 0.050 | 0.050 | 0.001 |
| sketch.compile.merge_duplicate_points | 28 | 0.351 | 0.013 | 0.012 | 0.019 | 0.029 | 0.029 | 0.009 |
| sketch.compile.rebuild_polylines | 28 | 0.409 | 0.015 | 0.014 | 0.028 | 0.032 | 0.032 | 0.007 |
| sketch.compile.remove_degenerate_curves | 28 | 0.100 | 0.004 | 0.002 | 0.019 | 0.028 | 0.028 | 0.004 |
| sketch.compile.remove_degenerate_lines.final | 28 | 0.049 | 0.002 | 0.002 | 0.003 | 0.004 | 0.004 | 0.000 |
| sketch.compile.remove_degenerate_lines.initial | 28 | 0.104 | 0.004 | 0.004 | 0.006 | 0.017 | 0.017 | 0.001 |
| sketch.compile.remove_duplicate_lines | 28 | 0.080 | 0.003 | 0.003 | 0.004 | 0.019 | 0.019 | 0.001 |
| sketch.compile.solve_faces | 28 | 29.599 | 1.057 | 0.485 | 3.281 | 3.287 | 3.287 | 1.158 |
| sketch.compile.split_lines_at_vertices | 28 | 0.272 | 0.010 | 0.011 | 0.022 | 0.038 | 0.038 | 0.001 |
| sketch.compile.total | 28 | 33.566 | 1.199 | 0.622 | 3.396 | 3.435 | 3.435 | 1.261 |
| sketch.compile.validation | 28 | 0.515 | 0.018 | 0.017 | 0.034 | 0.038 | 0.038 | 0.018 |
| sketch.face_solver.source_curves | 28 | 3.752 | 0.134 | 0.108 | 0.269 | 0.594 | 0.594 | 0.140 |
| sketch.face_solver.polygonize | 27 | 3.178 | 0.118 | 0.108 | 0.218 | 0.281 | 0.281 | 0.121 |
| sketch.face_solver.build_faces | 25 | 16.748 | 0.670 | 0.157 | 2.550 | 2.631 | 2.631 | 0.752 |
| sketch.face_solver.containment | 25 | 1.772 | 0.071 | 0.038 | 0.169 | 0.169 | 0.169 | 0.071 |
| toolctx.plan_trace.modify.selection_api_event | 21 | 0.040 | 0.002 | 0.001 | 0.010 | 0.010 | 0.010 | 0.000 |
| toolctx.plan_trace.snap_targets.fast_signature | 20 | 0.042 | 0.002 | 0.002 | 0.003 | 0.004 | 0.004 | 0.002 |
| toolctx.plan2d.guide_cache.extra.build | 19 | 0.445 | 0.023 | 0.019 | 0.063 | 0.075 | 0.075 | 0.019 |
| toolctx.plan2d.smart_snap.alignment | 19 | 2.401 | 0.126 | 0.128 | 0.158 | 0.172 | 0.172 | 0.107 |
| toolctx.plan2d.smart_snap.alignment.extra_cache | 19 | 0.753 | 0.040 | 0.035 | 0.078 | 0.091 | 0.091 | 0.034 |
| toolctx.plan2d.smart_snap.alignment.intersection_candidate | 19 | 0.135 | 0.007 | 0.007 | 0.009 | 0.011 | 0.011 | 0.007 |
| toolctx.plan2d.smart_snap.alignment.nearest_axes | 19 | 0.234 | 0.012 | 0.012 | 0.015 | 0.017 | 0.017 | 0.013 |
| toolctx.plan2d.smart_snap.alignment.project | 19 | 0.052 | 0.003 | 0.003 | 0.003 | 0.003 | 0.003 | 0.003 |
| toolctx.plan2d.smart_snap.alignment.radius | 19 | 0.044 | 0.002 | 0.002 | 0.003 | 0.004 | 0.004 | 0.002 |
| toolctx.plan2d.smart_snap.alignment.scene_cache | 19 | 0.482 | 0.025 | 0.014 | 0.041 | 0.045 | 0.045 | 0.012 |
| toolctx.plan2d.smart_snap.manager | 19 | 2.299 | 0.121 | 0.125 | 0.160 | 0.163 | 0.163 | 0.095 |
| toolctx.plan2d.smart_snap.prepare_targets | 19 | 0.006 | 0.000 | 0.000 | 0.000 | 0.001 | 0.001 | 0.000 |
| toolctx.plan2d.smart_snap.total | 19 | 5.311 | 0.280 | 0.285 | 0.351 | 0.355 | 0.355 | 0.222 |
| toolctx.plan_trace.cursor.register_cursor | 19 | 7.988 | 0.420 | 0.384 | 0.625 | 0.706 | 0.706 | 0.361 |
| toolctx.plan_trace.cursor.sync_actor_visuals | 19 | 1.683 | 0.089 | 0.034 | 0.056 | 1.073 | 1.073 | 0.035 |
| toolctx.plan_trace.cursor.sync_report | 19 | 0.180 | 0.009 | 0.013 | 0.015 | 0.016 | 0.016 | 0.014 |
| toolctx.plan_trace.snap.build_screen_index | 19 | 0.374 | 0.020 | 0.017 | 0.037 | 0.041 | 0.041 | 0.016 |
| toolctx.plan_trace.snap.near_query.cells | 19 | 0.035 | 0.002 | 0.002 | 0.003 | 0.003 | 0.003 | 0.002 |
| toolctx.plan_trace.snap.near_query.materialize | 19 | 0.030 | 0.002 | 0.001 | 0.003 | 0.003 | 0.003 | 0.001 |
| toolctx.plan_trace.snap.near_query.total | 19 | 1.458 | 0.077 | 0.072 | 0.100 | 0.114 | 0.114 | 0.066 |
| toolctx.plan_trace.snap_targets.build.anchor | 19 | 0.889 | 0.047 | 0.022 | 0.065 | 0.486 | 0.486 | 0.010 |
| toolctx.plan_trace.snap_targets.build.arcs | 19 | 0.011 | 0.001 | 0.001 | 0.001 | 0.002 | 0.002 | 0.001 |
| toolctx.plan_trace.snap_targets.build.beziers | 19 | 0.008 | 0.000 | 0.000 | 0.001 | 0.001 | 0.001 | 0.000 |
| toolctx.plan_trace.snap_targets.build.circles | 19 | 0.009 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | 0.000 |
| toolctx.plan_trace.snap_targets.build.lines | 19 | 0.084 | 0.004 | 0.001 | 0.034 | 0.040 | 0.040 | 0.001 |
| toolctx.plan_trace.snap_targets.build.points | 19 | 0.249 | 0.013 | 0.015 | 0.043 | 0.044 | 0.044 | 0.017 |
| toolctx.plan_trace.snap_targets.build_live_targets | 19 | 2.271 | 0.119 | 0.078 | 0.205 | 0.567 | 0.567 | 0.074 |
| toolctx.plan_trace.snap_targets.structural_signature | 19 | 0.239 | 0.013 | 0.012 | 0.015 | 0.016 | 0.016 | 0.011 |
| toolctx.scene_cache.snap.near_query.total | 19 | 0.496 | 0.026 | 0.015 | 0.041 | 0.048 | 0.048 | 0.014 |
| toolctx.snap.manager.providers | 19 | 0.007 | 0.000 | 0.000 | 0.001 | 0.001 | 0.001 | 0.001 |
| toolctx.snap.manager.targets_to_results | 19 | 0.755 | 0.040 | 0.036 | 0.042 | 0.098 | 0.098 | 0.034 |
| toolctx.snap.targets_to_results.classify | 19 | 0.020 | 0.001 | 0.000 | 0.001 | 0.013 | 0.013 | 0.000 |
| toolctx.snap.targets_to_results.curve_intersections | 19 | 0.021 | 0.001 | 0.001 | 0.001 | 0.002 | 0.002 | 0.001 |
| toolctx.snap.targets_to_results.direct_snaps | 19 | 0.048 | 0.003 | 0.000 | 0.005 | 0.038 | 0.038 | 0.000 |
| toolctx.snap.targets_to_results.segment_intersections | 19 | 0.026 | 0.001 | 0.001 | 0.001 | 0.010 | 0.010 | 0.001 |
| toolctx.snap.targets_to_results.total | 19 | 0.645 | 0.034 | 0.030 | 0.036 | 0.091 | 0.091 | 0.029 |
| toolctx.plan_trace.cursor.project | 18 | 0.169 | 0.009 | 0.009 | 0.013 | 0.015 | 0.015 | 0.007 |
| toolctx.plan_trace.cursor.update | 18 | 29.352 | 1.631 | 1.610 | 2.100 | 2.228 | 2.228 | 1.630 |
| toolctx.plan_trace.cursor.actor_sync | 17 | 7.855 | 0.462 | 0.450 | 0.515 | 0.517 | 0.517 | 0.436 |
| toolctx.plan_trace.cursor.constraint | 17 | 0.042 | 0.003 | 0.003 | 0.004 | 0.005 | 0.005 | 0.002 |
| toolctx.plan_trace.cursor.pending_preview | 17 | 3.904 | 0.230 | 0.044 | 0.491 | 0.787 | 0.787 | 0.371 |

## All timers
| Timer | Count | Total ms | Avg ms | P50 ms | P95 ms | P99 ms | Max ms | Last ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plan_trace.apply.mesh.boolean_ready_extrusion | 9 | 62.807 | 6.979 | 0.869 | 30.796 | 30.796 | 30.796 | 23.054 |
| sketch.compile.insert_curve_intersections | 7 | 0.042 | 0.006 | 0.004 | 0.016 | 0.016 | 0.016 | 0.016 |
| sketch.compile.insert_line_intersections | 28 | 0.356 | 0.013 | 0.014 | 0.025 | 0.050 | 0.050 | 0.001 |
| sketch.compile.merge_duplicate_points | 28 | 0.351 | 0.013 | 0.012 | 0.019 | 0.029 | 0.029 | 0.009 |
| sketch.compile.rebuild_polylines | 28 | 0.409 | 0.015 | 0.014 | 0.028 | 0.032 | 0.032 | 0.007 |
| sketch.compile.remove_degenerate_curves | 28 | 0.100 | 0.004 | 0.002 | 0.019 | 0.028 | 0.028 | 0.004 |
| sketch.compile.remove_degenerate_lines.final | 28 | 0.049 | 0.002 | 0.002 | 0.003 | 0.004 | 0.004 | 0.000 |
| sketch.compile.remove_degenerate_lines.initial | 28 | 0.104 | 0.004 | 0.004 | 0.006 | 0.017 | 0.017 | 0.001 |
| sketch.compile.remove_duplicate_lines | 28 | 0.080 | 0.003 | 0.003 | 0.004 | 0.019 | 0.019 | 0.001 |
| sketch.compile.solve_faces | 28 | 29.599 | 1.057 | 0.485 | 3.281 | 3.287 | 3.287 | 1.158 |
| sketch.compile.split_arcs_at_vertices | 7 | 0.005 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 |
| sketch.compile.split_circles_at_vertices | 7 | 0.015 | 0.002 | 0.001 | 0.010 | 0.010 | 0.010 | 0.010 |
| sketch.compile.split_lines_at_vertices | 28 | 0.272 | 0.010 | 0.011 | 0.022 | 0.038 | 0.038 | 0.001 |
| sketch.compile.total | 28 | 33.566 | 1.199 | 0.622 | 3.396 | 3.435 | 3.435 | 1.261 |
| sketch.compile.validation | 28 | 0.515 | 0.018 | 0.017 | 0.034 | 0.038 | 0.038 | 0.018 |
| sketch.face_solver.build_faces | 25 | 16.748 | 0.670 | 0.157 | 2.550 | 2.631 | 2.631 | 0.752 |
| sketch.face_solver.containment | 25 | 1.772 | 0.071 | 0.038 | 0.169 | 0.169 | 0.169 | 0.071 |
| sketch.face_solver.polygonize | 27 | 3.178 | 0.118 | 0.108 | 0.218 | 0.281 | 0.281 | 0.121 |
| sketch.face_solver.source_curves | 28 | 3.752 | 0.134 | 0.108 | 0.269 | 0.594 | 0.594 | 0.140 |
| toolctx.plan2d.actor_visuals.fast_drag | 1 | 0.027 | 0.027 | 0.027 | 0.027 | 0.027 | 0.027 | 0.027 |
| toolctx.plan2d.actor_visuals.full_interaction | 56 | 11.333 | 0.202 | 0.152 | 0.537 | 1.043 | 1.668 | 0.292 |
| toolctx.plan2d.guide_cache.extra.build | 19 | 0.445 | 0.023 | 0.019 | 0.063 | 0.075 | 0.075 | 0.019 |
| toolctx.plan2d.guide_cache.scene.build | 9 | 0.060 | 0.007 | 0.006 | 0.008 | 0.008 | 0.008 | 0.006 |
| toolctx.plan2d.guide_cache.scene.collect_targets | 9 | 0.053 | 0.006 | 0.006 | 0.007 | 0.007 | 0.007 | 0.006 |
| toolctx.plan2d.smart_snap.alignment | 19 | 2.401 | 0.126 | 0.128 | 0.158 | 0.172 | 0.172 | 0.107 |
| toolctx.plan2d.smart_snap.alignment.extra_cache | 19 | 0.753 | 0.040 | 0.035 | 0.078 | 0.091 | 0.091 | 0.034 |
| toolctx.plan2d.smart_snap.alignment.intersection_candidate | 19 | 0.135 | 0.007 | 0.007 | 0.009 | 0.011 | 0.011 | 0.007 |
| toolctx.plan2d.smart_snap.alignment.nearest_axes | 19 | 0.234 | 0.012 | 0.012 | 0.015 | 0.017 | 0.017 | 0.013 |
| toolctx.plan2d.smart_snap.alignment.project | 19 | 0.052 | 0.003 | 0.003 | 0.003 | 0.003 | 0.003 | 0.003 |
| toolctx.plan2d.smart_snap.alignment.radius | 19 | 0.044 | 0.002 | 0.002 | 0.003 | 0.004 | 0.004 | 0.002 |
| toolctx.plan2d.smart_snap.alignment.scene_cache | 19 | 0.482 | 0.025 | 0.014 | 0.041 | 0.045 | 0.045 | 0.012 |
| toolctx.plan2d.smart_snap.manager | 19 | 2.299 | 0.121 | 0.125 | 0.160 | 0.163 | 0.163 | 0.095 |
| toolctx.plan2d.smart_snap.prepare_targets | 19 | 0.006 | 0.000 | 0.000 | 0.000 | 0.001 | 0.001 | 0.000 |
| toolctx.plan2d.smart_snap.total | 19 | 5.311 | 0.280 | 0.285 | 0.351 | 0.355 | 0.355 | 0.222 |
| toolctx.plan_trace.apply.can_apply | 2 | 0.010 | 0.005 | 0.005 | 0.005 | 0.005 | 0.005 | 0.005 |
| toolctx.plan_trace.cursor.actor_sync | 17 | 7.855 | 0.462 | 0.450 | 0.515 | 0.517 | 0.517 | 0.436 |
| toolctx.plan_trace.cursor.constraint | 17 | 0.042 | 0.003 | 0.003 | 0.004 | 0.005 | 0.005 | 0.002 |
| toolctx.plan_trace.cursor.modify_fast_actor_sync | 1 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 | 0.725 |
| toolctx.plan_trace.cursor.modify_local_snap | 1 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 | 0.376 |
| toolctx.plan_trace.cursor.modify_near_targets | 1 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 | 0.335 |
| toolctx.plan_trace.cursor.pending_preview | 17 | 3.904 | 0.230 | 0.044 | 0.491 | 0.787 | 0.787 | 0.371 |
| toolctx.plan_trace.cursor.project | 18 | 0.169 | 0.009 | 0.009 | 0.013 | 0.015 | 0.015 | 0.007 |
| toolctx.plan_trace.cursor.register_cursor | 19 | 7.988 | 0.420 | 0.384 | 0.625 | 0.706 | 0.706 | 0.361 |
| toolctx.plan_trace.cursor.smart_snap | 17 | 5.034 | 0.296 | 0.305 | 0.344 | 0.381 | 0.381 | 0.241 |
| toolctx.plan_trace.cursor.sync_actor_visuals | 19 | 1.683 | 0.089 | 0.034 | 0.056 | 1.073 | 1.073 | 0.035 |
| toolctx.plan_trace.cursor.sync_report | 19 | 0.180 | 0.009 | 0.013 | 0.015 | 0.016 | 0.016 | 0.014 |
| toolctx.plan_trace.cursor.targets | 17 | 4.408 | 0.259 | 0.220 | 0.399 | 0.715 | 0.715 | 0.221 |
| toolctx.plan_trace.cursor.update | 18 | 29.352 | 1.631 | 1.610 | 2.100 | 2.228 | 2.228 | 1.630 |
| toolctx.plan_trace.drag.build_replacements | 1 | 0.019 | 0.019 | 0.019 | 0.019 | 0.019 | 0.019 | 0.019 |
| toolctx.plan_trace.drag.cursor_actor | 1 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 | 1.830 |
| toolctx.plan_trace.drag.project | 1 | 0.008 | 0.008 | 0.008 | 0.008 | 0.008 | 0.008 | 0.008 |
| toolctx.plan_trace.drag.resolve_positions.total | 1 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 | 3.942 |
| toolctx.plan_trace.drag.smart_snap | 1 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 | 0.629 |
| toolctx.plan_trace.drag.sync_moved_points | 1 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 | 1.371 |
| toolctx.plan_trace.draw_press.line | 2 | 4.187 | 2.093 | 1.225 | 2.962 | 2.962 | 2.962 | 2.962 |
| toolctx.plan_trace.draw_press.place_point | 1 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 | 1.469 |
| toolctx.plan_trace.draw_press.record_history | 9 | 0.181 | 0.020 | 0.018 | 0.025 | 0.025 | 0.025 | 0.018 |
| toolctx.plan_trace.draw_press.rectangle | 14 | 63.278 | 4.520 | 1.664 | 7.932 | 12.338 | 12.338 | 7.103 |
| toolctx.plan_trace.draw_press.snapshot | 17 | 0.206 | 0.012 | 0.011 | 0.017 | 0.020 | 0.020 | 0.009 |
| toolctx.plan_trace.draw_press.total | 17 | 108.198 | 6.365 | 3.643 | 11.070 | 15.063 | 15.063 | 5.385 |
| toolctx.plan_trace.event.key_press.total | 1 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 | 1.823 |
| toolctx.plan_trace.event.mouse_move.total | 1 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 | 2.288 |
| toolctx.plan_trace.event.mouse_move.update_cursor | 1 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 | 1.950 |
| toolctx.plan_trace.event.mouse_press.draw_press | 17 | 108.571 | 6.387 | 3.651 | 11.086 | 15.077 | 15.077 | 5.397 |
| toolctx.plan_trace.event.mouse_press.total | 29 | 148.509 | 5.121 | 3.496 | 11.220 | 15.208 | 15.208 | 5.517 |
| toolctx.plan_trace.event.mouse_release.total | 3 | 0.424 | 0.141 | 0.129 | 0.169 | 0.169 | 0.169 | 0.126 |
| toolctx.plan_trace.event.total | 34 | 153.284 | 4.508 | 3.196 | 11.221 | 15.214 | 15.214 | 1.835 |
| toolctx.plan_trace.lifecycle.open | 12 | 45.719 | 3.810 | 3.297 | 5.834 | 9.140 | 9.140 | 2.964 |
| toolctx.plan_trace.lifecycle.open.scene_cache_rebuild | 12 | 1.539 | 0.128 | 0.093 | 0.126 | 0.500 | 0.500 | 0.089 |
| toolctx.plan_trace.modify.selection_api_event | 21 | 0.040 | 0.002 | 0.001 | 0.010 | 0.010 | 0.010 | 0.000 |
| toolctx.plan_trace.motif.union_footprint | 3 | 3.182 | 1.061 | 0.925 | 1.480 | 1.480 | 1.480 | 0.925 |
| toolctx.plan_trace.native.release.total | 3 | 0.010 | 0.003 | 0.004 | 0.004 | 0.004 | 0.004 | 0.003 |
| toolctx.plan_trace.native.select.total | 3 | 4.538 | 1.513 | 1.539 | 1.583 | 1.583 | 1.583 | 1.417 |
| toolctx.plan_trace.render | 57 | 32.615 | 0.572 | 0.424 | 0.919 | 1.103 | 5.395 | 0.332 |
| toolctx.plan_trace.sketch.actor_visual_sync | 12 | 5.349 | 0.446 | 0.485 | 0.587 | 0.591 | 0.591 | 0.494 |
| toolctx.plan_trace.sketch.compile_kernel | 12 | 31.392 | 2.616 | 0.629 | 8.090 | 12.030 | 12.030 | 8.090 |
| toolctx.plan_trace.snap.build_screen_index | 19 | 0.374 | 0.020 | 0.017 | 0.037 | 0.041 | 0.041 | 0.016 |
| toolctx.plan_trace.snap.near_query.cells | 19 | 0.035 | 0.002 | 0.002 | 0.003 | 0.003 | 0.003 | 0.002 |
| toolctx.plan_trace.snap.near_query.materialize | 19 | 0.030 | 0.002 | 0.001 | 0.003 | 0.003 | 0.003 | 0.001 |
| toolctx.plan_trace.snap.near_query.total | 19 | 1.458 | 0.077 | 0.072 | 0.100 | 0.114 | 0.114 | 0.066 |
| toolctx.plan_trace.snap_targets.build.anchor | 19 | 0.889 | 0.047 | 0.022 | 0.065 | 0.486 | 0.486 | 0.010 |
| toolctx.plan_trace.snap_targets.build.arcs | 19 | 0.011 | 0.001 | 0.001 | 0.001 | 0.002 | 0.002 | 0.001 |
| toolctx.plan_trace.snap_targets.build.beziers | 19 | 0.008 | 0.000 | 0.000 | 0.001 | 0.001 | 0.001 | 0.000 |
| toolctx.plan_trace.snap_targets.build.circles | 19 | 0.009 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | 0.000 |
| toolctx.plan_trace.snap_targets.build.lines | 19 | 0.084 | 0.004 | 0.001 | 0.034 | 0.040 | 0.040 | 0.001 |
| toolctx.plan_trace.snap_targets.build.points | 19 | 0.249 | 0.013 | 0.015 | 0.043 | 0.044 | 0.044 | 0.017 |
| toolctx.plan_trace.snap_targets.build_live_targets | 19 | 2.271 | 0.119 | 0.078 | 0.205 | 0.567 | 0.567 | 0.074 |
| toolctx.plan_trace.snap_targets.fast_signature | 20 | 0.042 | 0.002 | 0.002 | 0.003 | 0.004 | 0.004 | 0.002 |
| toolctx.plan_trace.snap_targets.structural_signature | 19 | 0.239 | 0.013 | 0.012 | 0.015 | 0.016 | 0.016 | 0.011 |
| toolctx.plan_trace.surface.pick_press | 12 | 36.521 | 3.043 | 2.730 | 4.036 | 4.060 | 4.060 | 4.060 |
| toolctx.scene_cache.mesh.collect_objects | 12 | 0.204 | 0.017 | 0.020 | 0.025 | 0.028 | 0.028 | 0.010 |
| toolctx.scene_cache.rebuild.collect_document_meshes | 12 | 0.376 | 0.031 | 0.031 | 0.036 | 0.043 | 0.043 | 0.029 |
| toolctx.scene_cache.rebuild.collect_scene | 12 | 0.031 | 0.003 | 0.003 | 0.003 | 0.004 | 0.004 | 0.003 |
| toolctx.scene_cache.rebuild.collect_selection | 12 | 0.026 | 0.002 | 0.002 | 0.003 | 0.003 | 0.003 | 0.002 |
| toolctx.scene_cache.rebuild.collect_sketch | 12 | 0.047 | 0.004 | 0.004 | 0.005 | 0.005 | 0.005 | 0.004 |
| toolctx.scene_cache.rebuild.total | 12 | 1.028 | 0.086 | 0.084 | 0.096 | 0.116 | 0.116 | 0.081 |
| toolctx.scene_cache.snap.near_query.total | 19 | 0.496 | 0.026 | 0.015 | 0.041 | 0.048 | 0.048 | 0.014 |
| toolctx.scene_cache.snap.rebuild_screen_index | 9 | 0.042 | 0.005 | 0.005 | 0.005 | 0.005 | 0.005 | 0.005 |
| toolctx.snap.manager.providers | 19 | 0.007 | 0.000 | 0.000 | 0.001 | 0.001 | 0.001 | 0.001 |
| toolctx.snap.manager.targets_to_results | 19 | 0.755 | 0.040 | 0.036 | 0.042 | 0.098 | 0.098 | 0.034 |
| toolctx.snap.targets_to_results.classify | 19 | 0.020 | 0.001 | 0.000 | 0.001 | 0.013 | 0.013 | 0.000 |
| toolctx.snap.targets_to_results.curve_intersections | 19 | 0.021 | 0.001 | 0.001 | 0.001 | 0.002 | 0.002 | 0.001 |
| toolctx.snap.targets_to_results.direct_snaps | 19 | 0.048 | 0.003 | 0.000 | 0.005 | 0.038 | 0.038 | 0.000 |
| toolctx.snap.targets_to_results.segment_intersections | 19 | 0.026 | 0.001 | 0.001 | 0.001 | 0.010 | 0.010 | 0.001 |
| toolctx.snap.targets_to_results.total | 19 | 0.645 | 0.034 | 0.030 | 0.036 | 0.091 | 0.091 | 0.029 |

## Counters
| Counter | Value |
| --- | --- |
| render.full_request | 70 |
| render.performed | 70 |
| toolctx.document.bind.changed_target | 12 |
| toolctx.document.bind.same_target | 7 |
| toolctx.plan2d.actor_visuals.dirty_bridge | 132 |
| toolctx.plan2d.actor_visuals.fast_drag.calls | 1 |
| toolctx.plan2d.actor_visuals.full_interaction.calls | 56 |
| toolctx.plan2d.guide_cache.extra.misses | 19 |
| toolctx.plan2d.guide_cache.scene.hits | 10 |
| toolctx.plan2d.guide_cache.scene.misses | 9 |
| toolctx.plan2d.guide_cache.scene.object_scope.filtered | 0 |
| toolctx.plan2d.smart_snap.alignment_candidates | 7 |
| toolctx.plan2d.smart_snap.alignment_hits | 3 |
| toolctx.plan2d.smart_snap.alignment_targets | 38 |
| toolctx.plan2d.smart_snap.calls | 19 |
| toolctx.plan2d.smart_snap.extra_targets | 8 |
| toolctx.plan2d.smart_snap.grid.local_hits | 16 |
| toolctx.plan2d.smart_snap.grid.manager_ignored | 19 |
| toolctx.plan_trace.apply.can_apply.fast_path | 2 |
| toolctx.plan_trace.cursor.align_targets | 25 |
| toolctx.plan_trace.cursor.modify_fast_path | 1 |
| toolctx.plan_trace.cursor.modify_near_target_count | 7 |
| toolctx.plan_trace.cursor.moves | 18 |
| toolctx.plan_trace.cursor.near_targets | 0 |
| toolctx.plan_trace.drag.movable_points | 1 |
| toolctx.plan_trace.draw_press.tool.line | 2 |
| toolctx.plan_trace.draw_press.tool.point | 1 |
| toolctx.plan_trace.draw_press.tool.rectangle | 14 |
| toolctx.plan_trace.event.key_press | 1 |
| toolctx.plan_trace.event.mouse_move | 1 |
| toolctx.plan_trace.event.mouse_press | 29 |
| toolctx.plan_trace.event.mouse_release | 3 |
| toolctx.plan_trace.event.mouse_release.modify_no_compile | 3 |
| toolctx.plan_trace.motif.union_footprint.cache_misses | 3 |
| toolctx.plan_trace.native.release | 3 |
| toolctx.plan_trace.native.select | 3 |
| toolctx.plan_trace.sketch.changed_actors | 85 |
| toolctx.plan_trace.sketch.compile_cache_misses | 12 |
| toolctx.plan_trace.snap.index_cells | 92 |
| toolctx.plan_trace.snap.index_fallback_targets | 0 |
| toolctx.plan_trace.snap.index_targets | 43 |
| toolctx.plan_trace.snap.near_fallback_targets | 0 |
| toolctx.plan_trace.snap.near_index_candidates | 11 |
| toolctx.plan_trace.snap.near_queries | 19 |
| toolctx.plan_trace.snap.near_targets | 11 |
| toolctx.plan_trace.snap.rebuild_reason.initial | 19 |
| toolctx.plan_trace.snap.screen_index_misses | 19 |
| toolctx.plan_trace.snap_targets.fast_signature_hits | 1 |
| toolctx.plan_trace.snap_targets.fast_signature_misses | 19 |
| toolctx.plan_trace.snap_targets.rebuilds | 19 |
| toolctx.plan_trace.snap_targets.structural_signature_misses | 19 |
| toolctx.render.full | 70 |
| toolctx.scene_cache.rebuild.calls | 12 |
| toolctx.scene_cache.snap.index_cells | 0 |
| toolctx.scene_cache.snap.index_fallback | 0 |
| toolctx.scene_cache.snap.index_targets | 0 |
| toolctx.scene_cache.snap.rebuild_reason.initial | 9 |
| toolctx.scene_cache.snap.screen_index_hits | 10 |
| toolctx.scene_cache.snap.screen_index_misses | 9 |
| toolctx.snap.manager.filtered_candidates | 0 |
| toolctx.snap.manager.object_scope.filtered_scene_targets | 0 |
| toolctx.snap.manager.queries | 19 |
| toolctx.snap.manager.raw_candidates | 0 |
| toolctx.snap.manager.target_pool | 8 |
| toolctx.snap.targets_to_results.arcs | 0 |
| toolctx.snap.targets_to_results.circles | 0 |
| toolctx.snap.targets_to_results.results | 0 |
| toolctx.snap.targets_to_results.segments | 3 |
| toolctx.snap.targets_to_results.targets | 8 |
| toolctx.tool.cleanup | 12 |

## Last values / gauges
| Value | Last |
| --- | --- |
| toolctx.plan2d.actor_visuals.changed_last | 1 |
| toolctx.plan2d.actor_visuals.dirty_bridge_handles_last | 1 |
| toolctx.plan2d.actor_visuals.dirty_bridge_previews_last | 0 |
| toolctx.plan2d.actor_visuals.position_only_last | 0 |
| toolctx.plan2d.guide_cache.extra.points | 2 |
| toolctx.plan2d.guide_cache.extra.targets | 2 |
| toolctx.plan2d.guide_cache.scene.points | 0 |
| toolctx.plan2d.guide_cache.scene.targets | 0 |
| toolctx.plan2d.smart_snap.grid.distance_px | 0.000 |
| toolctx.plan2d.smart_snap.last_alignment_candidates | 1 |
| toolctx.plan_trace.diagnostic.enabled | 1 |
| toolctx.plan_trace.motif.union_footprint.cache_size | 1 |
| toolctx.plan_trace.motif.union_footprint.face_count | 1 |
| toolctx.plan_trace.snap.last_near_index_candidates | 0 |
| toolctx.plan_trace.snap.last_near_targets | 0 |
| toolctx.plan_trace.snap_targets.anchors | 1 |
| toolctx.plan_trace.snap_targets.arc_segments | 0 |
| toolctx.plan_trace.snap_targets.arcs | 0 |
| toolctx.plan_trace.snap_targets.bezier_segments | 0 |
| toolctx.plan_trace.snap_targets.beziers | 0 |
| toolctx.plan_trace.snap_targets.cached_total | 9 |
| toolctx.plan_trace.snap_targets.circles | 0 |
| toolctx.plan_trace.snap_targets.lines | 0 |
| toolctx.plan_trace.snap_targets.points | 1 |
| toolctx.plan_trace.snap_targets.total | 2 |
| toolctx.scene_cache.bounds | 0 |
| toolctx.scene_cache.extra_targets | 0 |
| toolctx.scene_cache.mesh.objects | 1 |
| toolctx.scene_cache.mesh.remaining_edge_budget | 3000 |
| toolctx.scene_cache.mesh.remaining_point_budget | 1200 |
| toolctx.scene_cache.mesh.sampled_unique_edges | 0 |
| toolctx.scene_cache.mesh.sampled_unique_points | 0 |
| toolctx.scene_cache.points | 0 |
| toolctx.scene_cache.segments | 0 |
| toolctx.scene_cache.snap.index_cells | 0 |
| toolctx.scene_cache.snap.index_fallback | 0 |
| toolctx.scene_cache.snap.index_targets | 0 |
| toolctx.scene_cache.snap.projection.has_camera | 0 |
| toolctx.scene_cache.snap.projection.has_owner_plotter | 0 |
| toolctx.scene_cache.snap.projection.has_viewport_plotter | 0 |
| toolctx.scene_cache.snap.projection_signature_changed | 0 |
| toolctx.scene_cache.snap.rebuild_reason.last | hit |
| toolctx.scene_cache.snap.structure_signature_changed | 0 |
| toolctx.scene_cache.version | 2 |
| toolctx.snap.manager.object_scope.scene_targets | 0 |

## Slow events
| At s | Name | Elapsed ms | Details |
| --- | --- | --- | --- |
| 1.347 | plan_trace.apply.mesh.boolean_ready_extrusion | 23.054 |  |
| 1.245 | plan_trace.apply.mesh.boolean_ready_extrusion | 30.796 |  |

## Timeline tail
| At s | Name | Elapsed ms | Details |
| --- | --- | --- | --- |
| 1.347 | plan_trace.apply.mesh.boolean_ready_extrusion | 23.054 |  |
| 1.314 | toolctx.plan_trace.motif.union_footprint | 0.925 |  |
| 1.279 | toolctx.plan_trace.motif.union_footprint | 1.480 |  |
| 1.245 | plan_trace.apply.mesh.boolean_ready_extrusion | 30.796 |  |
| 1.206 | toolctx.plan_trace.motif.union_footprint | 0.777 |  |
| 1.193 | toolctx.plan_trace.event.key_press.total | 1.823 |  |
| 1.191 | toolctx.plan_trace.draw_press.line | 2.962 |  |
| 1.186 | toolctx.plan_trace.draw_press.line | 1.225 |  |
| 1.173 | toolctx.plan_trace.drag.resolve_positions.total | 3.942 |  |
| 1.173 | toolctx.plan_trace.drag.cursor_actor | 1.830 |  |
| 1.171 | toolctx.plan_trace.drag.sync_moved_points | 1.371 |  |
| 1.171 | toolctx.plan2d.actor_visuals.fast_drag | 0.027 | {'changed': 2, 'render': False, 'projected': True} |
| 1.170 | toolctx.plan_trace.drag.build_replacements | 0.019 |  |
| 1.170 | toolctx.plan_trace.drag.smart_snap | 0.629 |  |
| 1.169 | toolctx.plan_trace.drag.project | 0.008 |  |
| 1.124 | toolctx.plan_trace.draw_press.place_point | 1.469 |  |
| 1.111 | toolctx.plan_trace.apply.can_apply | 0.005 |  |
| 1.108 | toolctx.plan_trace.apply.can_apply | 0.005 |  |
| 1.077 | toolctx.plan_trace.event.mouse_release.total | 0.126 |  |
| 1.077 | toolctx.plan_trace.native.release.total | 0.003 |  |
| 1.077 | toolctx.plan_trace.native.select.total | 1.417 |  |
| 1.048 | toolctx.plan_trace.event.mouse_release.total | 0.169 |  |
| 1.048 | toolctx.plan_trace.native.release.total | 0.004 |  |
| 1.048 | toolctx.plan_trace.native.select.total | 1.583 |  |
| 1.040 | toolctx.plan_trace.sketch.actor_visual_sync | 0.495 |  |
| 1.030 | toolctx.plan_trace.sketch.compile_kernel | 0.607 |  |
| 1.027 | toolctx.plan_trace.draw_press.record_history | 0.025 |  |
| 1.024 | toolctx.plan2d.guide_cache.scene.build | 0.008 |  |
| 1.024 | toolctx.plan2d.guide_cache.scene.collect_targets | 0.006 |  |
| 1.024 | toolctx.scene_cache.snap.rebuild_screen_index | 0.005 |  |
| 0.980 | toolctx.plan_trace.surface.pick_press | 2.523 |  |
| 0.977 | toolctx.plan_trace.lifecycle.open | 3.067 |  |
| 0.975 | toolctx.plan_trace.lifecycle.open.scene_cache_rebuild | 0.097 |  |
| 0.975 | toolctx.scene_cache.rebuild.total | 0.089 |  |
| 0.975 | toolctx.scene_cache.rebuild.collect_document_meshes | 0.033 |  |
| 0.975 | toolctx.scene_cache.mesh.collect_objects | 0.022 |  |
| 0.975 | toolctx.scene_cache.rebuild.collect_scene | 0.003 |  |
| 0.975 | toolctx.scene_cache.rebuild.collect_selection | 0.002 |  |
| 0.975 | toolctx.scene_cache.rebuild.collect_sketch | 0.004 |  |
| 0.972 | sketch.compile.split_circles_at_vertices | 0.001 |  |
| 0.972 | sketch.compile.split_arcs_at_vertices | 0.001 |  |
| 0.972 | sketch.compile.insert_curve_intersections | 0.004 |  |
| 0.502 | plan_trace.apply.mesh.boolean_ready_extrusion | 0.784 |  |
| 0.501 | sketch.compile.split_circles_at_vertices | 0.001 |  |
| 0.501 | sketch.compile.split_arcs_at_vertices | 0.001 |  |
| 0.501 | sketch.compile.insert_curve_intersections | 0.005 |  |
| 0.498 | sketch.compile.split_circles_at_vertices | 0.001 |  |
| 0.498 | sketch.compile.split_arcs_at_vertices | 0.001 |  |
| 0.498 | sketch.compile.insert_curve_intersections | 0.005 |  |
| 0.495 | toolctx.plan_trace.event.mouse_release.total | 0.129 |  |
| 0.495 | toolctx.plan_trace.native.release.total | 0.004 |  |
| 0.495 | toolctx.plan_trace.native.select.total | 1.539 |  |
| 0.486 | toolctx.plan_trace.sketch.actor_visual_sync | 0.465 |  |
| 0.482 | toolctx.plan_trace.sketch.compile_kernel | 0.669 |  |
| 0.480 | toolctx.plan_trace.event.mouse_press.draw_press | 2.892 |  |
| 0.480 | toolctx.plan_trace.draw_press.total | 2.884 |  |
| 0.480 | toolctx.plan_trace.draw_press.record_history | 0.023 |  |
| 0.480 | toolctx.plan_trace.draw_press.rectangle | 1.165 |  |
| 0.478 | toolctx.plan_trace.draw_press.snapshot | 0.014 |  |
| 0.478 | toolctx.plan_trace.cursor.actor_sync | 0.433 |  |
| 0.478 | toolctx.plan_trace.cursor.pending_preview | 0.024 |  |
| 0.478 | toolctx.plan_trace.cursor.constraint | 0.003 |  |
| 0.478 | toolctx.plan_trace.cursor.smart_snap | 0.329 |  |
| 0.477 | toolctx.plan2d.guide_cache.scene.build | 0.006 |  |
| 0.477 | toolctx.plan2d.guide_cache.scene.collect_targets | 0.007 |  |
| 0.477 | toolctx.scene_cache.snap.rebuild_screen_index | 0.005 |  |
| 0.477 | toolctx.plan_trace.cursor.targets | 0.220 |  |
| 0.475 | toolctx.plan_trace.surface.pick_press | 2.513 |  |
| 0.472 | toolctx.plan_trace.lifecycle.open | 3.297 |  |
| 0.470 | toolctx.plan_trace.lifecycle.open.scene_cache_rebuild | 0.088 |  |
| 0.470 | toolctx.scene_cache.rebuild.total | 0.082 |  |
| 0.470 | toolctx.scene_cache.rebuild.collect_document_meshes | 0.030 |  |
| 0.470 | toolctx.scene_cache.mesh.collect_objects | 0.021 |  |
| 0.470 | toolctx.scene_cache.rebuild.collect_scene | 0.003 |  |
| 0.470 | toolctx.scene_cache.rebuild.collect_selection | 0.003 |  |
| 0.470 | toolctx.scene_cache.rebuild.collect_sketch | 0.004 |  |
| 0.468 | toolctx.plan_trace.event.mouse_move.total | 2.288 |  |
| 0.468 | toolctx.plan_trace.event.mouse_move.update_cursor | 1.950 |  |
| 0.468 | toolctx.plan_trace.cursor.update | 1.628 |  |
| 0.468 | toolctx.plan_trace.cursor.modify_fast_actor_sync | 0.725 |  |
| 0.468 | toolctx.plan_trace.cursor.sync_report | 0.013 |  |
| 0.468 | toolctx.plan_trace.cursor.sync_actor_visuals | 0.056 |  |
| 0.468 | toolctx.plan_trace.cursor.register_cursor | 0.625 |  |
| 0.467 | toolctx.plan_trace.cursor.modify_local_snap | 0.376 |  |
| 0.467 | toolctx.plan2d.smart_snap.total | 0.355 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment | 0.172 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment.intersection_candidate | 0.008 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment.nearest_axes | 0.013 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment.radius | 0.003 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment.extra_cache | 0.091 |  |
| 0.467 | toolctx.plan2d.guide_cache.extra.build | 0.075 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment.scene_cache | 0.013 |  |
| 0.467 | toolctx.plan2d.smart_snap.alignment.project | 0.003 |  |
| 0.467 | toolctx.plan2d.smart_snap.manager | 0.163 |  |
| 0.467 | toolctx.snap.manager.targets_to_results | 0.098 |  |
| 0.467 | toolctx.snap.targets_to_results.total | 0.091 |  |
| 0.467 | toolctx.snap.targets_to_results.direct_snaps | 0.038 |  |
| 0.467 | toolctx.snap.targets_to_results.curve_intersections | 0.001 |  |
| 0.467 | toolctx.snap.targets_to_results.segment_intersections | 0.010 |  |
| 0.467 | toolctx.snap.targets_to_results.classify | 0.013 |  |
| 0.467 | toolctx.scene_cache.snap.near_query.total | 0.014 |  |
| 0.467 | toolctx.snap.manager.providers | 0.000 |  |
| 0.467 | toolctx.plan2d.smart_snap.prepare_targets | 0.000 |  |
| 0.467 | toolctx.plan_trace.cursor.modify_near_targets | 0.335 |  |
| 0.467 | toolctx.plan_trace.snap.near_query.total | 0.100 |  |
| 0.467 | toolctx.plan_trace.snap.near_query.materialize | 0.003 |  |
| 0.467 | toolctx.plan_trace.snap.near_query.cells | 0.003 |  |
| 0.466 | toolctx.plan_trace.snap.build_screen_index | 0.041 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build_live_targets | 0.143 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build.anchor | 0.010 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build.circles | 0.000 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build.beziers | 0.000 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build.arcs | 0.001 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build.lines | 0.040 |  |
| 0.466 | toolctx.plan_trace.snap_targets.build.points | 0.044 |  |
| 0.466 | toolctx.plan_trace.snap_targets.structural_signature | 0.016 |  |
| 0.466 | toolctx.plan_trace.snap_targets.fast_signature | 0.002 |  |
| 0.466 | toolctx.plan_trace.cursor.project | 0.009 |  |
| 0.466 | toolctx.plan_trace.modify.selection_api_event | 0.010 |  |
| 0.463 | toolctx.plan_trace.event.total | 11.228 |  |
| 0.463 | toolctx.plan_trace.event.mouse_press.total | 11.220 |  |
| 0.463 | toolctx.plan_trace.event.mouse_press.draw_press | 11.084 |  |
| 0.463 | toolctx.plan_trace.draw_press.total | 10.884 |  |
| 0.462 | toolctx.plan_trace.draw_press.rectangle | 7.932 |  |
| 0.460 | toolctx.plan_trace.sketch.actor_visual_sync | 0.591 |  |
| 0.455 | toolctx.plan_trace.sketch.compile_kernel | 0.629 |  |
| 0.454 | toolctx.plan_trace.draw_press.snapshot | 0.009 |  |
| 0.454 | toolctx.plan_trace.cursor.update | 1.855 |  |
| 0.454 | toolctx.plan_trace.cursor.actor_sync | 0.515 |  |
| 0.454 | toolctx.plan_trace.cursor.sync_report | 0.003 |  |
| 0.454 | toolctx.plan_trace.cursor.sync_actor_visuals | 0.039 |  |
| 0.453 | toolctx.plan_trace.cursor.register_cursor | 0.443 |  |
| 0.453 | toolctx.plan_trace.cursor.pending_preview | 0.491 |  |
| 0.453 | toolctx.plan_trace.cursor.constraint | 0.003 |  |
| 0.452 | toolctx.plan_trace.cursor.smart_snap | 0.256 |  |
| 0.452 | toolctx.plan2d.smart_snap.total | 0.237 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment | 0.107 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment.intersection_candidate | 0.007 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment.nearest_axes | 0.010 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment.radius | 0.002 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment.extra_cache | 0.037 |  |
| 0.452 | toolctx.plan2d.guide_cache.extra.build | 0.021 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment.scene_cache | 0.013 |  |
| 0.452 | toolctx.plan2d.smart_snap.alignment.project | 0.003 |  |
| 0.452 | toolctx.plan2d.smart_snap.manager | 0.099 |  |
| 0.452 | toolctx.snap.manager.targets_to_results | 0.034 |  |
| 0.452 | toolctx.snap.targets_to_results.total | 0.029 |  |
| 0.452 | toolctx.snap.targets_to_results.direct_snaps | 0.000 |  |
| 0.452 | toolctx.snap.targets_to_results.curve_intersections | 0.001 |  |
| 0.452 | toolctx.snap.targets_to_results.segment_intersections | 0.001 |  |
| 0.452 | toolctx.snap.targets_to_results.classify | 0.000 |  |
| 0.452 | toolctx.scene_cache.snap.near_query.total | 0.015 |  |
| 0.452 | toolctx.snap.manager.providers | 0.000 |  |
| 0.452 | toolctx.plan2d.smart_snap.prepare_targets | 0.001 |  |
| 0.452 | toolctx.plan_trace.cursor.targets | 0.213 |  |
| 0.452 | toolctx.plan_trace.snap.near_query.total | 0.070 |  |
| 0.452 | toolctx.plan_trace.snap.near_query.materialize | 0.001 |  |
| 0.452 | toolctx.plan_trace.snap.near_query.cells | 0.002 |  |
| 0.452 | toolctx.plan_trace.snap.build_screen_index | 0.019 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build_live_targets | 0.080 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build.anchor | 0.012 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build.circles | 0.000 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build.beziers | 0.000 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build.arcs | 0.001 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build.lines | 0.001 |  |
| 0.452 | toolctx.plan_trace.snap_targets.build.points | 0.020 |  |
| 0.452 | toolctx.plan_trace.snap_targets.structural_signature | 0.014 |  |
| 0.452 | toolctx.plan_trace.snap_targets.fast_signature | 0.003 |  |
| 0.452 | toolctx.plan_trace.cursor.project | 0.008 |  |
| 0.452 | toolctx.plan_trace.modify.selection_api_event | 0.001 |  |
| 0.452 | toolctx.plan_trace.event.total | 3.606 |  |
| 0.452 | toolctx.plan_trace.event.mouse_press.total | 3.599 |  |
| 0.452 | toolctx.plan_trace.event.mouse_press.draw_press | 3.476 |  |
| 0.452 | toolctx.plan_trace.draw_press.total | 3.467 |  |
| 0.452 | toolctx.plan_trace.draw_press.record_history | 0.022 |  |
| 0.452 | toolctx.plan_trace.draw_press.rectangle | 1.369 |  |
| 0.451 | toolctx.plan2d.actor_visuals.full_interaction | 0.006 | {'changed': 1, 'render': True, 'projected': True} |
| 0.450 | toolctx.plan_trace.draw_press.snapshot | 0.020 |  |
| 0.450 | toolctx.plan_trace.cursor.update | 1.755 |  |
| 0.450 | toolctx.plan_trace.cursor.actor_sync | 0.514 |  |
| 0.450 | toolctx.plan_trace.cursor.sync_report | 0.014 |  |
| 0.450 | toolctx.plan_trace.cursor.sync_actor_visuals | 0.033 |  |
| 0.450 | toolctx.plan2d.actor_visuals.full_interaction | 0.008 | {'changed': 0, 'render': False, 'projected': True} |
| 0.450 | toolctx.plan_trace.cursor.register_cursor | 0.437 |  |
| 0.449 | toolctx.plan_trace.cursor.pending_preview | 0.031 |  |
| 0.449 | toolctx.plan_trace.cursor.constraint | 0.004 |  |
| 0.449 | toolctx.plan_trace.cursor.smart_snap | 0.381 |  |
| 0.449 | toolctx.plan2d.smart_snap.total | 0.351 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment | 0.153 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment.intersection_candidate | 0.011 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment.nearest_axes | 0.017 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment.radius | 0.003 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment.extra_cache | 0.037 |  |
| 0.449 | toolctx.plan2d.guide_cache.extra.build | 0.019 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment.scene_cache | 0.045 |  |
| 0.449 | toolctx.plan2d.guide_cache.scene.build | 0.008 |  |
| 0.449 | toolctx.plan2d.guide_cache.scene.collect_targets | 0.007 |  |
| 0.449 | toolctx.plan2d.smart_snap.alignment.project | 0.003 |  |
| 0.449 | toolctx.plan2d.smart_snap.manager | 0.160 |  |
| 0.449 | toolctx.snap.manager.targets_to_results | 0.042 |  |

## Raw JSON

```json
{
  "counters": {
    "render.full_request": 70,
    "render.performed": 70,
    "toolctx.document.bind.changed_target": 12,
    "toolctx.document.bind.same_target": 7,
    "toolctx.plan2d.actor_visuals.dirty_bridge": 132,
    "toolctx.plan2d.actor_visuals.fast_drag.calls": 1,
    "toolctx.plan2d.actor_visuals.full_interaction.calls": 56,
    "toolctx.plan2d.guide_cache.extra.misses": 19,
    "toolctx.plan2d.guide_cache.scene.hits": 10,
    "toolctx.plan2d.guide_cache.scene.misses": 9,
    "toolctx.plan2d.guide_cache.scene.object_scope.filtered": 0,
    "toolctx.plan2d.smart_snap.alignment_candidates": 7,
    "toolctx.plan2d.smart_snap.alignment_hits": 3,
    "toolctx.plan2d.smart_snap.alignment_targets": 38,
    "toolctx.plan2d.smart_snap.calls": 19,
    "toolctx.plan2d.smart_snap.extra_targets": 8,
    "toolctx.plan2d.smart_snap.grid.local_hits": 16,
    "toolctx.plan2d.smart_snap.grid.manager_ignored": 19,
    "toolctx.plan_trace.apply.can_apply.fast_path": 2,
    "toolctx.plan_trace.cursor.align_targets": 25,
    "toolctx.plan_trace.cursor.modify_fast_path": 1,
    "toolctx.plan_trace.cursor.modify_near_target_count": 7,
    "toolctx.plan_trace.cursor.moves": 18,
    "toolctx.plan_trace.cursor.near_targets": 0,
    "toolctx.plan_trace.drag.movable_points": 1,
    "toolctx.plan_trace.draw_press.tool.line": 2,
    "toolctx.plan_trace.draw_press.tool.point": 1,
    "toolctx.plan_trace.draw_press.tool.rectangle": 14,
    "toolctx.plan_trace.event.key_press": 1,
    "toolctx.plan_trace.event.mouse_move": 1,
    "toolctx.plan_trace.event.mouse_press": 29,
    "toolctx.plan_trace.event.mouse_release": 3,
    "toolctx.plan_trace.event.mouse_release.modify_no_compile": 3,
    "toolctx.plan_trace.motif.union_footprint.cache_misses": 3,
    "toolctx.plan_trace.native.release": 3,
    "toolctx.plan_trace.native.select": 3,
    "toolctx.plan_trace.sketch.changed_actors": 85,
    "toolctx.plan_trace.sketch.compile_cache_misses": 12,
    "toolctx.plan_trace.snap.index_cells": 92,
    "toolctx.plan_trace.snap.index_fallback_targets": 0,
    "toolctx.plan_trace.snap.index_targets": 43,
    "toolctx.plan_trace.snap.near_fallback_targets": 0,
    "toolctx.plan_trace.snap.near_index_candidates": 11,
    "toolctx.plan_trace.snap.near_queries": 19,
    "toolctx.plan_trace.snap.near_targets": 11,
    "toolctx.plan_trace.snap.rebuild_reason.initial": 19,
    "toolctx.plan_trace.snap.screen_index_misses": 19,
    "toolctx.plan_trace.snap_targets.fast_signature_hits": 1,
    "toolctx.plan_trace.snap_targets.fast_signature_misses": 19,
    "toolctx.plan_trace.snap_targets.rebuilds": 19,
    "toolctx.plan_trace.snap_targets.structural_signature_misses": 19,
    "toolctx.render.full": 70,
    "toolctx.scene_cache.rebuild.calls": 12,
    "toolctx.scene_cache.snap.index_cells": 0,
    "toolctx.scene_cache.snap.index_fallback": 0,
    "toolctx.scene_cache.snap.index_targets": 0,
    "toolctx.scene_cache.snap.rebuild_reason.initial": 9,
    "toolctx.scene_cache.snap.screen_index_hits": 10,
    "toolctx.scene_cache.snap.screen_index_misses": 9,
    "toolctx.snap.manager.filtered_candidates": 0,
    "toolctx.snap.manager.object_scope.filtered_scene_targets": 0,
    "toolctx.snap.manager.queries": 19,
    "toolctx.snap.manager.raw_candidates": 0,
    "toolctx.snap.manager.target_pool": 8,
    "toolctx.snap.targets_to_results.arcs": 0,
    "toolctx.snap.targets_to_results.circles": 0,
    "toolctx.snap.targets_to_results.results": 0,
    "toolctx.snap.targets_to_results.segments": 3,
    "toolctx.snap.targets_to_results.targets": 8,
    "toolctx.tool.cleanup": 12
  },
  "metadata": {
    "cwd": "/mnt/data/LaserProg_v179_PlanTracerPerformanceSafety",
    "elapsed_session_s": 1.83,
    "generated_at": "2026-08-21 08:44:31",
    "last_export_path": null,
    "platform": "Linux-6.18.35-x86_64-with-glibc2.41",
    "process_id": 4079,
    "python": "3.13.5",
    "slow_threshold_ms": 16.0
  },
  "slow_events": [
    {
      "at_s": 1.245,
      "elapsed_ms": 30.796,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    },
    {
      "at_s": 1.347,
      "elapsed_ms": 23.0537,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    }
  ],
  "timeline_tail": [
    {
      "at_s": 0.393,
      "elapsed_ms": 0.0295,
      "name": "sketch.compile.merge_duplicate_points"
    },
    {
      "at_s": 0.393,
      "elapsed_ms": 0.017,
      "name": "sketch.compile.remove_degenerate_lines.initial"
    },
    {
      "at_s": 0.394,
      "elapsed_ms": 0.0497,
      "name": "sketch.compile.insert_line_intersections"
    },
    {
      "at_s": 0.394,
      "elapsed_ms": 0.0219,
      "name": "sketch.compile.split_lines_at_vertices"
    },
    {
      "at_s": 0.394,
      "elapsed_ms": 0.0037,
      "name": "sketch.compile.remove_degenerate_lines.final"
    },
    {
      "at_s": 0.394,
      "elapsed_ms": 0.0025,
      "name": "sketch.compile.remove_degenerate_curves"
    },
    {
      "at_s": 0.394,
      "elapsed_ms": 0.0188,
      "name": "sketch.compile.remove_duplicate_lines"
    },
    {
      "at_s": 0.394,
      "elapsed_ms": 0.0322,
      "name": "sketch.compile.rebuild_polylines"
    },
    {
      "at_s": 0.396,
      "elapsed_ms": 0.1744,
      "name": "sketch.face_solver.source_curves"
    },
    {
      "at_s": 0.396,
      "elapsed_ms": 0.1992,
      "name": "sketch.face_solver.polygonize"
    },
    {
      "at_s": 0.396,
      "elapsed_ms": 0.2779,
      "name": "sketch.face_solver.build_faces"
    },
    {
      "at_s": 0.397,
      "elapsed_ms": 0.0725,
      "name": "sketch.face_solver.containment"
    },
    {
      "at_s": 0.397,
      "elapsed_ms": 2.9107,
      "name": "sketch.compile.solve_faces"
    },
    {
      "at_s": 0.397,
      "elapsed_ms": 0.0283,
      "name": "sketch.compile.validation"
    },
    {
      "at_s": 0.397,
      "elapsed_ms": 3.2285,
      "name": "sketch.compile.total"
    },
    {
      "at_s": 0.4,
      "elapsed_ms": 0.8692,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.019,
      "name": "sketch.compile.merge_duplicate_points"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0049,
      "name": "sketch.compile.remove_degenerate_lines.initial"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0202,
      "name": "sketch.compile.insert_line_intersections"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0153,
      "name": "sketch.compile.split_lines_at_vertices"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0029,
      "name": "sketch.compile.remove_degenerate_lines.final"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0017,
      "name": "sketch.compile.remove_degenerate_curves"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0035,
      "name": "sketch.compile.remove_duplicate_lines"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.02,
      "name": "sketch.compile.rebuild_polylines"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0851,
      "name": "sketch.face_solver.source_curves"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.0836,
      "name": "sketch.face_solver.polygonize"
    },
    {
      "at_s": 0.401,
      "elapsed_ms": 0.1656,
      "name": "sketch.face_solver.build_faces"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0943,
      "name": "sketch.face_solver.containment"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.508,
      "name": "sketch.compile.solve_faces"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0172,
      "name": "sketch.compile.validation"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.6722,
      "name": "sketch.compile.total"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0154,
      "name": "sketch.compile.merge_duplicate_points"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.003,
      "name": "sketch.compile.remove_degenerate_lines.initial"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0155,
      "name": "sketch.compile.insert_line_intersections"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.012,
      "name": "sketch.compile.split_lines_at_vertices"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0024,
      "name": "sketch.compile.remove_degenerate_lines.final"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0009,
      "name": "sketch.compile.remove_degenerate_curves"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0029,
      "name": "sketch.compile.remove_duplicate_lines"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0197,
      "name": "sketch.compile.rebuild_polylines"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0562,
      "name": "sketch.face_solver.source_curves"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0553,
      "name": "sketch.face_solver.polygonize"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0841,
      "name": "sketch.face_solver.build_faces"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0304,
      "name": "sketch.face_solver.containment"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.2769,
      "name": "sketch.compile.solve_faces"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.0098,
      "name": "sketch.compile.validation"
    },
    {
      "at_s": 0.402,
      "elapsed_ms": 0.3981,
      "name": "sketch.compile.total"
    },
    {
      "at_s": 0.403,
      "elapsed_ms": 0.6349,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.0052,
      "name": "toolctx.scene_cache.rebuild.collect_sketch"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.0029,
      "name": "toolctx.scene_cache.rebuild.collect_selection"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.0037,
      "name": "toolctx.scene_cache.rebuild.collect_scene"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.0284,
      "name": "toolctx.scene_cache.mesh.collect_objects"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.0427,
      "name": "toolctx.scene_cache.rebuild.collect_document_meshes"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.1159,
      "name": "toolctx.scene_cache.rebuild.total"
    },
    {
      "at_s": 0.439,
      "elapsed_ms": 0.1255,
      "name": "toolctx.plan_trace.lifecycle.open.scene_cache_rebuild"
    },
    {
      "at_s": 0.442,
      "elapsed_ms": 0.3983,
      "name": "toolctx.plan_trace.render"
    },
    {
      "at_s": 0.443,
      "elapsed_ms": 5.834,
      "name": "toolctx.plan_trace.lifecycle.open"
    },
    {
      "at_s": 0.445,
      "details": {
        "changed": 2,
        "projected": true,
        "render": true
      },
      "elapsed_ms": 0.232,
      "name": "toolctx.plan2d.actor_visuals.full_interaction"
    },
    {
      "at_s": 0.446,
      "elapsed_ms": 0.4158,
      "name": "toolctx.plan_trace.render"
    },
    {
      "at_s": 0.446,
      "elapsed_ms": 3.3811,
      "name": "toolctx.plan_trace.surface.pick_press"
    },
    {
      "at_s": 0.446,
      "elapsed_ms": 3.4956,
      "name": "toolctx.plan_trace.event.mouse_press.total"
    },
    {
      "at_s": 0.446,
      "elapsed_ms": 3.5041,
      "name": "toolctx.plan_trace.event.total"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.4028,
      "name": "toolctx.plan_trace.render"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0006,
      "name": "toolctx.plan_trace.modify.selection_api_event"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.015,
      "name": "toolctx.plan_trace.cursor.project"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0044,
      "name": "toolctx.plan_trace.snap_targets.fast_signature"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0153,
      "name": "toolctx.plan_trace.snap_targets.structural_signature"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0008,
      "name": "toolctx.plan_trace.snap_targets.build.points"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0008,
      "name": "toolctx.plan_trace.snap_targets.build.lines"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0016,
      "name": "toolctx.plan_trace.snap_targets.build.arcs"
    },
    {
      "at_s": 0.448,
      "elapsed_ms": 0.0011,
      "name": "toolctx.plan_trace.snap_targets.build.beziers"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0008,
      "name": "toolctx.plan_trace.snap_targets.build.circles"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0477,
      "name": "toolctx.plan_trace.snap_targets.build.anchor"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.2055,
      "name": "toolctx.plan_trace.snap_targets.build_live_targets"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0223,
      "name": "toolctx.plan_trace.snap.build_screen_index"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.002,
      "name": "toolctx.plan_trace.snap.near_query.cells"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0025,
      "name": "toolctx.plan_trace.snap.near_query.materialize"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.1139,
      "name": "toolctx.plan_trace.snap.near_query.total"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.3994,
      "name": "toolctx.plan_trace.cursor.targets"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0004,
      "name": "toolctx.plan2d.smart_snap.prepare_targets"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0005,
      "name": "toolctx.snap.manager.providers"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0053,
      "name": "toolctx.scene_cache.snap.rebuild_screen_index"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0476,
      "name": "toolctx.scene_cache.snap.near_query.total"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0005,
      "name": "toolctx.snap.targets_to_results.classify"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0014,
      "name": "toolctx.snap.targets_to_results.segment_intersections"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0017,
      "name": "toolctx.snap.targets_to_results.curve_intersections"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0004,
      "name": "toolctx.snap.targets_to_results.direct_snaps"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.034,
      "name": "toolctx.snap.targets_to_results.total"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0415,
      "name": "toolctx.snap.manager.targets_to_results"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.1602,
      "name": "toolctx.plan2d.smart_snap.manager"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0028,
      "name": "toolctx.plan2d.smart_snap.alignment.project"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0074,
      "name": "toolctx.plan2d.guide_cache.scene.collect_targets"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0077,
      "name": "toolctx.plan2d.guide_cache.scene.build"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0453,
      "name": "toolctx.plan2d.smart_snap.alignment.scene_cache"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0188,
      "name": "toolctx.plan2d.guide_cache.extra.build"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.037,
      "name": "toolctx.plan2d.smart_snap.alignment.extra_cache"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0029,
      "name": "toolctx.plan2d.smart_snap.alignment.radius"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0166,
      "name": "toolctx.plan2d.smart_snap.alignment.nearest_axes"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0111,
      "name": "toolctx.plan2d.smart_snap.alignment.intersection_candidate"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.1528,
      "name": "toolctx.plan2d.smart_snap.alignment"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.3512,
      "name": "toolctx.plan2d.smart_snap.total"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.3809,
      "name": "toolctx.plan_trace.cursor.smart_snap"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0037,
      "name": "toolctx.plan_trace.cursor.constraint"
    },
    {
      "at_s": 0.449,
      "elapsed_ms": 0.0306,
      "name": "toolctx.plan_trace.cursor.pending_preview"
    },
    {
      "at_s": 0.45,
      "elapsed_ms": 0.4373,
      "name": "toolctx.plan_trace.cursor.register_cursor"
    },
    {
      "at_s": 0.45,
      "details": {
        "changed": 0,
        "projected": true,
        "render": false
      },
      "elapsed_ms": 0.0076,
      "name": "toolctx.plan2d.actor_visuals.full_interaction"
    },
    {
      "at_s": 0.45,
      "elapsed_ms": 0.0334,
      "name": "toolctx.plan_trace.cursor.sync_actor_visuals"
    },
    {
      "at_s": 0.45,
      "elapsed_ms": 0.0141,
      "name": "toolctx.plan_trace.cursor.sync_report"
    },
    {
      "at_s": 0.45,
      "elapsed_ms": 0.5137,
      "name": "toolctx.plan_trace.cursor.actor_sync"
    },
    {
      "at_s": 0.45,
      "elapsed_ms": 1.7549,
      "name": "toolctx.plan_trace.cursor.update"
    },
    {
      "at_s": 0.45,
      "elapsed_ms": 0.0196,
      "name": "toolctx.plan_trace.draw_press.snapshot"
    },
    {
      "at_s": 0.451,
      "details": {
        "changed": 1,
        "projected": true,
        "render": true
      },
      "elapsed_ms": 0.0065,
      "name": "toolctx.plan2d.actor_visuals.full_interaction"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 1.3687,
      "name": "toolctx.plan_trace.draw_press.rectangle"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0221,
      "name": "toolctx.plan_trace.draw_press.record_history"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 3.4674,
      "name": "toolctx.plan_trace.draw_press.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 3.4758,
      "name": "toolctx.plan_trace.event.mouse_press.draw_press"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 3.5992,
      "name": "toolctx.plan_trace.event.mouse_press.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 3.6064,
      "name": "toolctx.plan_trace.event.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0006,
      "name": "toolctx.plan_trace.modify.selection_api_event"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0081,
      "name": "toolctx.plan_trace.cursor.project"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0026,
      "name": "toolctx.plan_trace.snap_targets.fast_signature"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0136,
      "name": "toolctx.plan_trace.snap_targets.structural_signature"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0196,
      "name": "toolctx.plan_trace.snap_targets.build.points"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0007,
      "name": "toolctx.plan_trace.snap_targets.build.lines"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0005,
      "name": "toolctx.plan_trace.snap_targets.build.arcs"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0004,
      "name": "toolctx.plan_trace.snap_targets.build.beziers"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0004,
      "name": "toolctx.plan_trace.snap_targets.build.circles"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0116,
      "name": "toolctx.plan_trace.snap_targets.build.anchor"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0797,
      "name": "toolctx.plan_trace.snap_targets.build_live_targets"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0192,
      "name": "toolctx.plan_trace.snap.build_screen_index"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0018,
      "name": "toolctx.plan_trace.snap.near_query.cells"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0013,
      "name": "toolctx.plan_trace.snap.near_query.materialize"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0696,
      "name": "toolctx.plan_trace.snap.near_query.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.2127,
      "name": "toolctx.plan_trace.cursor.targets"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0005,
      "name": "toolctx.plan2d.smart_snap.prepare_targets"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0004,
      "name": "toolctx.snap.manager.providers"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0146,
      "name": "toolctx.scene_cache.snap.near_query.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0004,
      "name": "toolctx.snap.targets_to_results.classify"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0009,
      "name": "toolctx.snap.targets_to_results.segment_intersections"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.001,
      "name": "toolctx.snap.targets_to_results.curve_intersections"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0003,
      "name": "toolctx.snap.targets_to_results.direct_snaps"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.029,
      "name": "toolctx.snap.targets_to_results.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0341,
      "name": "toolctx.snap.manager.targets_to_results"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0992,
      "name": "toolctx.plan2d.smart_snap.manager"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0026,
      "name": "toolctx.plan2d.smart_snap.alignment.project"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0128,
      "name": "toolctx.plan2d.smart_snap.alignment.scene_cache"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.021,
      "name": "toolctx.plan2d.guide_cache.extra.build"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0367,
      "name": "toolctx.plan2d.smart_snap.alignment.extra_cache"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0024,
      "name": "toolctx.plan2d.smart_snap.alignment.radius"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0101,
      "name": "toolctx.plan2d.smart_snap.alignment.nearest_axes"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.0071,
      "name": "toolctx.plan2d.smart_snap.alignment.intersection_candidate"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.1067,
      "name": "toolctx.plan2d.smart_snap.alignment"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.2369,
      "name": "toolctx.plan2d.smart_snap.total"
    },
    {
      "at_s": 0.452,
      "elapsed_ms": 0.2563,
      "name": "toolctx.plan_trace.cursor.smart_snap"
    },
    {
      "at_s": 0.453,
      "elapsed_ms": 0.0025,
      "name": "toolctx.plan_trace.cursor.constraint"
    },
    {
      "at_s": 0.453,
      "elapsed_ms": 0.491,
      "name": "toolctx.plan_trace.cursor.pending_preview"
    },
    {
      "at_s": 0.453,
      "elapsed_ms": 0.443,
      "name": "toolctx.plan_trace.cursor.register_cursor"
    },
    {
      "at_s": 0.454,
      "elapsed_ms": 0.0393,
      "name": "toolctx.plan_trace.cursor.sync_actor_visuals"
    },
    {
      "at_s": 0.454,
      "elapsed_ms": 0.0034,
      "name": "toolctx.plan_trace.cursor.sync_report"
    },
    {
      "at_s": 0.454,
      "elapsed_ms": 0.5153,
      "name": "toolctx.plan_trace.cursor.actor_sync"
    },
    {
      "at_s": 0.454,
      "elapsed_ms": 1.8545,
      "name": "toolctx.plan_trace.cursor.update"
    },
    {
      "at_s": 0.454,
      "elapsed_ms": 0.0094,
      "name": "toolctx.plan_trace.draw_press.snapshot"
    },
    {
      "at_s": 0.455,
      "elapsed_ms": 0.6287,
      "name": "toolctx.plan_trace.sketch.compile_kernel"
    },
    {
      "at_s": 0.46,
      "elapsed_ms": 0.5914,
      "name": "toolctx.plan_trace.sketch.actor_visual_sync"
    },
    {
      "at_s": 0.462,
      "elapsed_ms": 7.9318,
      "name": "toolctx.plan_trace.draw_press.rectangle"
    },
    {
      "at_s": 0.463,
      "elapsed_ms": 10.8845,
      "name": "toolctx.plan_trace.draw_press.total"
    },
    {
      "at_s": 0.463,
      "elapsed_ms": 11.0839,
      "name": "toolctx.plan_trace.event.mouse_press.draw_press"
    },
    {
      "at_s": 0.463,
      "elapsed_ms": 11.2197,
      "name": "toolctx.plan_trace.event.mouse_press.total"
    },
    {
      "at_s": 0.463,
      "elapsed_ms": 11.2282,
      "name": "toolctx.plan_trace.event.total"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0104,
      "name": "toolctx.plan_trace.modify.selection_api_event"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0087,
      "name": "toolctx.plan_trace.cursor.project"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0016,
      "name": "toolctx.plan_trace.snap_targets.fast_signature"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0157,
      "name": "toolctx.plan_trace.snap_targets.structural_signature"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0443,
      "name": "toolctx.plan_trace.snap_targets.build.points"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0398,
      "name": "toolctx.plan_trace.snap_targets.build.lines"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0005,
      "name": "toolctx.plan_trace.snap_targets.build.arcs"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0003,
      "name": "toolctx.plan_trace.snap_targets.build.beziers"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0003,
      "name": "toolctx.plan_trace.snap_targets.build.circles"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0098,
      "name": "toolctx.plan_trace.snap_targets.build.anchor"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.1431,
      "name": "toolctx.plan_trace.snap_targets.build_live_targets"
    },
    {
      "at_s": 0.466,
      "elapsed_ms": 0.0412,
      "name": "toolctx.plan_trace.snap.build_screen_index"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0032,
      "name": "toolctx.plan_trace.snap.near_query.cells"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0032,
      "name": "toolctx.plan_trace.snap.near_query.materialize"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0999,
      "name": "toolctx.plan_trace.snap.near_query.total"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.335,
      "name": "toolctx.plan_trace.cursor.modify_near_targets"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0003,
      "name": "toolctx.plan2d.smart_snap.prepare_targets"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0003,
      "name": "toolctx.snap.manager.providers"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0143,
      "name": "toolctx.scene_cache.snap.near_query.total"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0128,
      "name": "toolctx.snap.targets_to_results.classify"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0102,
      "name": "toolctx.snap.targets_to_results.segment_intersections"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.001,
      "name": "toolctx.snap.targets_to_results.curve_intersections"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0376,
      "name": "toolctx.snap.targets_to_results.direct_snaps"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0914,
      "name": "toolctx.snap.targets_to_results.total"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0977,
      "name": "toolctx.snap.manager.targets_to_results"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.1628,
      "name": "toolctx.plan2d.smart_snap.manager"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0026,
      "name": "toolctx.plan2d.smart_snap.alignment.project"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.013,
      "name": "toolctx.plan2d.smart_snap.alignment.scene_cache"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0755,
      "name": "toolctx.plan2d.guide_cache.extra.build"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0909,
      "name": "toolctx.plan2d.smart_snap.alignment.extra_cache"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0025,
      "name": "toolctx.plan2d.smart_snap.alignment.radius"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0132,
      "name": "toolctx.plan2d.smart_snap.alignment.nearest_axes"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.0078,
      "name": "toolctx.plan2d.smart_snap.alignment.intersection_candidate"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.1715,
      "name": "toolctx.plan2d.smart_snap.alignment"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.3549,
      "name": "toolctx.plan2d.smart_snap.total"
    },
    {
      "at_s": 0.467,
      "elapsed_ms": 0.3762,
      "name": "toolctx.plan_trace.cursor.modify_local_snap"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 0.6246,
      "name": "toolctx.plan_trace.cursor.register_cursor"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 0.0559,
      "name": "toolctx.plan_trace.cursor.sync_actor_visuals"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 0.0134,
      "name": "toolctx.plan_trace.cursor.sync_report"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 0.7251,
      "name": "toolctx.plan_trace.cursor.modify_fast_actor_sync"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 1.6276,
      "name": "toolctx.plan_trace.cursor.update"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 1.9501,
      "name": "toolctx.plan_trace.event.mouse_move.update_cursor"
    },
    {
      "at_s": 0.468,
      "elapsed_ms": 2.2882,
      "name": "toolctx.plan_trace.event.mouse_move.total"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.0044,
      "name": "toolctx.scene_cache.rebuild.collect_sketch"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.0025,
      "name": "toolctx.scene_cache.rebuild.collect_selection"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.0025,
      "name": "toolctx.scene_cache.rebuild.collect_scene"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.021,
      "name": "toolctx.scene_cache.mesh.collect_objects"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.0301,
      "name": "toolctx.scene_cache.rebuild.collect_document_meshes"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.0816,
      "name": "toolctx.scene_cache.rebuild.total"
    },
    {
      "at_s": 0.47,
      "elapsed_ms": 0.0885,
      "name": "toolctx.plan_trace.lifecycle.open.scene_cache_rebuild"
    },
    {
      "at_s": 0.472,
      "elapsed_ms": 3.2968,
      "name": "toolctx.plan_trace.lifecycle.open"
    },
    {
      "at_s": 0.475,
      "elapsed_ms": 2.5134,
      "name": "toolctx.plan_trace.surface.pick_press"
    },
    {
      "at_s": 0.477,
      "elapsed_ms": 0.2195,
      "name": "toolctx.plan_trace.cursor.targets"
    },
    {
      "at_s": 0.477,
      "elapsed_ms": 0.0048,
      "name": "toolctx.scene_cache.snap.rebuild_screen_index"
    },
    {
      "at_s": 0.477,
      "elapsed_ms": 0.0071,
      "name": "toolctx.plan2d.guide_cache.scene.collect_targets"
    },
    {
      "at_s": 0.477,
      "elapsed_ms": 0.0061,
      "name": "toolctx.plan2d.guide_cache.scene.build"
    },
    {
      "at_s": 0.478,
      "elapsed_ms": 0.3293,
      "name": "toolctx.plan_trace.cursor.smart_snap"
    },
    {
      "at_s": 0.478,
      "elapsed_ms": 0.0026,
      "name": "toolctx.plan_trace.cursor.constraint"
    },
    {
      "at_s": 0.478,
      "elapsed_ms": 0.0244,
      "name": "toolctx.plan_trace.cursor.pending_preview"
    },
    {
      "at_s": 0.478,
      "elapsed_ms": 0.4335,
      "name": "toolctx.plan_trace.cursor.actor_sync"
    },
    {
      "at_s": 0.478,
      "elapsed_ms": 0.0137,
      "name": "toolctx.plan_trace.draw_press.snapshot"
    },
    {
      "at_s": 0.48,
      "elapsed_ms": 1.1655,
      "name": "toolctx.plan_trace.draw_press.rectangle"
    },
    {
      "at_s": 0.48,
      "elapsed_ms": 0.0231,
      "name": "toolctx.plan_trace.draw_press.record_history"
    },
    {
      "at_s": 0.48,
      "elapsed_ms": 2.8838,
      "name": "toolctx.plan_trace.draw_press.total"
    },
    {
      "at_s": 0.48,
      "elapsed_ms": 2.8919,
      "name": "toolctx.plan_trace.event.mouse_press.draw_press"
    },
    {
      "at_s": 0.482,
      "elapsed_ms": 0.6687,
      "name": "toolctx.plan_trace.sketch.compile_kernel"
    },
    {
      "at_s": 0.486,
      "elapsed_ms": 0.4648,
      "name": "toolctx.plan_trace.sketch.actor_visual_sync"
    },
    {
      "at_s": 0.495,
      "elapsed_ms": 1.5386,
      "name": "toolctx.plan_trace.native.select.total"
    },
    {
      "at_s": 0.495,
      "elapsed_ms": 0.0035,
      "name": "toolctx.plan_trace.native.release.total"
    },
    {
      "at_s": 0.495,
      "elapsed_ms": 0.1292,
      "name": "toolctx.plan_trace.event.mouse_release.total"
    },
    {
      "at_s": 0.498,
      "elapsed_ms": 0.0054,
      "name": "sketch.compile.insert_curve_intersections"
    },
    {
      "at_s": 0.498,
      "elapsed_ms": 0.0011,
      "name": "sketch.compile.split_arcs_at_vertices"
    },
    {
      "at_s": 0.498,
      "elapsed_ms": 0.0011,
      "name": "sketch.compile.split_circles_at_vertices"
    },
    {
      "at_s": 0.501,
      "elapsed_ms": 0.0054,
      "name": "sketch.compile.insert_curve_intersections"
    },
    {
      "at_s": 0.501,
      "elapsed_ms": 0.0008,
      "name": "sketch.compile.split_arcs_at_vertices"
    },
    {
      "at_s": 0.501,
      "elapsed_ms": 0.0008,
      "name": "sketch.compile.split_circles_at_vertices"
    },
    {
      "at_s": 0.502,
      "elapsed_ms": 0.7841,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    },
    {
      "at_s": 0.972,
      "elapsed_ms": 0.0044,
      "name": "sketch.compile.insert_curve_intersections"
    },
    {
      "at_s": 0.972,
      "elapsed_ms": 0.0007,
      "name": "sketch.compile.split_arcs_at_vertices"
    },
    {
      "at_s": 0.972,
      "elapsed_ms": 0.001,
      "name": "sketch.compile.split_circles_at_vertices"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.0043,
      "name": "toolctx.scene_cache.rebuild.collect_sketch"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.002,
      "name": "toolctx.scene_cache.rebuild.collect_selection"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.0031,
      "name": "toolctx.scene_cache.rebuild.collect_scene"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.0222,
      "name": "toolctx.scene_cache.mesh.collect_objects"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.0329,
      "name": "toolctx.scene_cache.rebuild.collect_document_meshes"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.089,
      "name": "toolctx.scene_cache.rebuild.total"
    },
    {
      "at_s": 0.975,
      "elapsed_ms": 0.0967,
      "name": "toolctx.plan_trace.lifecycle.open.scene_cache_rebuild"
    },
    {
      "at_s": 0.977,
      "elapsed_ms": 3.0666,
      "name": "toolctx.plan_trace.lifecycle.open"
    },
    {
      "at_s": 0.98,
      "elapsed_ms": 2.5231,
      "name": "toolctx.plan_trace.surface.pick_press"
    },
    {
      "at_s": 1.024,
      "elapsed_ms": 0.0047,
      "name": "toolctx.scene_cache.snap.rebuild_screen_index"
    },
    {
      "at_s": 1.024,
      "elapsed_ms": 0.0057,
      "name": "toolctx.plan2d.guide_cache.scene.collect_targets"
    },
    {
      "at_s": 1.024,
      "elapsed_ms": 0.0076,
      "name": "toolctx.plan2d.guide_cache.scene.build"
    },
    {
      "at_s": 1.027,
      "elapsed_ms": 0.0246,
      "name": "toolctx.plan_trace.draw_press.record_history"
    },
    {
      "at_s": 1.03,
      "elapsed_ms": 0.6069,
      "name": "toolctx.plan_trace.sketch.compile_kernel"
    },
    {
      "at_s": 1.04,
      "elapsed_ms": 0.4954,
      "name": "toolctx.plan_trace.sketch.actor_visual_sync"
    },
    {
      "at_s": 1.048,
      "elapsed_ms": 1.5832,
      "name": "toolctx.plan_trace.native.select.total"
    },
    {
      "at_s": 1.048,
      "elapsed_ms": 0.0042,
      "name": "toolctx.plan_trace.native.release.total"
    },
    {
      "at_s": 1.048,
      "elapsed_ms": 0.169,
      "name": "toolctx.plan_trace.event.mouse_release.total"
    },
    {
      "at_s": 1.077,
      "elapsed_ms": 1.4165,
      "name": "toolctx.plan_trace.native.select.total"
    },
    {
      "at_s": 1.077,
      "elapsed_ms": 0.0025,
      "name": "toolctx.plan_trace.native.release.total"
    },
    {
      "at_s": 1.077,
      "elapsed_ms": 0.1259,
      "name": "toolctx.plan_trace.event.mouse_release.total"
    },
    {
      "at_s": 1.108,
      "elapsed_ms": 0.0055,
      "name": "toolctx.plan_trace.apply.can_apply"
    },
    {
      "at_s": 1.111,
      "elapsed_ms": 0.0046,
      "name": "toolctx.plan_trace.apply.can_apply"
    },
    {
      "at_s": 1.124,
      "elapsed_ms": 1.4687,
      "name": "toolctx.plan_trace.draw_press.place_point"
    },
    {
      "at_s": 1.169,
      "elapsed_ms": 0.0082,
      "name": "toolctx.plan_trace.drag.project"
    },
    {
      "at_s": 1.17,
      "elapsed_ms": 0.6293,
      "name": "toolctx.plan_trace.drag.smart_snap"
    },
    {
      "at_s": 1.17,
      "elapsed_ms": 0.0194,
      "name": "toolctx.plan_trace.drag.build_replacements"
    },
    {
      "at_s": 1.171,
      "details": {
        "changed": 2,
        "projected": true,
        "render": false
      },
      "elapsed_ms": 0.0274,
      "name": "toolctx.plan2d.actor_visuals.fast_drag"
    },
    {
      "at_s": 1.171,
      "elapsed_ms": 1.3705,
      "name": "toolctx.plan_trace.drag.sync_moved_points"
    },
    {
      "at_s": 1.173,
      "elapsed_ms": 1.8304,
      "name": "toolctx.plan_trace.drag.cursor_actor"
    },
    {
      "at_s": 1.173,
      "elapsed_ms": 3.9423,
      "name": "toolctx.plan_trace.drag.resolve_positions.total"
    },
    {
      "at_s": 1.186,
      "elapsed_ms": 1.225,
      "name": "toolctx.plan_trace.draw_press.line"
    },
    {
      "at_s": 1.191,
      "elapsed_ms": 2.9616,
      "name": "toolctx.plan_trace.draw_press.line"
    },
    {
      "at_s": 1.193,
      "elapsed_ms": 1.8231,
      "name": "toolctx.plan_trace.event.key_press.total"
    },
    {
      "at_s": 1.206,
      "elapsed_ms": 0.7771,
      "name": "toolctx.plan_trace.motif.union_footprint"
    },
    {
      "at_s": 1.245,
      "elapsed_ms": 30.796,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    },
    {
      "at_s": 1.279,
      "elapsed_ms": 1.4801,
      "name": "toolctx.plan_trace.motif.union_footprint"
    },
    {
      "at_s": 1.314,
      "elapsed_ms": 0.9246,
      "name": "toolctx.plan_trace.motif.union_footprint"
    },
    {
      "at_s": 1.347,
      "elapsed_ms": 23.0537,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion"
    }
  ],
  "timers": {
    "plan_trace.apply.mesh.boolean_ready_extrusion": {
      "avg_ms": 6.9785,
      "count": 9,
      "last_ms": 23.0537,
      "max_ms": 30.796,
      "min_ms": 0.5969,
      "p50_ms": 0.8692,
      "p90_ms": 23.0537,
      "p95_ms": 30.796,
      "p99_ms": 30.796,
      "total_ms": 62.8066
    },
    "sketch.compile.insert_curve_intersections": {
      "avg_ms": 0.006,
      "count": 7,
      "last_ms": 0.016,
      "max_ms": 0.016,
      "min_ms": 0.0033,
      "p50_ms": 0.0044,
      "p90_ms": 0.0054,
      "p95_ms": 0.016,
      "p99_ms": 0.016,
      "total_ms": 0.0422
    },
    "sketch.compile.insert_line_intersections": {
      "avg_ms": 0.0127,
      "count": 28,
      "last_ms": 0.0009,
      "max_ms": 0.0497,
      "min_ms": 0.0006,
      "p50_ms": 0.0142,
      "p90_ms": 0.0202,
      "p95_ms": 0.0249,
      "p99_ms": 0.0497,
      "total_ms": 0.3556
    },
    "sketch.compile.merge_duplicate_points": {
      "avg_ms": 0.0125,
      "count": 28,
      "last_ms": 0.0085,
      "max_ms": 0.0295,
      "min_ms": 0.0012,
      "p50_ms": 0.0116,
      "p90_ms": 0.0186,
      "p95_ms": 0.0195,
      "p99_ms": 0.0295,
      "total_ms": 0.3509
    },
    "sketch.compile.rebuild_polylines": {
      "avg_ms": 0.0146,
      "count": 28,
      "last_ms": 0.0069,
      "max_ms": 0.0322,
      "min_ms": 0.0032,
      "p50_ms": 0.0141,
      "p90_ms": 0.02,
      "p95_ms": 0.0279,
      "p99_ms": 0.0322,
      "total_ms": 0.4092
    },
    "sketch.compile.remove_degenerate_curves": {
      "avg_ms": 0.0036,
      "count": 28,
      "last_ms": 0.0042,
      "max_ms": 0.0277,
      "min_ms": 0.0009,
      "p50_ms": 0.0018,
      "p90_ms": 0.004,
      "p95_ms": 0.0186,
      "p99_ms": 0.0277,
      "total_ms": 0.1004
    },
    "sketch.compile.remove_degenerate_lines.final": {
      "avg_ms": 0.0017,
      "count": 28,
      "last_ms": 0.0004,
      "max_ms": 0.0037,
      "min_ms": 0.0003,
      "p50_ms": 0.002,
      "p90_ms": 0.0025,
      "p95_ms": 0.0029,
      "p99_ms": 0.0037,
      "total_ms": 0.0487
    },
    "sketch.compile.remove_degenerate_lines.initial": {
      "avg_ms": 0.0037,
      "count": 28,
      "last_ms": 0.001,
      "max_ms": 0.017,
      "min_ms": 0.0008,
      "p50_ms": 0.0035,
      "p90_ms": 0.0052,
      "p95_ms": 0.0062,
      "p99_ms": 0.017,
      "total_ms": 0.1045
    },
    "sketch.compile.remove_duplicate_lines": {
      "avg_ms": 0.0028,
      "count": 28,
      "last_ms": 0.0009,
      "max_ms": 0.0188,
      "min_ms": 0.0006,
      "p50_ms": 0.0025,
      "p90_ms": 0.0035,
      "p95_ms": 0.0038,
      "p99_ms": 0.0188,
      "total_ms": 0.0798
    },
    "sketch.compile.solve_faces": {
      "avg_ms": 1.0571,
      "count": 28,
      "last_ms": 1.1582,
      "max_ms": 3.2867,
      "min_ms": 0.0206,
      "p50_ms": 0.4848,
      "p90_ms": 2.9107,
      "p95_ms": 3.2813,
      "p99_ms": 3.2867,
      "total_ms": 29.5987
    },
    "sketch.compile.split_arcs_at_vertices": {
      "avg_ms": 0.0008,
      "count": 7,
      "last_ms": 0.0008,
      "max_ms": 0.0011,
      "min_ms": 0.0007,
      "p50_ms": 0.0007,
      "p90_ms": 0.0008,
      "p95_ms": 0.0011,
      "p99_ms": 0.0011,
      "total_ms": 0.0055
    },
    "sketch.compile.split_circles_at_vertices": {
      "avg_ms": 0.0021,
      "count": 7,
      "last_ms": 0.0103,
      "max_ms": 0.0103,
      "min_ms": 0.0005,
      "p50_ms": 0.0008,
      "p90_ms": 0.0011,
      "p95_ms": 0.0103,
      "p99_ms": 0.0103,
      "total_ms": 0.0149
    },
    "sketch.compile.split_lines_at_vertices": {
      "avg_ms": 0.0097,
      "count": 28,
      "last_ms": 0.0007,
      "max_ms": 0.0385,
      "min_ms": 0.0007,
      "p50_ms": 0.0106,
      "p90_ms": 0.0153,
      "p95_ms": 0.0219,
      "p99_ms": 0.0385,
      "total_ms": 0.2723
    },
    "sketch.compile.total": {
      "avg_ms": 1.1988,
      "count": 28,
      "last_ms": 1.2606,
      "max_ms": 3.4353,
      "min_ms": 0.088,
      "p50_ms": 0.6215,
      "p90_ms": 3.2075,
      "p95_ms": 3.396,
      "p99_ms": 3.4353,
      "total_ms": 33.5659
    },
    "sketch.compile.validation": {
      "avg_ms": 0.0184,
      "count": 28,
      "last_ms": 0.0179,
      "max_ms": 0.0377,
      "min_ms": 0.0097,
      "p50_ms": 0.0168,
      "p90_ms": 0.0273,
      "p95_ms": 0.0341,
      "p99_ms": 0.0377,
      "total_ms": 0.5153
    },
    "sketch.face_solver.build_faces": {
      "avg_ms": 0.6699,
      "count": 25,
      "last_ms": 0.7524,
      "max_ms": 2.6308,
      "min_ms": 0.0841,
      "p50_ms": 0.1572,
      "p90_ms": 2.4988,
      "p95_ms": 2.5496,
      "p99_ms": 2.6308,
      "total_ms": 16.7476
    },
    "sketch.face_solver.containment": {
      "avg_ms": 0.0709,
      "count": 25,
      "last_ms": 0.0707,
      "max_ms": 0.1687,
      "min_ms": 0.0304,
      "p50_ms": 0.0384,
      "p90_ms": 0.1599,
      "p95_ms": 0.1685,
      "p99_ms": 0.1687,
      "total_ms": 1.7723
    },
    "sketch.face_solver.polygonize": {
      "avg_ms": 0.1177,
      "count": 27,
      "last_ms": 0.121,
      "max_ms": 0.281,
      "min_ms": 0.0408,
      "p50_ms": 0.1083,
      "p90_ms": 0.1992,
      "p95_ms": 0.2178,
      "p99_ms": 0.281,
      "total_ms": 3.1782
    },
    "sketch.face_solver.source_curves": {
      "avg_ms": 0.134,
      "count": 28,
      "last_ms": 0.1403,
      "max_ms": 0.594,
      "min_ms": 0.0041,
      "p50_ms": 0.1082,
      "p90_ms": 0.2316,
      "p95_ms": 0.2685,
      "p99_ms": 0.594,
      "total_ms": 3.7518
    },
    "toolctx.plan2d.actor_visuals.fast_drag": {
      "avg_ms": 0.0274,
      "count": 1,
      "last_ms": 0.0274,
      "max_ms": 0.0274,
      "min_ms": 0.0274,
      "p50_ms": 0.0274,
      "p90_ms": 0.0274,
      "p95_ms": 0.0274,
      "p99_ms": 0.0274,
      "total_ms": 0.0274
    },
    "toolctx.plan2d.actor_visuals.full_interaction": {
      "avg_ms": 0.2024,
      "count": 56,
      "last_ms": 0.2922,
      "max_ms": 1.6682,
      "min_ms": 0.0051,
      "p50_ms": 0.1518,
      "p90_ms": 0.4524,
      "p95_ms": 0.5369,
      "p99_ms": 1.0432,
      "total_ms": 11.3329
    },
    "toolctx.plan2d.guide_cache.extra.build": {
      "avg_ms": 0.0234,
      "count": 19,
      "last_ms": 0.0187,
      "max_ms": 0.0755,
      "min_ms": 0.0138,
      "p50_ms": 0.0188,
      "p90_ms": 0.0234,
      "p95_ms": 0.0627,
      "p99_ms": 0.0755,
      "total_ms": 0.4445
    },
    "toolctx.plan2d.guide_cache.scene.build": {
      "avg_ms": 0.0067,
      "count": 9,
      "last_ms": 0.0061,
      "max_ms": 0.0077,
      "min_ms": 0.0057,
      "p50_ms": 0.0063,
      "p90_ms": 0.0076,
      "p95_ms": 0.0077,
      "p99_ms": 0.0077,
      "total_ms": 0.0603
    },
    "toolctx.plan2d.guide_cache.scene.collect_targets": {
      "avg_ms": 0.0059,
      "count": 9,
      "last_ms": 0.0056,
      "max_ms": 0.0074,
      "min_ms": 0.0053,
      "p50_ms": 0.0056,
      "p90_ms": 0.0071,
      "p95_ms": 0.0074,
      "p99_ms": 0.0074,
      "total_ms": 0.0534
    },
    "toolctx.plan2d.smart_snap.alignment": {
      "avg_ms": 0.1263,
      "count": 19,
      "last_ms": 0.1073,
      "max_ms": 0.1715,
      "min_ms": 0.1002,
      "p50_ms": 0.1282,
      "p90_ms": 0.1528,
      "p95_ms": 0.158,
      "p99_ms": 0.1715,
      "total_ms": 2.4006
    },
    "toolctx.plan2d.smart_snap.alignment.extra_cache": {
      "avg_ms": 0.0396,
      "count": 19,
      "last_ms": 0.0335,
      "max_ms": 0.0909,
      "min_ms": 0.0295,
      "p50_ms": 0.0346,
      "p90_ms": 0.0392,
      "p95_ms": 0.0779,
      "p99_ms": 0.0909,
      "total_ms": 0.7528
    },
    "toolctx.plan2d.smart_snap.alignment.intersection_candidate": {
      "avg_ms": 0.0071,
      "count": 19,
      "last_ms": 0.0068,
      "max_ms": 0.0111,
      "min_ms": 0.0059,
      "p50_ms": 0.0068,
      "p90_ms": 0.0078,
      "p95_ms": 0.0088,
      "p99_ms": 0.0111,
      "total_ms": 0.1353
    },
    "toolctx.plan2d.smart_snap.alignment.nearest_axes": {
      "avg_ms": 0.0123,
      "count": 19,
      "last_ms": 0.0125,
      "max_ms": 0.0166,
      "min_ms": 0.0101,
      "p50_ms": 0.0122,
      "p90_ms": 0.0134,
      "p95_ms": 0.0149,
      "p99_ms": 0.0166,
      "total_ms": 0.2344
    },
    "toolctx.plan2d.smart_snap.alignment.project": {
      "avg_ms": 0.0027,
      "count": 19,
      "last_ms": 0.0026,
      "max_ms": 0.0031,
      "min_ms": 0.0025,
      "p50_ms": 0.0027,
      "p90_ms": 0.003,
      "p95_ms": 0.003,
      "p99_ms": 0.0031,
      "total_ms": 0.0516
    },
    "toolctx.plan2d.smart_snap.alignment.radius": {
      "avg_ms": 0.0023,
      "count": 19,
      "last_ms": 0.0018,
      "max_ms": 0.004,
      "min_ms": 0.0018,
      "p50_ms": 0.0022,
      "p90_ms": 0.0026,
      "p95_ms": 0.0029,
      "p99_ms": 0.004,
      "total_ms": 0.0436
    },
    "toolctx.plan2d.smart_snap.alignment.scene_cache": {
      "avg_ms": 0.0254,
      "count": 19,
      "last_ms": 0.0124,
      "max_ms": 0.0453,
      "min_ms": 0.0119,
      "p50_ms": 0.0139,
      "p90_ms": 0.04,
      "p95_ms": 0.0405,
      "p99_ms": 0.0453,
      "total_ms": 0.4821
    },
    "toolctx.plan2d.smart_snap.manager": {
      "avg_ms": 0.121,
      "count": 19,
      "last_ms": 0.095,
      "max_ms": 0.1628,
      "min_ms": 0.0926,
      "p50_ms": 0.1246,
      "p90_ms": 0.1403,
      "p95_ms": 0.1602,
      "p99_ms": 0.1628,
      "total_ms": 2.2991
    },
    "toolctx.plan2d.smart_snap.prepare_targets": {
      "avg_ms": 0.0003,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0005,
      "min_ms": 0.0003,
      "p50_ms": 0.0003,
      "p90_ms": 0.0004,
      "p95_ms": 0.0004,
      "p99_ms": 0.0005,
      "total_ms": 0.0064
    },
    "toolctx.plan2d.smart_snap.total": {
      "avg_ms": 0.2795,
      "count": 19,
      "last_ms": 0.2221,
      "max_ms": 0.3549,
      "min_ms": 0.2221,
      "p50_ms": 0.2849,
      "p90_ms": 0.3201,
      "p95_ms": 0.3512,
      "p99_ms": 0.3549,
      "total_ms": 5.311
    },
    "toolctx.plan_trace.apply.can_apply": {
      "avg_ms": 0.005,
      "count": 2,
      "last_ms": 0.0046,
      "max_ms": 0.0055,
      "min_ms": 0.0046,
      "p50_ms": 0.0046,
      "p90_ms": 0.0055,
      "p95_ms": 0.0055,
      "p99_ms": 0.0055,
      "total_ms": 0.01
    },
    "toolctx.plan_trace.cursor.actor_sync": {
      "avg_ms": 0.462,
      "count": 17,
      "last_ms": 0.4363,
      "max_ms": 0.517,
      "min_ms": 0.4319,
      "p50_ms": 0.4495,
      "p90_ms": 0.5137,
      "p95_ms": 0.5153,
      "p99_ms": 0.517,
      "total_ms": 7.8546
    },
    "toolctx.plan_trace.cursor.constraint": {
      "avg_ms": 0.0025,
      "count": 17,
      "last_ms": 0.0018,
      "max_ms": 0.0049,
      "min_ms": 0.0017,
      "p50_ms": 0.0025,
      "p90_ms": 0.0027,
      "p95_ms": 0.0037,
      "p99_ms": 0.0049,
      "total_ms": 0.0422
    },
    "toolctx.plan_trace.cursor.modify_fast_actor_sync": {
      "avg_ms": 0.7251,
      "count": 1,
      "last_ms": 0.7251,
      "max_ms": 0.7251,
      "min_ms": 0.7251,
      "p50_ms": 0.7251,
      "p90_ms": 0.7251,
      "p95_ms": 0.7251,
      "p99_ms": 0.7251,
      "total_ms": 0.7251
    },
    "toolctx.plan_trace.cursor.modify_local_snap": {
      "avg_ms": 0.3762,
      "count": 1,
      "last_ms": 0.3762,
      "max_ms": 0.3762,
      "min_ms": 0.3762,
      "p50_ms": 0.3762,
      "p90_ms": 0.3762,
      "p95_ms": 0.3762,
      "p99_ms": 0.3762,
      "total_ms": 0.3762
    },
    "toolctx.plan_trace.cursor.modify_near_targets": {
      "avg_ms": 0.335,
      "count": 1,
      "last_ms": 0.335,
      "max_ms": 0.335,
      "min_ms": 0.335,
      "p50_ms": 0.335,
      "p90_ms": 0.335,
      "p95_ms": 0.335,
      "p99_ms": 0.335,
      "total_ms": 0.335
    },
    "toolctx.plan_trace.cursor.pending_preview": {
      "avg_ms": 0.2296,
      "count": 17,
      "last_ms": 0.3709,
      "max_ms": 0.7868,
      "min_ms": 0.023,
      "p50_ms": 0.0443,
      "p90_ms": 0.44,
      "p95_ms": 0.491,
      "p99_ms": 0.7868,
      "total_ms": 3.9035
    },
    "toolctx.plan_trace.cursor.project": {
      "avg_ms": 0.0094,
      "count": 18,
      "last_ms": 0.0074,
      "max_ms": 0.015,
      "min_ms": 0.0064,
      "p50_ms": 0.0087,
      "p90_ms": 0.0124,
      "p95_ms": 0.0132,
      "p99_ms": 0.015,
      "total_ms": 0.1688
    },
    "toolctx.plan_trace.cursor.register_cursor": {
      "avg_ms": 0.4204,
      "count": 19,
      "last_ms": 0.3615,
      "max_ms": 0.7059,
      "min_ms": 0.3615,
      "p50_ms": 0.3842,
      "p90_ms": 0.443,
      "p95_ms": 0.6246,
      "p99_ms": 0.7059,
      "total_ms": 7.9877
    },
    "toolctx.plan_trace.cursor.smart_snap": {
      "avg_ms": 0.2961,
      "count": 17,
      "last_ms": 0.2411,
      "max_ms": 0.3809,
      "min_ms": 0.2411,
      "p50_ms": 0.3052,
      "p90_ms": 0.3391,
      "p95_ms": 0.3439,
      "p99_ms": 0.3809,
      "total_ms": 5.0341
    },
    "toolctx.plan_trace.cursor.sync_actor_visuals": {
      "avg_ms": 0.0886,
      "count": 19,
      "last_ms": 0.0346,
      "max_ms": 1.0731,
      "min_ms": 0.0266,
      "p50_ms": 0.0341,
      "p90_ms": 0.0413,
      "p95_ms": 0.0559,
      "p99_ms": 1.0731,
      "total_ms": 1.6833
    },
    "toolctx.plan_trace.cursor.sync_report": {
      "avg_ms": 0.0095,
      "count": 19,
      "last_ms": 0.0136,
      "max_ms": 0.0156,
      "min_ms": 0.0021,
      "p50_ms": 0.0127,
      "p90_ms": 0.0143,
      "p95_ms": 0.0145,
      "p99_ms": 0.0156,
      "total_ms": 0.1802
    },
    "toolctx.plan_trace.cursor.targets": {
      "avg_ms": 0.2593,
      "count": 17,
      "last_ms": 0.2211,
      "max_ms": 0.7154,
      "min_ms": 0.1892,
      "p50_ms": 0.2195,
      "p90_ms": 0.2592,
      "p95_ms": 0.3994,
      "p99_ms": 0.7154,
      "total_ms": 4.4081
    },
    "toolctx.plan_trace.cursor.update": {
      "avg_ms": 1.6307,
      "count": 18,
      "last_ms": 1.6297,
      "max_ms": 2.228,
      "min_ms": 1.3508,
      "p50_ms": 1.6098,
      "p90_ms": 1.8545,
      "p95_ms": 2.1005,
      "p99_ms": 2.228,
      "total_ms": 29.352
    },
    "toolctx.plan_trace.drag.build_replacements": {
      "avg_ms": 0.0194,
      "count": 1,
      "last_ms": 0.0194,
      "max_ms": 0.0194,
      "min_ms": 0.0194,
      "p50_ms": 0.0194,
      "p90_ms": 0.0194,
      "p95_ms": 0.0194,
      "p99_ms": 0.0194,
      "total_ms": 0.0194
    },
    "toolctx.plan_trace.drag.cursor_actor": {
      "avg_ms": 1.8304,
      "count": 1,
      "last_ms": 1.8304,
      "max_ms": 1.8304,
      "min_ms": 1.8304,
      "p50_ms": 1.8304,
      "p90_ms": 1.8304,
      "p95_ms": 1.8304,
      "p99_ms": 1.8304,
      "total_ms": 1.8304
    },
    "toolctx.plan_trace.drag.project": {
      "avg_ms": 0.0082,
      "count": 1,
      "last_ms": 0.0082,
      "max_ms": 0.0082,
      "min_ms": 0.0082,
      "p50_ms": 0.0082,
      "p90_ms": 0.0082,
      "p95_ms": 0.0082,
      "p99_ms": 0.0082,
      "total_ms": 0.0082
    },
    "toolctx.plan_trace.drag.resolve_positions.total": {
      "avg_ms": 3.9423,
      "count": 1,
      "last_ms": 3.9423,
      "max_ms": 3.9423,
      "min_ms": 3.9423,
      "p50_ms": 3.9423,
      "p90_ms": 3.9423,
      "p95_ms": 3.9423,
      "p99_ms": 3.9423,
      "total_ms": 3.9423
    },
    "toolctx.plan_trace.drag.smart_snap": {
      "avg_ms": 0.6293,
      "count": 1,
      "last_ms": 0.6293,
      "max_ms": 0.6293,
      "min_ms": 0.6293,
      "p50_ms": 0.6293,
      "p90_ms": 0.6293,
      "p95_ms": 0.6293,
      "p99_ms": 0.6293,
      "total_ms": 0.6293
    },
    "toolctx.plan_trace.drag.sync_moved_points": {
      "avg_ms": 1.3705,
      "count": 1,
      "last_ms": 1.3705,
      "max_ms": 1.3705,
      "min_ms": 1.3705,
      "p50_ms": 1.3705,
      "p90_ms": 1.3705,
      "p95_ms": 1.3705,
      "p99_ms": 1.3705,
      "total_ms": 1.3705
    },
    "toolctx.plan_trace.draw_press.line": {
      "avg_ms": 2.0933,
      "count": 2,
      "last_ms": 2.9616,
      "max_ms": 2.9616,
      "min_ms": 1.225,
      "p50_ms": 1.225,
      "p90_ms": 2.9616,
      "p95_ms": 2.9616,
      "p99_ms": 2.9616,
      "total_ms": 4.1866
    },
    "toolctx.plan_trace.draw_press.place_point": {
      "avg_ms": 1.4687,
      "count": 1,
      "last_ms": 1.4687,
      "max_ms": 1.4687,
      "min_ms": 1.4687,
      "p50_ms": 1.4687,
      "p90_ms": 1.4687,
      "p95_ms": 1.4687,
      "p99_ms": 1.4687,
      "total_ms": 1.4687
    },
    "toolctx.plan_trace.draw_press.record_history": {
      "avg_ms": 0.0201,
      "count": 9,
      "last_ms": 0.0181,
      "max_ms": 0.0246,
      "min_ms": 0.017,
      "p50_ms": 0.0185,
      "p90_ms": 0.0231,
      "p95_ms": 0.0246,
      "p99_ms": 0.0246,
      "total_ms": 0.1811
    },
    "toolctx.plan_trace.draw_press.rectangle": {
      "avg_ms": 4.5198,
      "count": 14,
      "last_ms": 7.1034,
      "max_ms": 12.3375,
      "min_ms": 1.1532,
      "p50_ms": 1.664,
      "p90_ms": 7.9318,
      "p95_ms": 7.9318,
      "p99_ms": 12.3375,
      "total_ms": 63.2776
    },
    "toolctx.plan_trace.draw_press.snapshot": {
      "avg_ms": 0.0121,
      "count": 17,
      "last_ms": 0.0089,
      "max_ms": 0.0196,
      "min_ms": 0.0083,
      "p50_ms": 0.0114,
      "p90_ms": 0.0154,
      "p95_ms": 0.0165,
      "p99_ms": 0.0196,
      "total_ms": 0.2058
    },
    "toolctx.plan_trace.draw_press.total": {
      "avg_ms": 6.3646,
      "count": 17,
      "last_ms": 5.3849,
      "max_ms": 15.0627,
      "min_ms": 2.7909,
      "p50_ms": 3.6426,
      "p90_ms": 10.8845,
      "p95_ms": 11.0704,
      "p99_ms": 15.0627,
      "total_ms": 108.1976
    },
    "toolctx.plan_trace.event.key_press.total": {
      "avg_ms": 1.8231,
      "count": 1,
      "last_ms": 1.8231,
      "max_ms": 1.8231,
      "min_ms": 1.8231,
      "p50_ms": 1.8231,
      "p90_ms": 1.8231,
      "p95_ms": 1.8231,
      "p99_ms": 1.8231,
      "total_ms": 1.8231
    },
    "toolctx.plan_trace.event.mouse_move.total": {
      "avg_ms": 2.2882,
      "count": 1,
      "last_ms": 2.2882,
      "max_ms": 2.2882,
      "min_ms": 2.2882,
      "p50_ms": 2.2882,
      "p90_ms": 2.2882,
      "p95_ms": 2.2882,
      "p99_ms": 2.2882,
      "total_ms": 2.2882
    },
    "toolctx.plan_trace.event.mouse_move.update_cursor": {
      "avg_ms": 1.9501,
      "count": 1,
      "last_ms": 1.9501,
      "max_ms": 1.9501,
      "min_ms": 1.9501,
      "p50_ms": 1.9501,
      "p90_ms": 1.9501,
      "p95_ms": 1.9501,
      "p99_ms": 1.9501,
      "total_ms": 1.9501
    },
    "toolctx.plan_trace.event.mouse_press.draw_press": {
      "avg_ms": 6.3866,
      "count": 17,
      "last_ms": 5.3968,
      "max_ms": 15.0771,
      "min_ms": 2.7978,
      "p50_ms": 3.6507,
      "p90_ms": 11.0839,
      "p95_ms": 11.0861,
      "p99_ms": 15.0771,
      "total_ms": 108.5714
    },
    "toolctx.plan_trace.event.mouse_press.total": {
      "avg_ms": 5.121,
      "count": 29,
      "last_ms": 5.5174,
      "max_ms": 15.2078,
      "min_ms": 2.5527,
      "p50_ms": 3.4956,
      "p90_ms": 10.0516,
      "p95_ms": 11.2197,
      "p99_ms": 15.2078,
      "total_ms": 148.5094
    },
    "toolctx.plan_trace.event.mouse_release.total": {
      "avg_ms": 0.1414,
      "count": 3,
      "last_ms": 0.1259,
      "max_ms": 0.169,
      "min_ms": 0.1259,
      "p50_ms": 0.1292,
      "p90_ms": 0.169,
      "p95_ms": 0.169,
      "p99_ms": 0.169,
      "total_ms": 0.4242
    },
    "toolctx.plan_trace.event.total": {
      "avg_ms": 4.5084,
      "count": 34,
      "last_ms": 1.8349,
      "max_ms": 15.2142,
      "min_ms": 0.1324,
      "p50_ms": 3.196,
      "p90_ms": 10.058,
      "p95_ms": 11.2207,
      "p99_ms": 15.2142,
      "total_ms": 153.2844
    },
    "toolctx.plan_trace.lifecycle.open": {
      "avg_ms": 3.81,
      "count": 12,
      "last_ms": 2.964,
      "max_ms": 9.1405,
      "min_ms": 2.3228,
      "p50_ms": 3.2968,
      "p90_ms": 5.834,
      "p95_ms": 5.834,
      "p99_ms": 9.1405,
      "total_ms": 45.7195
    },
    "toolctx.plan_trace.lifecycle.open.scene_cache_rebuild": {
      "avg_ms": 0.1283,
      "count": 12,
      "last_ms": 0.0888,
      "max_ms": 0.5005,
      "min_ms": 0.0835,
      "p50_ms": 0.0935,
      "p90_ms": 0.1255,
      "p95_ms": 0.1255,
      "p99_ms": 0.5005,
      "total_ms": 1.5394
    },
    "toolctx.plan_trace.modify.selection_api_event": {
      "avg_ms": 0.0019,
      "count": 21,
      "last_ms": 0.0004,
      "max_ms": 0.0104,
      "min_ms": 0.0004,
      "p50_ms": 0.0005,
      "p90_ms": 0.0065,
      "p95_ms": 0.0101,
      "p99_ms": 0.0104,
      "total_ms": 0.0404
    },
    "toolctx.plan_trace.motif.union_footprint": {
      "avg_ms": 1.0606,
      "count": 3,
      "last_ms": 0.9246,
      "max_ms": 1.4801,
      "min_ms": 0.7771,
      "p50_ms": 0.9246,
      "p90_ms": 1.4801,
      "p95_ms": 1.4801,
      "p99_ms": 1.4801,
      "total_ms": 3.1818
    },
    "toolctx.plan_trace.native.release.total": {
      "avg_ms": 0.0034,
      "count": 3,
      "last_ms": 0.0025,
      "max_ms": 0.0042,
      "min_ms": 0.0025,
      "p50_ms": 0.0035,
      "p90_ms": 0.0042,
      "p95_ms": 0.0042,
      "p99_ms": 0.0042,
      "total_ms": 0.0103
    },
    "toolctx.plan_trace.native.select.total": {
      "avg_ms": 1.5128,
      "count": 3,
      "last_ms": 1.4165,
      "max_ms": 1.5832,
      "min_ms": 1.4165,
      "p50_ms": 1.5386,
      "p90_ms": 1.5832,
      "p95_ms": 1.5832,
      "p99_ms": 1.5832,
      "total_ms": 4.5383
    },
    "toolctx.plan_trace.render": {
      "avg_ms": 0.5722,
      "count": 57,
      "last_ms": 0.3321,
      "max_ms": 5.3946,
      "min_ms": 0.2669,
      "p50_ms": 0.4241,
      "p90_ms": 0.6839,
      "p95_ms": 0.919,
      "p99_ms": 1.1029,
      "total_ms": 32.6154
    },
    "toolctx.plan_trace.sketch.actor_visual_sync": {
      "avg_ms": 0.4457,
      "count": 12,
      "last_ms": 0.4937,
      "max_ms": 0.5914,
      "min_ms": 0.0313,
      "p50_ms": 0.4846,
      "p90_ms": 0.587,
      "p95_ms": 0.587,
      "p99_ms": 0.5914,
      "total_ms": 5.3487
    },
    "toolctx.plan_trace.sketch.compile_kernel": {
      "avg_ms": 2.616,
      "count": 12,
      "last_ms": 8.0904,
      "max_ms": 12.0299,
      "min_ms": 0.1018,
      "p50_ms": 0.6287,
      "p90_ms": 8.0904,
      "p95_ms": 8.0904,
      "p99_ms": 12.0299,
      "total_ms": 31.3918
    },
    "toolctx.plan_trace.snap.build_screen_index": {
      "avg_ms": 0.0197,
      "count": 19,
      "last_ms": 0.0157,
      "max_ms": 0.0412,
      "min_ms": 0.0156,
      "p50_ms": 0.017,
      "p90_ms": 0.0223,
      "p95_ms": 0.0368,
      "p99_ms": 0.0412,
      "total_ms": 0.3736
    },
    "toolctx.plan_trace.snap.near_query.cells": {
      "avg_ms": 0.0018,
      "count": 19,
      "last_ms": 0.0015,
      "max_ms": 0.0032,
      "min_ms": 0.0014,
      "p50_ms": 0.0016,
      "p90_ms": 0.0022,
      "p95_ms": 0.0025,
      "p99_ms": 0.0032,
      "total_ms": 0.0346
    },
    "toolctx.plan_trace.snap.near_query.materialize": {
      "avg_ms": 0.0016,
      "count": 19,
      "last_ms": 0.0013,
      "max_ms": 0.0032,
      "min_ms": 0.0011,
      "p50_ms": 0.0014,
      "p90_ms": 0.002,
      "p95_ms": 0.0025,
      "p99_ms": 0.0032,
      "total_ms": 0.0297
    },
    "toolctx.plan_trace.snap.near_query.total": {
      "avg_ms": 0.0767,
      "count": 19,
      "last_ms": 0.0663,
      "max_ms": 0.1139,
      "min_ms": 0.0644,
      "p50_ms": 0.0719,
      "p90_ms": 0.0908,
      "p95_ms": 0.0999,
      "p99_ms": 0.1139,
      "total_ms": 1.4582
    },
    "toolctx.plan_trace.snap_targets.build.anchor": {
      "avg_ms": 0.0468,
      "count": 19,
      "last_ms": 0.0104,
      "max_ms": 0.486,
      "min_ms": 0.0093,
      "p50_ms": 0.0225,
      "p90_ms": 0.0477,
      "p95_ms": 0.0654,
      "p99_ms": 0.486,
      "total_ms": 0.8889
    },
    "toolctx.plan_trace.snap_targets.build.arcs": {
      "avg_ms": 0.0006,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0016,
      "min_ms": 0.0003,
      "p50_ms": 0.0005,
      "p90_ms": 0.0008,
      "p95_ms": 0.0008,
      "p99_ms": 0.0016,
      "total_ms": 0.0109
    },
    "toolctx.plan_trace.snap_targets.build.beziers": {
      "avg_ms": 0.0004,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0011,
      "min_ms": 0.0003,
      "p50_ms": 0.0004,
      "p90_ms": 0.0005,
      "p95_ms": 0.0007,
      "p99_ms": 0.0011,
      "total_ms": 0.0084
    },
    "toolctx.plan_trace.snap_targets.build.circles": {
      "avg_ms": 0.0005,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0008,
      "min_ms": 0.0002,
      "p50_ms": 0.0005,
      "p90_ms": 0.0006,
      "p95_ms": 0.0006,
      "p99_ms": 0.0008,
      "total_ms": 0.009
    },
    "toolctx.plan_trace.snap_targets.build.lines": {
      "avg_ms": 0.0044,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0398,
      "min_ms": 0.0004,
      "p50_ms": 0.0006,
      "p90_ms": 0.0008,
      "p95_ms": 0.0335,
      "p99_ms": 0.0398,
      "total_ms": 0.0835
    },
    "toolctx.plan_trace.snap_targets.build.points": {
      "avg_ms": 0.0131,
      "count": 19,
      "last_ms": 0.017,
      "max_ms": 0.0443,
      "min_ms": 0.0004,
      "p50_ms": 0.0152,
      "p90_ms": 0.0249,
      "p95_ms": 0.0433,
      "p99_ms": 0.0443,
      "total_ms": 0.2494
    },
    "toolctx.plan_trace.snap_targets.build_live_targets": {
      "avg_ms": 0.1195,
      "count": 19,
      "last_ms": 0.0743,
      "max_ms": 0.5674,
      "min_ms": 0.0709,
      "p50_ms": 0.0781,
      "p90_ms": 0.1431,
      "p95_ms": 0.2055,
      "p99_ms": 0.5674,
      "total_ms": 2.2714
    },
    "toolctx.plan_trace.snap_targets.fast_signature": {
      "avg_ms": 0.0021,
      "count": 20,
      "last_ms": 0.0017,
      "max_ms": 0.0044,
      "min_ms": 0.0013,
      "p50_ms": 0.002,
      "p90_ms": 0.0027,
      "p95_ms": 0.0027,
      "p99_ms": 0.0044,
      "total_ms": 0.0415
    },
    "toolctx.plan_trace.snap_targets.structural_signature": {
      "avg_ms": 0.0126,
      "count": 19,
      "last_ms": 0.0114,
      "max_ms": 0.0157,
      "min_ms": 0.0106,
      "p50_ms": 0.0122,
      "p90_ms": 0.0138,
      "p95_ms": 0.0153,
      "p99_ms": 0.0157,
      "total_ms": 0.2386
    },
    "toolctx.plan_trace.surface.pick_press": {
      "avg_ms": 3.0434,
      "count": 12,
      "last_ms": 4.0603,
      "max_ms": 4.0603,
      "min_ms": 2.4633,
      "p50_ms": 2.7298,
      "p90_ms": 4.0364,
      "p95_ms": 4.0364,
      "p99_ms": 4.0603,
      "total_ms": 36.521
    },
    "toolctx.scene_cache.mesh.collect_objects": {
      "avg_ms": 0.017,
      "count": 12,
      "last_ms": 0.0101,
      "max_ms": 0.0284,
      "min_ms": 0.0083,
      "p50_ms": 0.0203,
      "p90_ms": 0.0249,
      "p95_ms": 0.0249,
      "p99_ms": 0.0284,
      "total_ms": 0.2041
    },
    "toolctx.scene_cache.rebuild.collect_document_meshes": {
      "avg_ms": 0.0313,
      "count": 12,
      "last_ms": 0.0287,
      "max_ms": 0.0427,
      "min_ms": 0.0264,
      "p50_ms": 0.0309,
      "p90_ms": 0.0361,
      "p95_ms": 0.0361,
      "p99_ms": 0.0427,
      "total_ms": 0.3756
    },
    "toolctx.scene_cache.rebuild.collect_scene": {
      "avg_ms": 0.0026,
      "count": 12,
      "last_ms": 0.0025,
      "max_ms": 0.0037,
      "min_ms": 0.002,
      "p50_ms": 0.0025,
      "p90_ms": 0.0033,
      "p95_ms": 0.0033,
      "p99_ms": 0.0037,
      "total_ms": 0.031
    },
    "toolctx.scene_cache.rebuild.collect_selection": {
      "avg_ms": 0.0022,
      "count": 12,
      "last_ms": 0.002,
      "max_ms": 0.0029,
      "min_ms": 0.0017,
      "p50_ms": 0.0021,
      "p90_ms": 0.0025,
      "p95_ms": 0.0025,
      "p99_ms": 0.0029,
      "total_ms": 0.0259
    },
    "toolctx.scene_cache.rebuild.collect_sketch": {
      "avg_ms": 0.0039,
      "count": 12,
      "last_ms": 0.0039,
      "max_ms": 0.0052,
      "min_ms": 0.0031,
      "p50_ms": 0.0039,
      "p90_ms": 0.0047,
      "p95_ms": 0.0047,
      "p99_ms": 0.0052,
      "total_ms": 0.0472
    },
    "toolctx.scene_cache.rebuild.total": {
      "avg_ms": 0.0857,
      "count": 12,
      "last_ms": 0.0813,
      "max_ms": 0.1159,
      "min_ms": 0.0761,
      "p50_ms": 0.0835,
      "p90_ms": 0.0961,
      "p95_ms": 0.0961,
      "p99_ms": 0.1159,
      "total_ms": 1.0285
    },
    "toolctx.scene_cache.snap.near_query.total": {
      "avg_ms": 0.0261,
      "count": 19,
      "last_ms": 0.0138,
      "max_ms": 0.0476,
      "min_ms": 0.0129,
      "p50_ms": 0.0147,
      "p90_ms": 0.0405,
      "p95_ms": 0.0412,
      "p99_ms": 0.0476,
      "total_ms": 0.4962
    },
    "toolctx.scene_cache.snap.rebuild_screen_index": {
      "avg_ms": 0.0046,
      "count": 9,
      "last_ms": 0.0047,
      "max_ms": 0.0053,
      "min_ms": 0.004,
      "p50_ms": 0.0047,
      "p90_ms": 0.0051,
      "p95_ms": 0.0053,
      "p99_ms": 0.0053,
      "total_ms": 0.0417
    },
    "toolctx.snap.manager.providers": {
      "avg_ms": 0.0003,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0005,
      "min_ms": 0.0002,
      "p50_ms": 0.0003,
      "p90_ms": 0.0005,
      "p95_ms": 0.0005,
      "p99_ms": 0.0005,
      "total_ms": 0.0066
    },
    "toolctx.snap.manager.targets_to_results": {
      "avg_ms": 0.0397,
      "count": 19,
      "last_ms": 0.0338,
      "max_ms": 0.0977,
      "min_ms": 0.0331,
      "p50_ms": 0.0363,
      "p90_ms": 0.0415,
      "p95_ms": 0.0417,
      "p99_ms": 0.0977,
      "total_ms": 0.7546
    },
    "toolctx.snap.targets_to_results.classify": {
      "avg_ms": 0.001,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0128,
      "min_ms": 0.0003,
      "p50_ms": 0.0004,
      "p90_ms": 0.0005,
      "p95_ms": 0.0007,
      "p99_ms": 0.0128,
      "total_ms": 0.0197
    },
    "toolctx.snap.targets_to_results.curve_intersections": {
      "avg_ms": 0.0011,
      "count": 19,
      "last_ms": 0.001,
      "max_ms": 0.0017,
      "min_ms": 0.0009,
      "p50_ms": 0.001,
      "p90_ms": 0.0013,
      "p95_ms": 0.0014,
      "p99_ms": 0.0017,
      "total_ms": 0.0209
    },
    "toolctx.snap.targets_to_results.direct_snaps": {
      "avg_ms": 0.0025,
      "count": 19,
      "last_ms": 0.0003,
      "max_ms": 0.0376,
      "min_ms": 0.0002,
      "p50_ms": 0.0003,
      "p90_ms": 0.0005,
      "p95_ms": 0.0053,
      "p99_ms": 0.0376,
      "total_ms": 0.048
    },
    "toolctx.snap.targets_to_results.segment_intersections": {
      "avg_ms": 0.0014,
      "count": 19,
      "last_ms": 0.0006,
      "max_ms": 0.0102,
      "min_ms": 0.0006,
      "p50_ms": 0.0009,
      "p90_ms": 0.0011,
      "p95_ms": 0.0014,
      "p99_ms": 0.0102,
      "total_ms": 0.0258
    },
    "toolctx.snap.targets_to_results.total": {
      "avg_ms": 0.034,
      "count": 19,
      "last_ms": 0.0285,
      "max_ms": 0.0914,
      "min_ms": 0.0278,
      "p50_ms": 0.0304,
      "p90_ms": 0.0355,
      "p95_ms": 0.036,
      "p99_ms": 0.0914,
      "total_ms": 0.6454
    }
  },
  "top_count": [
    {
      "avg_ms": 0.5722,
      "count": 57,
      "last_ms": 0.3321,
      "max_ms": 5.3946,
      "min_ms": 0.2669,
      "name": "toolctx.plan_trace.render",
      "p50_ms": 0.4241,
      "p90_ms": 0.6839,
      "p95_ms": 0.919,
      "p99_ms": 1.1029,
      "total_ms": 32.6154
    },
    {
      "avg_ms": 0.2024,
      "count": 56,
      "last_ms": 0.2922,
      "max_ms": 1.6682,
      "min_ms": 0.0051,
      "name": "toolctx.plan2d.actor_visuals.full_interaction",
      "p50_ms": 0.1518,
      "p90_ms": 0.4524,
      "p95_ms": 0.5369,
      "p99_ms": 1.0432,
      "total_ms": 11.3329
    },
    {
      "avg_ms": 4.5084,
      "count": 34,
      "last_ms": 1.8349,
      "max_ms": 15.2142,
      "min_ms": 0.1324,
      "name": "toolctx.plan_trace.event.total",
      "p50_ms": 3.196,
      "p90_ms": 10.058,
      "p95_ms": 11.2207,
      "p99_ms": 15.2142,
      "total_ms": 153.2844
    },
    {
      "avg_ms": 5.121,
      "count": 29,
      "last_ms": 5.5174,
      "max_ms": 15.2078,
      "min_ms": 2.5527,
      "name": "toolctx.plan_trace.event.mouse_press.total",
      "p50_ms": 3.4956,
      "p90_ms": 10.0516,
      "p95_ms": 11.2197,
      "p99_ms": 15.2078,
      "total_ms": 148.5094
    },
    {
      "avg_ms": 0.0127,
      "count": 28,
      "last_ms": 0.0009,
      "max_ms": 0.0497,
      "min_ms": 0.0006,
      "name": "sketch.compile.insert_line_intersections",
      "p50_ms": 0.0142,
      "p90_ms": 0.0202,
      "p95_ms": 0.0249,
      "p99_ms": 0.0497,
      "total_ms": 0.3556
    },
    {
      "avg_ms": 0.0125,
      "count": 28,
      "last_ms": 0.0085,
      "max_ms": 0.0295,
      "min_ms": 0.0012,
      "name": "sketch.compile.merge_duplicate_points",
      "p50_ms": 0.0116,
      "p90_ms": 0.0186,
      "p95_ms": 0.0195,
      "p99_ms": 0.0295,
      "total_ms": 0.3509
    },
    {
      "avg_ms": 0.0146,
      "count": 28,
      "last_ms": 0.0069,
      "max_ms": 0.0322,
      "min_ms": 0.0032,
      "name": "sketch.compile.rebuild_polylines",
      "p50_ms": 0.0141,
      "p90_ms": 0.02,
      "p95_ms": 0.0279,
      "p99_ms": 0.0322,
      "total_ms": 0.4092
    },
    {
      "avg_ms": 0.0036,
      "count": 28,
      "last_ms": 0.0042,
      "max_ms": 0.0277,
      "min_ms": 0.0009,
      "name": "sketch.compile.remove_degenerate_curves",
      "p50_ms": 0.0018,
      "p90_ms": 0.004,
      "p95_ms": 0.0186,
      "p99_ms": 0.0277,
      "total_ms": 0.1004
    },
    {
      "avg_ms": 0.0017,
      "count": 28,
      "last_ms": 0.0004,
      "max_ms": 0.0037,
      "min_ms": 0.0003,
      "name": "sketch.compile.remove_degenerate_lines.final",
      "p50_ms": 0.002,
      "p90_ms": 0.0025,
      "p95_ms": 0.0029,
      "p99_ms": 0.0037,
      "total_ms": 0.0487
    },
    {
      "avg_ms": 0.0037,
      "count": 28,
      "last_ms": 0.001,
      "max_ms": 0.017,
      "min_ms": 0.0008,
      "name": "sketch.compile.remove_degenerate_lines.initial",
      "p50_ms": 0.0035,
      "p90_ms": 0.0052,
      "p95_ms": 0.0062,
      "p99_ms": 0.017,
      "total_ms": 0.1045
    },
    {
      "avg_ms": 0.0028,
      "count": 28,
      "last_ms": 0.0009,
      "max_ms": 0.0188,
      "min_ms": 0.0006,
      "name": "sketch.compile.remove_duplicate_lines",
      "p50_ms": 0.0025,
      "p90_ms": 0.0035,
      "p95_ms": 0.0038,
      "p99_ms": 0.0188,
      "total_ms": 0.0798
    },
    {
      "avg_ms": 1.0571,
      "count": 28,
      "last_ms": 1.1582,
      "max_ms": 3.2867,
      "min_ms": 0.0206,
      "name": "sketch.compile.solve_faces",
      "p50_ms": 0.4848,
      "p90_ms": 2.9107,
      "p95_ms": 3.2813,
      "p99_ms": 3.2867,
      "total_ms": 29.5987
    },
    {
      "avg_ms": 0.0097,
      "count": 28,
      "last_ms": 0.0007,
      "max_ms": 0.0385,
      "min_ms": 0.0007,
      "name": "sketch.compile.split_lines_at_vertices",
      "p50_ms": 0.0106,
      "p90_ms": 0.0153,
      "p95_ms": 0.0219,
      "p99_ms": 0.0385,
      "total_ms": 0.2723
    },
    {
      "avg_ms": 1.1988,
      "count": 28,
      "last_ms": 1.2606,
      "max_ms": 3.4353,
      "min_ms": 0.088,
      "name": "sketch.compile.total",
      "p50_ms": 0.6215,
      "p90_ms": 3.2075,
      "p95_ms": 3.396,
      "p99_ms": 3.4353,
      "total_ms": 33.5659
    },
    {
      "avg_ms": 0.0184,
      "count": 28,
      "last_ms": 0.0179,
      "max_ms": 0.0377,
      "min_ms": 0.0097,
      "name": "sketch.compile.validation",
      "p50_ms": 0.0168,
      "p90_ms": 0.0273,
      "p95_ms": 0.0341,
      "p99_ms": 0.0377,
      "total_ms": 0.5153
    },
    {
      "avg_ms": 0.134,
      "count": 28,
      "last_ms": 0.1403,
      "max_ms": 0.594,
      "min_ms": 0.0041,
      "name": "sketch.face_solver.source_curves",
      "p50_ms": 0.1082,
      "p90_ms": 0.2316,
      "p95_ms": 0.2685,
      "p99_ms": 0.594,
      "total_ms": 3.7518
    },
    {
      "avg_ms": 0.1177,
      "count": 27,
      "last_ms": 0.121,
      "max_ms": 0.281,
      "min_ms": 0.0408,
      "name": "sketch.face_solver.polygonize",
      "p50_ms": 0.1083,
      "p90_ms": 0.1992,
      "p95_ms": 0.2178,
      "p99_ms": 0.281,
      "total_ms": 3.1782
    },
    {
      "avg_ms": 0.6699,
      "count": 25,
      "last_ms": 0.7524,
      "max_ms": 2.6308,
      "min_ms": 0.0841,
      "name": "sketch.face_solver.build_faces",
      "p50_ms": 0.1572,
      "p90_ms": 2.4988,
      "p95_ms": 2.5496,
      "p99_ms": 2.6308,
      "total_ms": 16.7476
    },
    {
      "avg_ms": 0.0709,
      "count": 25,
      "last_ms": 0.0707,
      "max_ms": 0.1687,
      "min_ms": 0.0304,
      "name": "sketch.face_solver.containment",
      "p50_ms": 0.0384,
      "p90_ms": 0.1599,
      "p95_ms": 0.1685,
      "p99_ms": 0.1687,
      "total_ms": 1.7723
    },
    {
      "avg_ms": 0.0019,
      "count": 21,
      "last_ms": 0.0004,
      "max_ms": 0.0104,
      "min_ms": 0.0004,
      "name": "toolctx.plan_trace.modify.selection_api_event",
      "p50_ms": 0.0005,
      "p90_ms": 0.0065,
      "p95_ms": 0.0101,
      "p99_ms": 0.0104,
      "total_ms": 0.0404
    },
    {
      "avg_ms": 0.0021,
      "count": 20,
      "last_ms": 0.0017,
      "max_ms": 0.0044,
      "min_ms": 0.0013,
      "name": "toolctx.plan_trace.snap_targets.fast_signature",
      "p50_ms": 0.002,
      "p90_ms": 0.0027,
      "p95_ms": 0.0027,
      "p99_ms": 0.0044,
      "total_ms": 0.0415
    },
    {
      "avg_ms": 0.0234,
      "count": 19,
      "last_ms": 0.0187,
      "max_ms": 0.0755,
      "min_ms": 0.0138,
      "name": "toolctx.plan2d.guide_cache.extra.build",
      "p50_ms": 0.0188,
      "p90_ms": 0.0234,
      "p95_ms": 0.0627,
      "p99_ms": 0.0755,
      "total_ms": 0.4445
    },
    {
      "avg_ms": 0.1263,
      "count": 19,
      "last_ms": 0.1073,
      "max_ms": 0.1715,
      "min_ms": 0.1002,
      "name": "toolctx.plan2d.smart_snap.alignment",
      "p50_ms": 0.1282,
      "p90_ms": 0.1528,
      "p95_ms": 0.158,
      "p99_ms": 0.1715,
      "total_ms": 2.4006
    },
    {
      "avg_ms": 0.0396,
      "count": 19,
      "last_ms": 0.0335,
      "max_ms": 0.0909,
      "min_ms": 0.0295,
      "name": "toolctx.plan2d.smart_snap.alignment.extra_cache",
      "p50_ms": 0.0346,
      "p90_ms": 0.0392,
      "p95_ms": 0.0779,
      "p99_ms": 0.0909,
      "total_ms": 0.7528
    },
    {
      "avg_ms": 0.0071,
      "count": 19,
      "last_ms": 0.0068,
      "max_ms": 0.0111,
      "min_ms": 0.0059,
      "name": "toolctx.plan2d.smart_snap.alignment.intersection_candidate",
      "p50_ms": 0.0068,
      "p90_ms": 0.0078,
      "p95_ms": 0.0088,
      "p99_ms": 0.0111,
      "total_ms": 0.1353
    },
    {
      "avg_ms": 0.0123,
      "count": 19,
      "last_ms": 0.0125,
      "max_ms": 0.0166,
      "min_ms": 0.0101,
      "name": "toolctx.plan2d.smart_snap.alignment.nearest_axes",
      "p50_ms": 0.0122,
      "p90_ms": 0.0134,
      "p95_ms": 0.0149,
      "p99_ms": 0.0166,
      "total_ms": 0.2344
    },
    {
      "avg_ms": 0.0027,
      "count": 19,
      "last_ms": 0.0026,
      "max_ms": 0.0031,
      "min_ms": 0.0025,
      "name": "toolctx.plan2d.smart_snap.alignment.project",
      "p50_ms": 0.0027,
      "p90_ms": 0.003,
      "p95_ms": 0.003,
      "p99_ms": 0.0031,
      "total_ms": 0.0516
    },
    {
      "avg_ms": 0.0023,
      "count": 19,
      "last_ms": 0.0018,
      "max_ms": 0.004,
      "min_ms": 0.0018,
      "name": "toolctx.plan2d.smart_snap.alignment.radius",
      "p50_ms": 0.0022,
      "p90_ms": 0.0026,
      "p95_ms": 0.0029,
      "p99_ms": 0.004,
      "total_ms": 0.0436
    },
    {
      "avg_ms": 0.0254,
      "count": 19,
      "last_ms": 0.0124,
      "max_ms": 0.0453,
      "min_ms": 0.0119,
      "name": "toolctx.plan2d.smart_snap.alignment.scene_cache",
      "p50_ms": 0.0139,
      "p90_ms": 0.04,
      "p95_ms": 0.0405,
      "p99_ms": 0.0453,
      "total_ms": 0.4821
    },
    {
      "avg_ms": 0.121,
      "count": 19,
      "last_ms": 0.095,
      "max_ms": 0.1628,
      "min_ms": 0.0926,
      "name": "toolctx.plan2d.smart_snap.manager",
      "p50_ms": 0.1246,
      "p90_ms": 0.1403,
      "p95_ms": 0.1602,
      "p99_ms": 0.1628,
      "total_ms": 2.2991
    },
    {
      "avg_ms": 0.0003,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0005,
      "min_ms": 0.0003,
      "name": "toolctx.plan2d.smart_snap.prepare_targets",
      "p50_ms": 0.0003,
      "p90_ms": 0.0004,
      "p95_ms": 0.0004,
      "p99_ms": 0.0005,
      "total_ms": 0.0064
    },
    {
      "avg_ms": 0.2795,
      "count": 19,
      "last_ms": 0.2221,
      "max_ms": 0.3549,
      "min_ms": 0.2221,
      "name": "toolctx.plan2d.smart_snap.total",
      "p50_ms": 0.2849,
      "p90_ms": 0.3201,
      "p95_ms": 0.3512,
      "p99_ms": 0.3549,
      "total_ms": 5.311
    },
    {
      "avg_ms": 0.4204,
      "count": 19,
      "last_ms": 0.3615,
      "max_ms": 0.7059,
      "min_ms": 0.3615,
      "name": "toolctx.plan_trace.cursor.register_cursor",
      "p50_ms": 0.3842,
      "p90_ms": 0.443,
      "p95_ms": 0.6246,
      "p99_ms": 0.7059,
      "total_ms": 7.9877
    },
    {
      "avg_ms": 0.0886,
      "count": 19,
      "last_ms": 0.0346,
      "max_ms": 1.0731,
      "min_ms": 0.0266,
      "name": "toolctx.plan_trace.cursor.sync_actor_visuals",
      "p50_ms": 0.0341,
      "p90_ms": 0.0413,
      "p95_ms": 0.0559,
      "p99_ms": 1.0731,
      "total_ms": 1.6833
    },
    {
      "avg_ms": 0.0095,
      "count": 19,
      "last_ms": 0.0136,
      "max_ms": 0.0156,
      "min_ms": 0.0021,
      "name": "toolctx.plan_trace.cursor.sync_report",
      "p50_ms": 0.0127,
      "p90_ms": 0.0143,
      "p95_ms": 0.0145,
      "p99_ms": 0.0156,
      "total_ms": 0.1802
    },
    {
      "avg_ms": 0.0197,
      "count": 19,
      "last_ms": 0.0157,
      "max_ms": 0.0412,
      "min_ms": 0.0156,
      "name": "toolctx.plan_trace.snap.build_screen_index",
      "p50_ms": 0.017,
      "p90_ms": 0.0223,
      "p95_ms": 0.0368,
      "p99_ms": 0.0412,
      "total_ms": 0.3736
    },
    {
      "avg_ms": 0.0018,
      "count": 19,
      "last_ms": 0.0015,
      "max_ms": 0.0032,
      "min_ms": 0.0014,
      "name": "toolctx.plan_trace.snap.near_query.cells",
      "p50_ms": 0.0016,
      "p90_ms": 0.0022,
      "p95_ms": 0.0025,
      "p99_ms": 0.0032,
      "total_ms": 0.0346
    },
    {
      "avg_ms": 0.0016,
      "count": 19,
      "last_ms": 0.0013,
      "max_ms": 0.0032,
      "min_ms": 0.0011,
      "name": "toolctx.plan_trace.snap.near_query.materialize",
      "p50_ms": 0.0014,
      "p90_ms": 0.002,
      "p95_ms": 0.0025,
      "p99_ms": 0.0032,
      "total_ms": 0.0297
    },
    {
      "avg_ms": 0.0767,
      "count": 19,
      "last_ms": 0.0663,
      "max_ms": 0.1139,
      "min_ms": 0.0644,
      "name": "toolctx.plan_trace.snap.near_query.total",
      "p50_ms": 0.0719,
      "p90_ms": 0.0908,
      "p95_ms": 0.0999,
      "p99_ms": 0.1139,
      "total_ms": 1.4582
    },
    {
      "avg_ms": 0.0468,
      "count": 19,
      "last_ms": 0.0104,
      "max_ms": 0.486,
      "min_ms": 0.0093,
      "name": "toolctx.plan_trace.snap_targets.build.anchor",
      "p50_ms": 0.0225,
      "p90_ms": 0.0477,
      "p95_ms": 0.0654,
      "p99_ms": 0.486,
      "total_ms": 0.8889
    },
    {
      "avg_ms": 0.0006,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0016,
      "min_ms": 0.0003,
      "name": "toolctx.plan_trace.snap_targets.build.arcs",
      "p50_ms": 0.0005,
      "p90_ms": 0.0008,
      "p95_ms": 0.0008,
      "p99_ms": 0.0016,
      "total_ms": 0.0109
    },
    {
      "avg_ms": 0.0004,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0011,
      "min_ms": 0.0003,
      "name": "toolctx.plan_trace.snap_targets.build.beziers",
      "p50_ms": 0.0004,
      "p90_ms": 0.0005,
      "p95_ms": 0.0007,
      "p99_ms": 0.0011,
      "total_ms": 0.0084
    },
    {
      "avg_ms": 0.0005,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0008,
      "min_ms": 0.0002,
      "name": "toolctx.plan_trace.snap_targets.build.circles",
      "p50_ms": 0.0005,
      "p90_ms": 0.0006,
      "p95_ms": 0.0006,
      "p99_ms": 0.0008,
      "total_ms": 0.009
    },
    {
      "avg_ms": 0.0044,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0398,
      "min_ms": 0.0004,
      "name": "toolctx.plan_trace.snap_targets.build.lines",
      "p50_ms": 0.0006,
      "p90_ms": 0.0008,
      "p95_ms": 0.0335,
      "p99_ms": 0.0398,
      "total_ms": 0.0835
    },
    {
      "avg_ms": 0.0131,
      "count": 19,
      "last_ms": 0.017,
      "max_ms": 0.0443,
      "min_ms": 0.0004,
      "name": "toolctx.plan_trace.snap_targets.build.points",
      "p50_ms": 0.0152,
      "p90_ms": 0.0249,
      "p95_ms": 0.0433,
      "p99_ms": 0.0443,
      "total_ms": 0.2494
    },
    {
      "avg_ms": 0.1195,
      "count": 19,
      "last_ms": 0.0743,
      "max_ms": 0.5674,
      "min_ms": 0.0709,
      "name": "toolctx.plan_trace.snap_targets.build_live_targets",
      "p50_ms": 0.0781,
      "p90_ms": 0.1431,
      "p95_ms": 0.2055,
      "p99_ms": 0.5674,
      "total_ms": 2.2714
    },
    {
      "avg_ms": 0.0126,
      "count": 19,
      "last_ms": 0.0114,
      "max_ms": 0.0157,
      "min_ms": 0.0106,
      "name": "toolctx.plan_trace.snap_targets.structural_signature",
      "p50_ms": 0.0122,
      "p90_ms": 0.0138,
      "p95_ms": 0.0153,
      "p99_ms": 0.0157,
      "total_ms": 0.2386
    },
    {
      "avg_ms": 0.0261,
      "count": 19,
      "last_ms": 0.0138,
      "max_ms": 0.0476,
      "min_ms": 0.0129,
      "name": "toolctx.scene_cache.snap.near_query.total",
      "p50_ms": 0.0147,
      "p90_ms": 0.0405,
      "p95_ms": 0.0412,
      "p99_ms": 0.0476,
      "total_ms": 0.4962
    },
    {
      "avg_ms": 0.0003,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0005,
      "min_ms": 0.0002,
      "name": "toolctx.snap.manager.providers",
      "p50_ms": 0.0003,
      "p90_ms": 0.0005,
      "p95_ms": 0.0005,
      "p99_ms": 0.0005,
      "total_ms": 0.0066
    },
    {
      "avg_ms": 0.0397,
      "count": 19,
      "last_ms": 0.0338,
      "max_ms": 0.0977,
      "min_ms": 0.0331,
      "name": "toolctx.snap.manager.targets_to_results",
      "p50_ms": 0.0363,
      "p90_ms": 0.0415,
      "p95_ms": 0.0417,
      "p99_ms": 0.0977,
      "total_ms": 0.7546
    },
    {
      "avg_ms": 0.001,
      "count": 19,
      "last_ms": 0.0004,
      "max_ms": 0.0128,
      "min_ms": 0.0003,
      "name": "toolctx.snap.targets_to_results.classify",
      "p50_ms": 0.0004,
      "p90_ms": 0.0005,
      "p95_ms": 0.0007,
      "p99_ms": 0.0128,
      "total_ms": 0.0197
    },
    {
      "avg_ms": 0.0011,
      "count": 19,
      "last_ms": 0.001,
      "max_ms": 0.0017,
      "min_ms": 0.0009,
      "name": "toolctx.snap.targets_to_results.curve_intersections",
      "p50_ms": 0.001,
      "p90_ms": 0.0013,
      "p95_ms": 0.0014,
      "p99_ms": 0.0017,
      "total_ms": 0.0209
    },
    {
      "avg_ms": 0.0025,
      "count": 19,
      "last_ms": 0.0003,
      "max_ms": 0.0376,
      "min_ms": 0.0002,
      "name": "toolctx.snap.targets_to_results.direct_snaps",
      "p50_ms": 0.0003,
      "p90_ms": 0.0005,
      "p95_ms": 0.0053,
      "p99_ms": 0.0376,
      "total_ms": 0.048
    },
    {
      "avg_ms": 0.0014,
      "count": 19,
      "last_ms": 0.0006,
      "max_ms": 0.0102,
      "min_ms": 0.0006,
      "name": "toolctx.snap.targets_to_results.segment_intersections",
      "p50_ms": 0.0009,
      "p90_ms": 0.0011,
      "p95_ms": 0.0014,
      "p99_ms": 0.0102,
      "total_ms": 0.0258
    },
    {
      "avg_ms": 0.034,
      "count": 19,
      "last_ms": 0.0285,
      "max_ms": 0.0914,
      "min_ms": 0.0278,
      "name": "toolctx.snap.targets_to_results.total",
      "p50_ms": 0.0304,
      "p90_ms": 0.0355,
      "p95_ms": 0.036,
      "p99_ms": 0.0914,
      "total_ms": 0.6454
    },
    {
      "avg_ms": 0.0094,
      "count": 18,
      "last_ms": 0.0074,
      "max_ms": 0.015,
      "min_ms": 0.0064,
      "name": "toolctx.plan_trace.cursor.project",
      "p50_ms": 0.0087,
      "p90_ms": 0.0124,
      "p95_ms": 0.0132,
      "p99_ms": 0.015,
      "total_ms": 0.1688
    },
    {
      "avg_ms": 1.6307,
      "count": 18,
      "last_ms": 1.6297,
      "max_ms": 2.228,
      "min_ms": 1.3508,
      "name": "toolctx.plan_trace.cursor.update",
      "p50_ms": 1.6098,
      "p90_ms": 1.8545,
      "p95_ms": 2.1005,
      "p99_ms": 2.228,
      "total_ms": 29.352
    },
    {
      "avg_ms": 0.462,
      "count": 17,
      "last_ms": 0.4363,
      "max_ms": 0.517,
      "min_ms": 0.4319,
      "name": "toolctx.plan_trace.cursor.actor_sync",
      "p50_ms": 0.4495,
      "p90_ms": 0.5137,
      "p95_ms": 0.5153,
      "p99_ms": 0.517,
      "total_ms": 7.8546
    },
    {
      "avg_ms": 0.0025,
      "count": 17,
      "last_ms": 0.0018,
      "max_ms": 0.0049,
      "min_ms": 0.0017,
      "name": "toolctx.plan_trace.cursor.constraint",
      "p50_ms": 0.0025,
      "p90_ms": 0.0027,
      "p95_ms": 0.0037,
      "p99_ms": 0.0049,
      "total_ms": 0.0422
    },
    {
      "avg_ms": 0.2296,
      "count": 17,
      "last_ms": 0.3709,
      "max_ms": 0.7868,
      "min_ms": 0.023,
      "name": "toolctx.plan_trace.cursor.pending_preview",
      "p50_ms": 0.0443,
      "p90_ms": 0.44,
      "p95_ms": 0.491,
      "p99_ms": 0.7868,
      "total_ms": 3.9035
    }
  ],
  "top_p95_ms": [
    {
      "avg_ms": 6.9785,
      "count": 9,
      "last_ms": 23.0537,
      "max_ms": 30.796,
      "min_ms": 0.5969,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion",
      "p50_ms": 0.8692,
      "p90_ms": 23.0537,
      "p95_ms": 30.796,
      "p99_ms": 30.796,
      "total_ms": 62.8066
    },
    {
      "avg_ms": 4.5084,
      "count": 34,
      "last_ms": 1.8349,
      "max_ms": 15.2142,
      "min_ms": 0.1324,
      "name": "toolctx.plan_trace.event.total",
      "p50_ms": 3.196,
      "p90_ms": 10.058,
      "p95_ms": 11.2207,
      "p99_ms": 15.2142,
      "total_ms": 153.2844
    },
    {
      "avg_ms": 5.121,
      "count": 29,
      "last_ms": 5.5174,
      "max_ms": 15.2078,
      "min_ms": 2.5527,
      "name": "toolctx.plan_trace.event.mouse_press.total",
      "p50_ms": 3.4956,
      "p90_ms": 10.0516,
      "p95_ms": 11.2197,
      "p99_ms": 15.2078,
      "total_ms": 148.5094
    },
    {
      "avg_ms": 6.3866,
      "count": 17,
      "last_ms": 5.3968,
      "max_ms": 15.0771,
      "min_ms": 2.7978,
      "name": "toolctx.plan_trace.event.mouse_press.draw_press",
      "p50_ms": 3.6507,
      "p90_ms": 11.0839,
      "p95_ms": 11.0861,
      "p99_ms": 15.0771,
      "total_ms": 108.5714
    },
    {
      "avg_ms": 6.3646,
      "count": 17,
      "last_ms": 5.3849,
      "max_ms": 15.0627,
      "min_ms": 2.7909,
      "name": "toolctx.plan_trace.draw_press.total",
      "p50_ms": 3.6426,
      "p90_ms": 10.8845,
      "p95_ms": 11.0704,
      "p99_ms": 15.0627,
      "total_ms": 108.1976
    },
    {
      "avg_ms": 2.616,
      "count": 12,
      "last_ms": 8.0904,
      "max_ms": 12.0299,
      "min_ms": 0.1018,
      "name": "toolctx.plan_trace.sketch.compile_kernel",
      "p50_ms": 0.6287,
      "p90_ms": 8.0904,
      "p95_ms": 8.0904,
      "p99_ms": 12.0299,
      "total_ms": 31.3918
    },
    {
      "avg_ms": 4.5198,
      "count": 14,
      "last_ms": 7.1034,
      "max_ms": 12.3375,
      "min_ms": 1.1532,
      "name": "toolctx.plan_trace.draw_press.rectangle",
      "p50_ms": 1.664,
      "p90_ms": 7.9318,
      "p95_ms": 7.9318,
      "p99_ms": 12.3375,
      "total_ms": 63.2776
    },
    {
      "avg_ms": 3.81,
      "count": 12,
      "last_ms": 2.964,
      "max_ms": 9.1405,
      "min_ms": 2.3228,
      "name": "toolctx.plan_trace.lifecycle.open",
      "p50_ms": 3.2968,
      "p90_ms": 5.834,
      "p95_ms": 5.834,
      "p99_ms": 9.1405,
      "total_ms": 45.7195
    },
    {
      "avg_ms": 3.0434,
      "count": 12,
      "last_ms": 4.0603,
      "max_ms": 4.0603,
      "min_ms": 2.4633,
      "name": "toolctx.plan_trace.surface.pick_press",
      "p50_ms": 2.7298,
      "p90_ms": 4.0364,
      "p95_ms": 4.0364,
      "p99_ms": 4.0603,
      "total_ms": 36.521
    },
    {
      "avg_ms": 3.9423,
      "count": 1,
      "last_ms": 3.9423,
      "max_ms": 3.9423,
      "min_ms": 3.9423,
      "name": "toolctx.plan_trace.drag.resolve_positions.total",
      "p50_ms": 3.9423,
      "p90_ms": 3.9423,
      "p95_ms": 3.9423,
      "p99_ms": 3.9423,
      "total_ms": 3.9423
    },
    {
      "avg_ms": 1.1988,
      "count": 28,
      "last_ms": 1.2606,
      "max_ms": 3.4353,
      "min_ms": 0.088,
      "name": "sketch.compile.total",
      "p50_ms": 0.6215,
      "p90_ms": 3.2075,
      "p95_ms": 3.396,
      "p99_ms": 3.4353,
      "total_ms": 33.5659
    },
    {
      "avg_ms": 1.0571,
      "count": 28,
      "last_ms": 1.1582,
      "max_ms": 3.2867,
      "min_ms": 0.0206,
      "name": "sketch.compile.solve_faces",
      "p50_ms": 0.4848,
      "p90_ms": 2.9107,
      "p95_ms": 3.2813,
      "p99_ms": 3.2867,
      "total_ms": 29.5987
    },
    {
      "avg_ms": 2.0933,
      "count": 2,
      "last_ms": 2.9616,
      "max_ms": 2.9616,
      "min_ms": 1.225,
      "name": "toolctx.plan_trace.draw_press.line",
      "p50_ms": 1.225,
      "p90_ms": 2.9616,
      "p95_ms": 2.9616,
      "p99_ms": 2.9616,
      "total_ms": 4.1866
    },
    {
      "avg_ms": 0.6699,
      "count": 25,
      "last_ms": 0.7524,
      "max_ms": 2.6308,
      "min_ms": 0.0841,
      "name": "sketch.face_solver.build_faces",
      "p50_ms": 0.1572,
      "p90_ms": 2.4988,
      "p95_ms": 2.5496,
      "p99_ms": 2.6308,
      "total_ms": 16.7476
    },
    {
      "avg_ms": 2.2882,
      "count": 1,
      "last_ms": 2.2882,
      "max_ms": 2.2882,
      "min_ms": 2.2882,
      "name": "toolctx.plan_trace.event.mouse_move.total",
      "p50_ms": 2.2882,
      "p90_ms": 2.2882,
      "p95_ms": 2.2882,
      "p99_ms": 2.2882,
      "total_ms": 2.2882
    },
    {
      "avg_ms": 1.6307,
      "count": 18,
      "last_ms": 1.6297,
      "max_ms": 2.228,
      "min_ms": 1.3508,
      "name": "toolctx.plan_trace.cursor.update",
      "p50_ms": 1.6098,
      "p90_ms": 1.8545,
      "p95_ms": 2.1005,
      "p99_ms": 2.228,
      "total_ms": 29.352
    },
    {
      "avg_ms": 1.9501,
      "count": 1,
      "last_ms": 1.9501,
      "max_ms": 1.9501,
      "min_ms": 1.9501,
      "name": "toolctx.plan_trace.event.mouse_move.update_cursor",
      "p50_ms": 1.9501,
      "p90_ms": 1.9501,
      "p95_ms": 1.9501,
      "p99_ms": 1.9501,
      "total_ms": 1.9501
    },
    {
      "avg_ms": 1.8304,
      "count": 1,
      "last_ms": 1.8304,
      "max_ms": 1.8304,
      "min_ms": 1.8304,
      "name": "toolctx.plan_trace.drag.cursor_actor",
      "p50_ms": 1.8304,
      "p90_ms": 1.8304,
      "p95_ms": 1.8304,
      "p99_ms": 1.8304,
      "total_ms": 1.8304
    },
    {
      "avg_ms": 1.8231,
      "count": 1,
      "last_ms": 1.8231,
      "max_ms": 1.8231,
      "min_ms": 1.8231,
      "name": "toolctx.plan_trace.event.key_press.total",
      "p50_ms": 1.8231,
      "p90_ms": 1.8231,
      "p95_ms": 1.8231,
      "p99_ms": 1.8231,
      "total_ms": 1.8231
    },
    {
      "avg_ms": 1.5128,
      "count": 3,
      "last_ms": 1.4165,
      "max_ms": 1.5832,
      "min_ms": 1.4165,
      "name": "toolctx.plan_trace.native.select.total",
      "p50_ms": 1.5386,
      "p90_ms": 1.5832,
      "p95_ms": 1.5832,
      "p99_ms": 1.5832,
      "total_ms": 4.5383
    },
    {
      "avg_ms": 1.0606,
      "count": 3,
      "last_ms": 0.9246,
      "max_ms": 1.4801,
      "min_ms": 0.7771,
      "name": "toolctx.plan_trace.motif.union_footprint",
      "p50_ms": 0.9246,
      "p90_ms": 1.4801,
      "p95_ms": 1.4801,
      "p99_ms": 1.4801,
      "total_ms": 3.1818
    },
    {
      "avg_ms": 1.4687,
      "count": 1,
      "last_ms": 1.4687,
      "max_ms": 1.4687,
      "min_ms": 1.4687,
      "name": "toolctx.plan_trace.draw_press.place_point",
      "p50_ms": 1.4687,
      "p90_ms": 1.4687,
      "p95_ms": 1.4687,
      "p99_ms": 1.4687,
      "total_ms": 1.4687
    },
    {
      "avg_ms": 1.3705,
      "count": 1,
      "last_ms": 1.3705,
      "max_ms": 1.3705,
      "min_ms": 1.3705,
      "name": "toolctx.plan_trace.drag.sync_moved_points",
      "p50_ms": 1.3705,
      "p90_ms": 1.3705,
      "p95_ms": 1.3705,
      "p99_ms": 1.3705,
      "total_ms": 1.3705
    },
    {
      "avg_ms": 0.5722,
      "count": 57,
      "last_ms": 0.3321,
      "max_ms": 5.3946,
      "min_ms": 0.2669,
      "name": "toolctx.plan_trace.render",
      "p50_ms": 0.4241,
      "p90_ms": 0.6839,
      "p95_ms": 0.919,
      "p99_ms": 1.1029,
      "total_ms": 32.6154
    },
    {
      "avg_ms": 0.7251,
      "count": 1,
      "last_ms": 0.7251,
      "max_ms": 0.7251,
      "min_ms": 0.7251,
      "name": "toolctx.plan_trace.cursor.modify_fast_actor_sync",
      "p50_ms": 0.7251,
      "p90_ms": 0.7251,
      "p95_ms": 0.7251,
      "p99_ms": 0.7251,
      "total_ms": 0.7251
    },
    {
      "avg_ms": 0.6293,
      "count": 1,
      "last_ms": 0.6293,
      "max_ms": 0.6293,
      "min_ms": 0.6293,
      "name": "toolctx.plan_trace.drag.smart_snap",
      "p50_ms": 0.6293,
      "p90_ms": 0.6293,
      "p95_ms": 0.6293,
      "p99_ms": 0.6293,
      "total_ms": 0.6293
    },
    {
      "avg_ms": 0.4204,
      "count": 19,
      "last_ms": 0.3615,
      "max_ms": 0.7059,
      "min_ms": 0.3615,
      "name": "toolctx.plan_trace.cursor.register_cursor",
      "p50_ms": 0.3842,
      "p90_ms": 0.443,
      "p95_ms": 0.6246,
      "p99_ms": 0.7059,
      "total_ms": 7.9877
    },
    {
      "avg_ms": 0.4457,
      "count": 12,
      "last_ms": 0.4937,
      "max_ms": 0.5914,
      "min_ms": 0.0313,
      "name": "toolctx.plan_trace.sketch.actor_visual_sync",
      "p50_ms": 0.4846,
      "p90_ms": 0.587,
      "p95_ms": 0.587,
      "p99_ms": 0.5914,
      "total_ms": 5.3487
    },
    {
      "avg_ms": 0.2024,
      "count": 56,
      "last_ms": 0.2922,
      "max_ms": 1.6682,
      "min_ms": 0.0051,
      "name": "toolctx.plan2d.actor_visuals.full_interaction",
      "p50_ms": 0.1518,
      "p90_ms": 0.4524,
      "p95_ms": 0.5369,
      "p99_ms": 1.0432,
      "total_ms": 11.3329
    },
    {
      "avg_ms": 0.462,
      "count": 17,
      "last_ms": 0.4363,
      "max_ms": 0.517,
      "min_ms": 0.4319,
      "name": "toolctx.plan_trace.cursor.actor_sync",
      "p50_ms": 0.4495,
      "p90_ms": 0.5137,
      "p95_ms": 0.5153,
      "p99_ms": 0.517,
      "total_ms": 7.8546
    },
    {
      "avg_ms": 0.2296,
      "count": 17,
      "last_ms": 0.3709,
      "max_ms": 0.7868,
      "min_ms": 0.023,
      "name": "toolctx.plan_trace.cursor.pending_preview",
      "p50_ms": 0.0443,
      "p90_ms": 0.44,
      "p95_ms": 0.491,
      "p99_ms": 0.7868,
      "total_ms": 3.9035
    },
    {
      "avg_ms": 0.2593,
      "count": 17,
      "last_ms": 0.2211,
      "max_ms": 0.7154,
      "min_ms": 0.1892,
      "name": "toolctx.plan_trace.cursor.targets",
      "p50_ms": 0.2195,
      "p90_ms": 0.2592,
      "p95_ms": 0.3994,
      "p99_ms": 0.7154,
      "total_ms": 4.4081
    },
    {
      "avg_ms": 0.3762,
      "count": 1,
      "last_ms": 0.3762,
      "max_ms": 0.3762,
      "min_ms": 0.3762,
      "name": "toolctx.plan_trace.cursor.modify_local_snap",
      "p50_ms": 0.3762,
      "p90_ms": 0.3762,
      "p95_ms": 0.3762,
      "p99_ms": 0.3762,
      "total_ms": 0.3762
    },
    {
      "avg_ms": 0.2795,
      "count": 19,
      "last_ms": 0.2221,
      "max_ms": 0.3549,
      "min_ms": 0.2221,
      "name": "toolctx.plan2d.smart_snap.total",
      "p50_ms": 0.2849,
      "p90_ms": 0.3201,
      "p95_ms": 0.3512,
      "p99_ms": 0.3549,
      "total_ms": 5.311
    },
    {
      "avg_ms": 0.2961,
      "count": 17,
      "last_ms": 0.2411,
      "max_ms": 0.3809,
      "min_ms": 0.2411,
      "name": "toolctx.plan_trace.cursor.smart_snap",
      "p50_ms": 0.3052,
      "p90_ms": 0.3391,
      "p95_ms": 0.3439,
      "p99_ms": 0.3809,
      "total_ms": 5.0341
    },
    {
      "avg_ms": 0.335,
      "count": 1,
      "last_ms": 0.335,
      "max_ms": 0.335,
      "min_ms": 0.335,
      "name": "toolctx.plan_trace.cursor.modify_near_targets",
      "p50_ms": 0.335,
      "p90_ms": 0.335,
      "p95_ms": 0.335,
      "p99_ms": 0.335,
      "total_ms": 0.335
    },
    {
      "avg_ms": 0.134,
      "count": 28,
      "last_ms": 0.1403,
      "max_ms": 0.594,
      "min_ms": 0.0041,
      "name": "sketch.face_solver.source_curves",
      "p50_ms": 0.1082,
      "p90_ms": 0.2316,
      "p95_ms": 0.2685,
      "p99_ms": 0.594,
      "total_ms": 3.7518
    },
    {
      "avg_ms": 0.1177,
      "count": 27,
      "last_ms": 0.121,
      "max_ms": 0.281,
      "min_ms": 0.0408,
      "name": "sketch.face_solver.polygonize",
      "p50_ms": 0.1083,
      "p90_ms": 0.1992,
      "p95_ms": 0.2178,
      "p99_ms": 0.281,
      "total_ms": 3.1782
    },
    {
      "avg_ms": 0.1195,
      "count": 19,
      "last_ms": 0.0743,
      "max_ms": 0.5674,
      "min_ms": 0.0709,
      "name": "toolctx.plan_trace.snap_targets.build_live_targets",
      "p50_ms": 0.0781,
      "p90_ms": 0.1431,
      "p95_ms": 0.2055,
      "p99_ms": 0.5674,
      "total_ms": 2.2714
    },
    {
      "avg_ms": 0.1414,
      "count": 3,
      "last_ms": 0.1259,
      "max_ms": 0.169,
      "min_ms": 0.1259,
      "name": "toolctx.plan_trace.event.mouse_release.total",
      "p50_ms": 0.1292,
      "p90_ms": 0.169,
      "p95_ms": 0.169,
      "p99_ms": 0.169,
      "total_ms": 0.4242
    },
    {
      "avg_ms": 0.0709,
      "count": 25,
      "last_ms": 0.0707,
      "max_ms": 0.1687,
      "min_ms": 0.0304,
      "name": "sketch.face_solver.containment",
      "p50_ms": 0.0384,
      "p90_ms": 0.1599,
      "p95_ms": 0.1685,
      "p99_ms": 0.1687,
      "total_ms": 1.7723
    },
    {
      "avg_ms": 0.121,
      "count": 19,
      "last_ms": 0.095,
      "max_ms": 0.1628,
      "min_ms": 0.0926,
      "name": "toolctx.plan2d.smart_snap.manager",
      "p50_ms": 0.1246,
      "p90_ms": 0.1403,
      "p95_ms": 0.1602,
      "p99_ms": 0.1628,
      "total_ms": 2.2991
    },
    {
      "avg_ms": 0.1263,
      "count": 19,
      "last_ms": 0.1073,
      "max_ms": 0.1715,
      "min_ms": 0.1002,
      "name": "toolctx.plan2d.smart_snap.alignment",
      "p50_ms": 0.1282,
      "p90_ms": 0.1528,
      "p95_ms": 0.158,
      "p99_ms": 0.1715,
      "total_ms": 2.4006
    },
    {
      "avg_ms": 0.1283,
      "count": 12,
      "last_ms": 0.0888,
      "max_ms": 0.5005,
      "min_ms": 0.0835,
      "name": "toolctx.plan_trace.lifecycle.open.scene_cache_rebuild",
      "p50_ms": 0.0935,
      "p90_ms": 0.1255,
      "p95_ms": 0.1255,
      "p99_ms": 0.5005,
      "total_ms": 1.5394
    },
    {
      "avg_ms": 0.0767,
      "count": 19,
      "last_ms": 0.0663,
      "max_ms": 0.1139,
      "min_ms": 0.0644,
      "name": "toolctx.plan_trace.snap.near_query.total",
      "p50_ms": 0.0719,
      "p90_ms": 0.0908,
      "p95_ms": 0.0999,
      "p99_ms": 0.1139,
      "total_ms": 1.4582
    },
    {
      "avg_ms": 0.0857,
      "count": 12,
      "last_ms": 0.0813,
      "max_ms": 0.1159,
      "min_ms": 0.0761,
      "name": "toolctx.scene_cache.rebuild.total",
      "p50_ms": 0.0835,
      "p90_ms": 0.0961,
      "p95_ms": 0.0961,
      "p99_ms": 0.1159,
      "total_ms": 1.0285
    },
    {
      "avg_ms": 0.0396,
      "count": 19,
      "last_ms": 0.0335,
      "max_ms": 0.0909,
      "min_ms": 0.0295,
      "name": "toolctx.plan2d.smart_snap.alignment.extra_cache",
      "p50_ms": 0.0346,
      "p90_ms": 0.0392,
      "p95_ms": 0.0779,
      "p99_ms": 0.0909,
      "total_ms": 0.7528
    },
    {
      "avg_ms": 0.0468,
      "count": 19,
      "last_ms": 0.0104,
      "max_ms": 0.486,
      "min_ms": 0.0093,
      "name": "toolctx.plan_trace.snap_targets.build.anchor",
      "p50_ms": 0.0225,
      "p90_ms": 0.0477,
      "p95_ms": 0.0654,
      "p99_ms": 0.486,
      "total_ms": 0.8889
    },
    {
      "avg_ms": 0.0234,
      "count": 19,
      "last_ms": 0.0187,
      "max_ms": 0.0755,
      "min_ms": 0.0138,
      "name": "toolctx.plan2d.guide_cache.extra.build",
      "p50_ms": 0.0188,
      "p90_ms": 0.0234,
      "p95_ms": 0.0627,
      "p99_ms": 0.0755,
      "total_ms": 0.4445
    },
    {
      "avg_ms": 0.0886,
      "count": 19,
      "last_ms": 0.0346,
      "max_ms": 1.0731,
      "min_ms": 0.0266,
      "name": "toolctx.plan_trace.cursor.sync_actor_visuals",
      "p50_ms": 0.0341,
      "p90_ms": 0.0413,
      "p95_ms": 0.0559,
      "p99_ms": 1.0731,
      "total_ms": 1.6833
    },
    {
      "avg_ms": 0.0131,
      "count": 19,
      "last_ms": 0.017,
      "max_ms": 0.0443,
      "min_ms": 0.0004,
      "name": "toolctx.plan_trace.snap_targets.build.points",
      "p50_ms": 0.0152,
      "p90_ms": 0.0249,
      "p95_ms": 0.0433,
      "p99_ms": 0.0443,
      "total_ms": 0.2494
    },
    {
      "avg_ms": 0.0397,
      "count": 19,
      "last_ms": 0.0338,
      "max_ms": 0.0977,
      "min_ms": 0.0331,
      "name": "toolctx.snap.manager.targets_to_results",
      "p50_ms": 0.0363,
      "p90_ms": 0.0415,
      "p95_ms": 0.0417,
      "p99_ms": 0.0977,
      "total_ms": 0.7546
    },
    {
      "avg_ms": 0.0261,
      "count": 19,
      "last_ms": 0.0138,
      "max_ms": 0.0476,
      "min_ms": 0.0129,
      "name": "toolctx.scene_cache.snap.near_query.total",
      "p50_ms": 0.0147,
      "p90_ms": 0.0405,
      "p95_ms": 0.0412,
      "p99_ms": 0.0476,
      "total_ms": 0.4962
    },
    {
      "avg_ms": 0.0254,
      "count": 19,
      "last_ms": 0.0124,
      "max_ms": 0.0453,
      "min_ms": 0.0119,
      "name": "toolctx.plan2d.smart_snap.alignment.scene_cache",
      "p50_ms": 0.0139,
      "p90_ms": 0.04,
      "p95_ms": 0.0405,
      "p99_ms": 0.0453,
      "total_ms": 0.4821
    },
    {
      "avg_ms": 0.0197,
      "count": 19,
      "last_ms": 0.0157,
      "max_ms": 0.0412,
      "min_ms": 0.0156,
      "name": "toolctx.plan_trace.snap.build_screen_index",
      "p50_ms": 0.017,
      "p90_ms": 0.0223,
      "p95_ms": 0.0368,
      "p99_ms": 0.0412,
      "total_ms": 0.3736
    },
    {
      "avg_ms": 0.0313,
      "count": 12,
      "last_ms": 0.0287,
      "max_ms": 0.0427,
      "min_ms": 0.0264,
      "name": "toolctx.scene_cache.rebuild.collect_document_meshes",
      "p50_ms": 0.0309,
      "p90_ms": 0.0361,
      "p95_ms": 0.0361,
      "p99_ms": 0.0427,
      "total_ms": 0.3756
    },
    {
      "avg_ms": 0.034,
      "count": 19,
      "last_ms": 0.0285,
      "max_ms": 0.0914,
      "min_ms": 0.0278,
      "name": "toolctx.snap.targets_to_results.total",
      "p50_ms": 0.0304,
      "p90_ms": 0.0355,
      "p95_ms": 0.036,
      "p99_ms": 0.0914,
      "total_ms": 0.6454
    },
    {
      "avg_ms": 0.0184,
      "count": 28,
      "last_ms": 0.0179,
      "max_ms": 0.0377,
      "min_ms": 0.0097,
      "name": "sketch.compile.validation",
      "p50_ms": 0.0168,
      "p90_ms": 0.0273,
      "p95_ms": 0.0341,
      "p99_ms": 0.0377,
      "total_ms": 0.5153
    },
    {
      "avg_ms": 0.0044,
      "count": 19,
      "last_ms": 0.0005,
      "max_ms": 0.0398,
      "min_ms": 0.0004,
      "name": "toolctx.plan_trace.snap_targets.build.lines",
      "p50_ms": 0.0006,
      "p90_ms": 0.0008,
      "p95_ms": 0.0335,
      "p99_ms": 0.0398,
      "total_ms": 0.0835
    },
    {
      "avg_ms": 0.0146,
      "count": 28,
      "last_ms": 0.0069,
      "max_ms": 0.0322,
      "min_ms": 0.0032,
      "name": "sketch.compile.rebuild_polylines",
      "p50_ms": 0.0141,
      "p90_ms": 0.02,
      "p95_ms": 0.0279,
      "p99_ms": 0.0322,
      "total_ms": 0.4092
    }
  ],
  "top_total_ms": [
    {
      "avg_ms": 4.5084,
      "count": 34,
      "last_ms": 1.8349,
      "max_ms": 15.2142,
      "min_ms": 0.1324,
      "name": "toolctx.plan_trace.event.total",
      "p50_ms": 3.196,
      "p90_ms": 10.058,
      "p95_ms": 11.2207,
      "p99_ms": 15.2142,
      "total_ms": 153.2844
    },
    {
      "avg_ms": 5.121,
      "count": 29,
      "last_ms": 5.5174,
      "max_ms": 15.2078,
      "min_ms": 2.5527,
      "name": "toolctx.plan_trace.event.mouse_press.total",
      "p50_ms": 3.4956,
      "p90_ms": 10.0516,
      "p95_ms": 11.2197,
      "p99_ms": 15.2078,
      "total_ms": 148.5094
    },
    {
      "avg_ms": 6.3866,
      "count": 17,
      "last_ms": 5.3968,
      "max_ms": 15.0771,
      "min_ms": 2.7978,
      "name": "toolctx.plan_trace.event.mouse_press.draw_press",
      "p50_ms": 3.6507,
      "p90_ms": 11.0839,
      "p95_ms": 11.0861,
      "p99_ms": 15.0771,
      "total_ms": 108.5714
    },
    {
      "avg_ms": 6.3646,
      "count": 17,
      "last_ms": 5.3849,
      "max_ms": 15.0627,
      "min_ms": 2.7909,
      "name": "toolctx.plan_trace.draw_press.total",
      "p50_ms": 3.6426,
      "p90_ms": 10.8845,
      "p95_ms": 11.0704,
      "p99_ms": 15.0627,
      "total_ms": 108.1976
    },
    {
      "avg_ms": 4.5198,
      "count": 14,
      "last_ms": 7.1034,
      "max_ms": 12.3375,
      "min_ms": 1.1532,
      "name": "toolctx.plan_trace.draw_press.rectangle",
      "p50_ms": 1.664,
      "p90_ms": 7.9318,
      "p95_ms": 7.9318,
      "p99_ms": 12.3375,
      "total_ms": 63.2776
    },
    {
      "avg_ms": 6.9785,
      "count": 9,
      "last_ms": 23.0537,
      "max_ms": 30.796,
      "min_ms": 0.5969,
      "name": "plan_trace.apply.mesh.boolean_ready_extrusion",
      "p50_ms": 0.8692,
      "p90_ms": 23.0537,
      "p95_ms": 30.796,
      "p99_ms": 30.796,
      "total_ms": 62.8066
    },
    {
      "avg_ms": 3.81,
      "count": 12,
      "last_ms": 2.964,
      "max_ms": 9.1405,
      "min_ms": 2.3228,
      "name": "toolctx.plan_trace.lifecycle.open",
      "p50_ms": 3.2968,
      "p90_ms": 5.834,
      "p95_ms": 5.834,
      "p99_ms": 9.1405,
      "total_ms": 45.7195
    },
    {
      "avg_ms": 3.0434,
      "count": 12,
      "last_ms": 4.0603,
      "max_ms": 4.0603,
      "min_ms": 2.4633,
      "name": "toolctx.plan_trace.surface.pick_press",
      "p50_ms": 2.7298,
      "p90_ms": 4.0364,
      "p95_ms": 4.0364,
      "p99_ms": 4.0603,
      "total_ms": 36.521
    },
    {
      "avg_ms": 1.1988,
      "count": 28,
      "last_ms": 1.2606,
      "max_ms": 3.4353,
      "min_ms": 0.088,
      "name": "sketch.compile.total",
      "p50_ms": 0.6215,
      "p90_ms": 3.2075,
      "p95_ms": 3.396,
      "p99_ms": 3.4353,
      "total_ms": 33.5659
    },
    {
      "avg_ms": 0.5722,
      "count": 57,
      "last_ms": 0.3321,
      "max_ms": 5.3946,
      "min_ms": 0.2669,
      "name": "toolctx.plan_trace.render",
      "p50_ms": 0.4241,
      "p90_ms": 0.6839,
      "p95_ms": 0.919,
      "p99_ms": 1.1029,
      "total_ms": 32.6154
    },
    {
      "avg_ms": 2.616,
      "count": 12,
      "last_ms": 8.0904,
      "max_ms": 12.0299,
      "min_ms": 0.1018,
      "name": "toolctx.plan_trace.sketch.compile_kernel",
      "p50_ms": 0.6287,
      "p90_ms": 8.0904,
      "p95_ms": 8.0904,
      "p99_ms": 12.0299,
      "total_ms": 31.3918
    },
    {
      "avg_ms": 1.0571,
      "count": 28,
      "last_ms": 1.1582,
      "max_ms": 3.2867,
      "min_ms": 0.0206,
      "name": "sketch.compile.solve_faces",
      "p50_ms": 0.4848,
      "p90_ms": 2.9107,
      "p95_ms": 3.2813,
      "p99_ms": 3.2867,
      "total_ms": 29.5987
    },
    {
      "avg_ms": 1.6307,
      "count": 18,
      "last_ms": 1.6297,
      "max_ms": 2.228,
      "min_ms": 1.3508,
      "name": "toolctx.plan_trace.cursor.update",
      "p50_ms": 1.6098,
      "p90_ms": 1.8545,
      "p95_ms": 2.1005,
      "p99_ms": 2.228,
      "total_ms": 29.352
    },
    {
      "avg_ms": 0.6699,
      "count": 25,
      "last_ms": 0.7524,
      "max_ms": 2.6308,
      "min_ms": 0.0841,
      "name": "sketch.face_solver.build_faces",
      "p50_ms": 0.1572,
      "p90_ms": 2.4988,
      "p95_ms": 2.5496,
      "p99_ms": 2.6308,
      "total_ms": 16.7476
    },
    {
      "avg_ms": 0.2024,
      "count": 56,
      "last_ms": 0.2922,
      "max_ms": 1.6682,
      "min_ms": 0.0051,
      "name": "toolctx.plan2d.actor_visuals.full_interaction",
      "p50_ms": 0.1518,
      "p90_ms": 0.4524,
      "p95_ms": 0.5369,
      "p99_ms": 1.0432,
      "total_ms": 11.3329
    },
    {
      "avg_ms": 0.4204,
      "count": 19,
      "last_ms": 0.3615,
      "max_ms": 0.7059,
      "min_ms": 0.3615,
      "name": "toolctx.plan_trace.cursor.register_cursor",
      "p50_ms": 0.3842,
      "p90_ms": 0.443,
      "p95_ms": 0.6246,
      "p99_ms": 0.7059,
      "total_ms": 7.9877
    },
    {
      "avg_ms": 0.462,
      "count": 17,
      "last_ms": 0.4363,
      "max_ms": 0.517,
      "min_ms": 0.4319,
      "name": "toolctx.plan_trace.cursor.actor_sync",
      "p50_ms": 0.4495,
      "p90_ms": 0.5137,
      "p95_ms": 0.5153,
      "p99_ms": 0.517,
      "total_ms": 7.8546
    },
    {
      "avg_ms": 0.4457,
      "count": 12,
      "last_ms": 0.4937,
      "max_ms": 0.5914,
      "min_ms": 0.0313,
      "name": "toolctx.plan_trace.sketch.actor_visual_sync",
      "p50_ms": 0.4846,
      "p90_ms": 0.587,
      "p95_ms": 0.587,
      "p99_ms": 0.5914,
      "total_ms": 5.3487
    },
    {
      "avg_ms": 0.2795,
      "count": 19,
      "last_ms": 0.2221,
      "max_ms": 0.3549,
      "min_ms": 0.2221,
      "name": "toolctx.plan2d.smart_snap.total",
      "p50_ms": 0.2849,
      "p90_ms": 0.3201,
      "p95_ms": 0.3512,
      "p99_ms": 0.3549,
      "total_ms": 5.311
    },
    {
      "avg_ms": 0.2961,
      "count": 17,
      "last_ms": 0.2411,
      "max_ms": 0.3809,
      "min_ms": 0.2411,
      "name": "toolctx.plan_trace.cursor.smart_snap",
      "p50_ms": 0.3052,
      "p90_ms": 0.3391,
      "p95_ms": 0.3439,
      "p99_ms": 0.3809,
      "total_ms": 5.0341
    },
    {
      "avg_ms": 1.5128,
      "count": 3,
      "last_ms": 1.4165,
      "max_ms": 1.5832,
      "min_ms": 1.4165,
      "name": "toolctx.plan_trace.native.select.total",
      "p50_ms": 1.5386,
      "p90_ms": 1.5832,
      "p95_ms": 1.5832,
      "p99_ms": 1.5832,
      "total_ms": 4.5383
    },
    {
      "avg_ms": 0.2593,
      "count": 17,
      "last_ms": 0.2211,
      "max_ms": 0.7154,
      "min_ms": 0.1892,
      "name": "toolctx.plan_trace.cursor.targets",
      "p50_ms": 0.2195,
      "p90_ms": 0.2592,
      "p95_ms": 0.3994,
      "p99_ms": 0.7154,
      "total_ms": 4.4081
    },
    {
      "avg_ms": 2.0933,
      "count": 2,
      "last_ms": 2.9616,
      "max_ms": 2.9616,
      "min_ms": 1.225,
      "name": "toolctx.plan_trace.draw_press.line",
      "p50_ms": 1.225,
      "p90_ms": 2.9616,
      "p95_ms": 2.9616,
      "p99_ms": 2.9616,
      "total_ms": 4.1866
    },
    {
      "avg_ms": 3.9423,
      "count": 1,
      "last_ms": 3.9423,
      "max_ms": 3.9423,
      "min_ms": 3.9423,
      "name": "toolctx.plan_trace.drag.resolve_positions.total",
      "p50_ms": 3.9423,
      "p90_ms": 3.9423,
      "p95_ms": 3.9423,
      "p99_ms": 3.9423,
      "total_ms": 3.9423
    },
    {
      "avg_ms": 0.2296,
      "count": 17,
      "last_ms": 0.3709,
      "max_ms": 0.7868,
      "min_ms": 0.023,
      "name": "toolctx.plan_trace.cursor.pending_preview",
      "p50_ms": 0.0443,
      "p90_ms": 0.44,
      "p95_ms": 0.491,
      "p99_ms": 0.7868,
      "total_ms": 3.9035
    },
    {
      "avg_ms": 0.134,
      "count": 28,
      "last_ms": 0.1403,
      "max_ms": 0.594,
      "min_ms": 0.0041,
      "name": "sketch.face_solver.source_curves",
      "p50_ms": 0.1082,
      "p90_ms": 0.2316,
      "p95_ms": 0.2685,
      "p99_ms": 0.594,
      "total_ms": 3.7518
    },
    {
      "avg_ms": 1.0606,
      "count": 3,
      "last_ms": 0.9246,
      "max_ms": 1.4801,
      "min_ms": 0.7771,
      "name": "toolctx.plan_trace.motif.union_footprint",
      "p50_ms": 0.9246,
      "p90_ms": 1.4801,
      "p95_ms": 1.4801,
      "p99_ms": 1.4801,
      "total_ms": 3.1818
    },
    {
      "avg_ms": 0.1177,
      "count": 27,
      "last_ms": 0.121,
      "max_ms": 0.281,
      "min_ms": 0.0408,
      "name": "sketch.face_solver.polygonize",
      "p50_ms": 0.1083,
      "p90_ms": 0.1992,
      "p95_ms": 0.2178,
      "p99_ms": 0.281,
      "total_ms": 3.1782
    },
    {
      "avg_ms": 0.1263,
      "count": 19,
      "last_ms": 0.1073,
      "max_ms": 0.1715,
      "min_ms": 0.1002,
      "name": "toolctx.plan2d.smart_snap.alignment",
      "p50_ms": 0.1282,
      "p90_ms": 0.1528,
      "p95_ms": 0.158,
      "p99_ms": 0.1715,
      "total_ms": 2.4006
    },
    {
      "avg_ms": 0.121,
      "count": 19,
      "last_ms": 0.095,
      "max_ms": 0.1628,
      "min_ms": 0.0926,
      "name": "toolctx.plan2d.smart_snap.manager",
      "p50_ms": 0.1246,
      "p90_ms": 0.1403,
      "p95_ms": 0.1602,
      "p99_ms": 0.1628,
      "total_ms": 2.2991
    },
    {
      "avg_ms": 2.2882,
      "count": 1,
      "last_ms": 2.2882,
      "max_ms": 2.2882,
      "min_ms": 2.2882,
      "name": "toolctx.plan_trace.event.mouse_move.total",
      "p50_ms": 2.2882,
      "p90_ms": 2.2882,
      "p95_ms": 2.2882,
      "p99_ms": 2.2882,
      "total_ms": 2.2882
    },
    {
      "avg_ms": 0.1195,
      "count": 19,
      "last_ms": 0.0743,
      "max_ms": 0.5674,
      "min_ms": 0.0709,
      "name": "toolctx.plan_trace.snap_targets.build_live_targets",
      "p50_ms": 0.0781,
      "p90_ms": 0.1431,
      "p95_ms": 0.2055,
      "p99_ms": 0.5674,
      "total_ms": 2.2714
    },
    {
      "avg_ms": 1.9501,
      "count": 1,
      "last_ms": 1.9501,
      "max_ms": 1.9501,
      "min_ms": 1.9501,
      "name": "toolctx.plan_trace.event.mouse_move.update_cursor",
      "p50_ms": 1.9501,
      "p90_ms": 1.9501,
      "p95_ms": 1.9501,
      "p99_ms": 1.9501,
      "total_ms": 1.9501
    },
    {
      "avg_ms": 1.8304,
      "count": 1,
      "last_ms": 1.8304,
      "max_ms": 1.8304,
      "min_ms": 1.8304,
      "name": "toolctx.plan_trace.drag.cursor_actor",
      "p50_ms": 1.8304,
      "p90_ms": 1.8304,
      "p95_ms": 1.8304,
      "p99_ms": 1.8304,
      "total_ms": 1.8304
    },
    {
      "avg_ms": 1.8231,
      "count": 1,
      "last_ms": 1.8231,
      "max_ms": 1.8231,
      "min_ms": 1.8231,
      "name": "toolctx.plan_trace.event.key_press.total",
      "p50_ms": 1.8231,
      "p90_ms": 1.8231,
      "p95_ms": 1.8231,
      "p99_ms": 1.8231,
      "total_ms": 1.8231
    },
    {
      "avg_ms": 0.0709,
      "count": 25,
      "last_ms": 0.0707,
      "max_ms": 0.1687,
      "min_ms": 0.0304,
      "name": "sketch.face_solver.containment",
      "p50_ms": 0.0384,
      "p90_ms": 0.1599,
      "p95_ms": 0.1685,
      "p99_ms": 0.1687,
      "total_ms": 1.7723
    },
    {
      "avg_ms": 0.0886,
      "count": 19,
      "last_ms": 0.0346,
      "max_ms": 1.0731,
      "min_ms": 0.0266,
      "name": "toolctx.plan_trace.cursor.sync_actor_visuals",
      "p50_ms": 0.0341,
      "p90_ms": 0.0413,
      "p95_ms": 0.0559,
      "p99_ms": 1.0731,
      "total_ms": 1.6833
    },
    {
      "avg_ms": 0.1283,
      "count": 12,
      "last_ms": 0.0888,
      "max_ms": 0.5005,
      "min_ms": 0.0835,
      "name": "toolctx.plan_trace.lifecycle.open.scene_cache_rebuild",
      "p50_ms": 0.0935,
      "p90_ms": 0.1255,
      "p95_ms": 0.1255,
      "p99_ms": 0.5005,
      "total_ms": 1.5394
    },
    {
      "avg_ms": 1.4687,
      "count": 1,
      "last_ms": 1.4687,
      "max_ms": 1.4687,
      "min_ms": 1.4687,
      "name": "toolctx.plan_trace.draw_press.place_point",
      "p50_ms": 1.4687,
      "p90_ms": 1.4687,
      "p95_ms": 1.4687,
      "p99_ms": 1.4687,
      "total_ms": 1.4687
    },
    {
      "avg_ms": 0.0767,
      "count": 19,
      "last_ms": 0.0663,
      "max_ms": 0.1139,
      "min_ms": 0.0644,
      "name": "toolctx.plan_trace.snap.near_query.total",
      "p50_ms": 0.0719,
      "p90_ms": 0.0908,
      "p95_ms": 0.0999,
      "p99_ms": 0.1139,
      "total_ms": 1.4582
    },
    {
      "avg_ms": 1.3705,
      "count": 1,
      "last_ms": 1.3705,
      "max_ms": 1.3705,
      "min_ms": 1.3705,
      "name": "toolctx.plan_trace.drag.sync_moved_points",
      "p50_ms": 1.3705,
      "p90_ms": 1.3705,
      "p95_ms": 1.3705,
      "p99_ms": 1.3705,
      "total_ms": 1.3705
    },
    {
      "avg_ms": 0.0857,
      "count": 12,
      "last_ms": 0.0813,
      "max_ms": 0.1159,
      "min_ms": 0.0761,
      "name": "toolctx.scene_cache.rebuild.total",
      "p50_ms": 0.0835,
      "p90_ms": 0.0961,
      "p95_ms": 0.0961,
      "p99_ms": 0.1159,
      "total_ms": 1.0285
    },
    {
      "avg_ms": 0.0468,
      "count": 19,
      "last_ms": 0.0104,
      "max_ms": 0.486,
      "min_ms": 0.0093,
      "name": "toolctx.plan_trace.snap_targets.build.anchor",
      "p50_ms": 0.0225,
      "p90_ms": 0.0477,
      "p95_ms": 0.0654,
      "p99_ms": 0.486,
      "total_ms": 0.8889
    },
    {
      "avg_ms": 0.0397,
      "count": 19,
      "last_ms": 0.0338,
      "max_ms": 0.0977,
      "min_ms": 0.0331,
      "name": "toolctx.snap.manager.targets_to_results",
      "p50_ms": 0.0363,
      "p90_ms": 0.0415,
      "p95_ms": 0.0417,
      "p99_ms": 0.0977,
      "total_ms": 0.7546
    },
    {
      "avg_ms": 0.0396,
      "count": 19,
      "last_ms": 0.0335,
      "max_ms": 0.0909,
      "min_ms": 0.0295,
      "name": "toolctx.plan2d.smart_snap.alignment.extra_cache",
      "p50_ms": 0.0346,
      "p90_ms": 0.0392,
      "p95_ms": 0.0779,
      "p99_ms": 0.0909,
      "total_ms": 0.7528
    },
    {
      "avg_ms": 0.7251,
      "count": 1,
      "last_ms": 0.7251,
      "max_ms": 0.7251,
      "min_ms": 0.7251,
      "name": "toolctx.plan_trace.cursor.modify_fast_actor_sync",
      "p50_ms": 0.7251,
      "p90_ms": 0.7251,
      "p95_ms": 0.7251,
      "p99_ms": 0.7251,
      "total_ms": 0.7251
    },
    {
      "avg_ms": 0.034,
      "count": 19,
      "last_ms": 0.0285,
      "max_ms": 0.0914,
      "min_ms": 0.0278,
      "name": "toolctx.snap.targets_to_results.total",
      "p50_ms": 0.0304,
      "p90_ms": 0.0355,
      "p95_ms": 0.036,
      "p99_ms": 0.0914,
      "total_ms": 0.6454
    },
    {
      "avg_ms": 0.6293,
      "count": 1,
      "last_ms": 0.6293,
      "max_ms": 0.6293,
      "min_ms": 0.6293,
      "name": "toolctx.plan_trace.drag.smart_snap",
      "p50_ms": 0.6293,
      "p90_ms": 0.6293,
      "p95_ms": 0.6293,
      "p99_ms": 0.6293,
      "total_ms": 0.6293
    },
    {
      "avg_ms": 0.0184,
      "count": 28,
      "last_ms": 0.0179,
      "max_ms": 0.0377,
      "min_ms": 0.0097,
      "name": "sketch.compile.validation",
      "p50_ms": 0.0168,
      "p90_ms": 0.0273,
      "p95_ms": 0.0341,
      "p99_ms": 0.0377,
      "total_ms": 0.5153
    },
    {
      "avg_ms": 0.0261,
      "count": 19,
      "last_ms": 0.0138,
      "max_ms": 0.0476,
      "min_ms": 0.0129,
      "name": "toolctx.scene_cache.snap.near_query.total",
      "p50_ms": 0.0147,
      "p90_ms": 0.0405,
      "p95_ms": 0.0412,
      "p99_ms": 0.0476,
      "total_ms": 0.4962
    },
    {
      "avg_ms": 0.0254,
      "count": 19,
      "last_ms": 0.0124,
      "max_ms": 0.0453,
      "min_ms": 0.0119,
      "name": "toolctx.plan2d.smart_snap.alignment.scene_cache",
      "p50_ms": 0.0139,
      "p90_ms": 0.04,
      "p95_ms": 0.0405,
      "p99_ms": 0.0453,
      "total_ms": 0.4821
    },
    {
      "avg_ms": 0.0234,
      "count": 19,
      "last_ms": 0.0187,
      "max_ms": 0.0755,
      "min_ms": 0.0138,
      "name": "toolctx.plan2d.guide_cache.extra.build",
      "p50_ms": 0.0188,
      "p90_ms": 0.0234,
      "p95_ms": 0.0627,
      "p99_ms": 0.0755,
      "total_ms": 0.4445
    },
    {
      "avg_ms": 0.1414,
      "count": 3,
      "last_ms": 0.1259,
      "max_ms": 0.169,
      "min_ms": 0.1259,
      "name": "toolctx.plan_trace.event.mouse_release.total",
      "p50_ms": 0.1292,
      "p90_ms": 0.169,
      "p95_ms": 0.169,
      "p99_ms": 0.169,
      "total_ms": 0.4242
    },
    {
      "avg_ms": 0.0146,
      "count": 28,
      "last_ms": 0.0069,
      "max_ms": 0.0322,
      "min_ms": 0.0032,
      "name": "sketch.compile.rebuild_polylines",
      "p50_ms": 0.0141,
      "p90_ms": 0.02,
      "p95_ms": 0.0279,
      "p99_ms": 0.0322,
      "total_ms": 0.4092
    },
    {
      "avg_ms": 0.3762,
      "count": 1,
      "last_ms": 0.3762,
      "max_ms": 0.3762,
      "min_ms": 0.3762,
      "name": "toolctx.plan_trace.cursor.modify_local_snap",
      "p50_ms": 0.3762,
      "p90_ms": 0.3762,
      "p95_ms": 0.3762,
      "p99_ms": 0.3762,
      "total_ms": 0.3762
    },
    {
      "avg_ms": 0.0313,
      "count": 12,
      "last_ms": 0.0287,
      "max_ms": 0.0427,
      "min_ms": 0.0264,
      "name": "toolctx.scene_cache.rebuild.collect_document_meshes",
      "p50_ms": 0.0309,
      "p90_ms": 0.0361,
      "p95_ms": 0.0361,
      "p99_ms": 0.0427,
      "total_ms": 0.3756
    },
    {
      "avg_ms": 0.0197,
      "count": 19,
      "last_ms": 0.0157,
      "max_ms": 0.0412,
      "min_ms": 0.0156,
      "name": "toolctx.plan_trace.snap.build_screen_index",
      "p50_ms": 0.017,
      "p90_ms": 0.0223,
      "p95_ms": 0.0368,
      "p99_ms": 0.0412,
      "total_ms": 0.3736
    },
    {
      "avg_ms": 0.0127,
      "count": 28,
      "last_ms": 0.0009,
      "max_ms": 0.0497,
      "min_ms": 0.0006,
      "name": "sketch.compile.insert_line_intersections",
      "p50_ms": 0.0142,
      "p90_ms": 0.0202,
      "p95_ms": 0.0249,
      "p99_ms": 0.0497,
      "total_ms": 0.3556
    },
    {
      "avg_ms": 0.0125,
      "count": 28,
      "last_ms": 0.0085,
      "max_ms": 0.0295,
      "min_ms": 0.0012,
      "name": "sketch.compile.merge_duplicate_points",
      "p50_ms": 0.0116,
      "p90_ms": 0.0186,
      "p95_ms": 0.0195,
      "p99_ms": 0.0295,
      "total_ms": 0.3509
    },
    {
      "avg_ms": 0.335,
      "count": 1,
      "last_ms": 0.335,
      "max_ms": 0.335,
      "min_ms": 0.335,
      "name": "toolctx.plan_trace.cursor.modify_near_targets",
      "p50_ms": 0.335,
      "p90_ms": 0.335,
      "p95_ms": 0.335,
      "p99_ms": 0.335,
      "total_ms": 0.335
    }
  ],
  "values": {
    "toolctx.plan2d.actor_visuals.changed_last": 1,
    "toolctx.plan2d.actor_visuals.dirty_bridge_handles_last": 1,
    "toolctx.plan2d.actor_visuals.dirty_bridge_previews_last": 0,
    "toolctx.plan2d.actor_visuals.position_only_last": 0,
    "toolctx.plan2d.guide_cache.extra.points": 2,
    "toolctx.plan2d.guide_cache.extra.targets": 2,
    "toolctx.plan2d.guide_cache.scene.points": 0,
    "toolctx.plan2d.guide_cache.scene.targets": 0,
    "toolctx.plan2d.smart_snap.grid.distance_px": 0.0,
    "toolctx.plan2d.smart_snap.last_alignment_candidates": 1,
    "toolctx.plan_trace.diagnostic.enabled": 1,
    "toolctx.plan_trace.motif.union_footprint.cache_size": 1,
    "toolctx.plan_trace.motif.union_footprint.face_count": 1,
    "toolctx.plan_trace.snap.last_near_index_candidates": 0,
    "toolctx.plan_trace.snap.last_near_targets": 0,
    "toolctx.plan_trace.snap_targets.anchors": 1,
    "toolctx.plan_trace.snap_targets.arc_segments": 0,
    "toolctx.plan_trace.snap_targets.arcs": 0,
    "toolctx.plan_trace.snap_targets.bezier_segments": 0,
    "toolctx.plan_trace.snap_targets.beziers": 0,
    "toolctx.plan_trace.snap_targets.cached_total": 9,
    "toolctx.plan_trace.snap_targets.circles": 0,
    "toolctx.plan_trace.snap_targets.lines": 0,
    "toolctx.plan_trace.snap_targets.points": 1,
    "toolctx.plan_trace.snap_targets.total": 2,
    "toolctx.scene_cache.bounds": 0,
    "toolctx.scene_cache.extra_targets": 0,
    "toolctx.scene_cache.mesh.objects": 1,
    "toolctx.scene_cache.mesh.remaining_edge_budget": 3000,
    "toolctx.scene_cache.mesh.remaining_point_budget": 1200,
    "toolctx.scene_cache.mesh.sampled_unique_edges": 0,
    "toolctx.scene_cache.mesh.sampled_unique_points": 0,
    "toolctx.scene_cache.points": 0,
    "toolctx.scene_cache.segments": 0,
    "toolctx.scene_cache.snap.index_cells": 0,
    "toolctx.scene_cache.snap.index_fallback": 0,
    "toolctx.scene_cache.snap.index_targets": 0,
    "toolctx.scene_cache.snap.projection.has_camera": 0,
    "toolctx.scene_cache.snap.projection.has_owner_plotter": 0,
    "toolctx.scene_cache.snap.projection.has_viewport_plotter": 0,
    "toolctx.scene_cache.snap.projection_signature_changed": 0,
    "toolctx.scene_cache.snap.rebuild_reason.last": "hit",
    "toolctx.scene_cache.snap.structure_signature_changed": 0,
    "toolctx.scene_cache.version": 2,
    "toolctx.snap.manager.object_scope.scene_targets": 0
  }
}
```
