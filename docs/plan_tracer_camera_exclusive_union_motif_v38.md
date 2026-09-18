# LaserProg v38 — Plan Tracer camera-exclusive navigation and union motifs

## Purpose

This pass continues the Plan Tracer 2D performance work after the v37 field capture. It targets two concrete issues:

1. Pointer-derived editing work was still allowed to run while the camera was moving.
2. Motif used only one face even when several faces were selected with Shift in Modify mode.

## Findings from the v37 capture

The v37 capture already showed that projected geometry compilation was no longer the main camera bottleneck. Pan and zoom rendering stayed below one 60 Hz frame in most cases, but Plan Tracer still received thousands of cursor updates and projected drawing synchronisations during the session.

The largest remaining avoidable cumulative item was the static projected-drawing synchronisation path. The capture recorded 8,967 static synchronisations for about 9.39 seconds total. Pan rendering was 9.35 ms at p95 and zoom rendering 8.78 ms at p95. That left useful margin to remove snap, hover, hit-test and cursor work during navigation without reducing displayed geometry.

## Camera-exclusive navigation

Plan Tracer now enters a persistent camera-exclusive state for:

- left-button orbit;
- middle/right pan;
- mouse-wheel or trackpad zoom.

While that state is active, the viewport performs only camera movement, projected-point reprojection and rendering. The following Plan Tracer operations are suspended:

- smart snap queries;
- snap target/index rebuilds;
- cursor registration and visual synchronisation;
- hover and hit testing;
- Modify selection updates;
- drawing previews driven by pointer movement;
- generic gizmo-hover and pointer-recovery work.

QVTK may temporarily report `NoButton` during a real drag. The state therefore remains active until the explicit release event instead of relying only on `event.buttons()`. The custom right-pan implementation also keeps working through those transient `NoButton` frames.

At the end of a drag, Plan Tracer performs one cursor/snap catch-up at the final pointer position. Wheel and trackpad zoom use a 90 ms generation-based debounce, so only the last pulse can trigger the catch-up.

New diagnostics include:

- `creator.camera_navigation.begin/end`;
- `creator.camera_navigation.skipped_move.<mode>`;
- `creator.camera_navigation.controller_fast_path`;
- `creator.camera_navigation.custom_right_pan_frame`;
- `plan_trace.camera_navigation.suppressed_tool_event`;
- `plan_trace.camera_navigation.catchup` and `catchup_done`.

## Static renderer fast path

`ProjectedDrawingManager.state_token()` exposes only the owner revision and visibility. When neither primitives nor camera changed, `ProjectedDrawingOverlay2D.sync_from_manager()` now returns without:

- creating a full primitive snapshot;
- rescanning handles and labels;
- rebuilding batches;
- reprojection.

When only the camera changed, it uses a camera-only path and skips snapshot/geometry compilation.

An isolated benchmark with 2,042 projected primitives measured the unchanged static call at 0.1010 ms in v37 and 0.000882 ms in v38, a 99.13% reduction in renderer bookkeeping. This is an isolated CPU microbenchmark; the next real application capture is still required to measure end-to-end frame p95 on the user's machine.

## Motif on the union of Shift-selected faces

The Motif overlay now keeps the complete ordered face selection. Preview, offset gizmo, status text and final Apply all use the same target set.

The geometry pipeline is:

1. build valid polygons for every selected face;
2. compute their Shapely union;
3. generate one globally aligned motif over the union bounds;
4. clip openings against the union footprint;
5. split each opening back onto the contributing source faces;
6. apply and synchronise all selected faces in one projected-drawing batch.

A motif cell that crosses an internal boundary is therefore continuous across that boundary instead of restarting independently on each face. Disconnected selected faces are also supported: the union may be a `MultiPolygon`.

## Preview-to-Apply result cache

The preview and final Apply normally use identical geometry and parameters. v38 caches both:

- the validated union openings;
- their per-face split;
- estimated segment count and budget metadata.

The final Apply can reuse a complete lower-budget preview when the apply budget is equal or larger. Budget-limited previews are never cached as final results.

A local benchmark with 20 adjacent selected faces and 154 union openings measured:

- first preview: 66.15 ms median;
- final cached Apply preparation: 6.51 ms median;
- reduction: 90.15%.

## Validation

- 44 focused camera, projected-drawing, union-motif and migration tests passed.
- The broad Plan Tracer/projected renderer selection passed 360 tests.
- Its 18 failures are identical in the clean v37 reference tree; they include persistent-grid preference order dependence and older toolbar assertions that predate the Motif button.
- Multi-face motif tests verify openings on both adjacent faces, including openings crossing their shared boundary.
- The generated apply mesh remains closed and boolean-ready.
- A regression test verifies that final Apply does not regenerate or re-split a complete preview.
- A camera regression test verifies that a stray tool event during navigation cannot invoke cursor/snap work.

## Expected user-visible result

During pan, zoom and orbit, the tool should feel lighter because Plan Tracer no longer competes with the camera for pointer processing. The projected drawing remains visible and follows the camera. Snap and hover state are refreshed once when navigation ends.

A new field capture should show the new navigation counters and substantially fewer `plan_trace.cursor.update`, smart-snap and static-sync calls overlapping camera frames.
