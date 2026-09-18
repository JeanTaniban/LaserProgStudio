# Plan Tracer selection and snap lifecycle — v144

## Interaction contract

### Point click

A left press on a point may prepare a native grab, but a matching release with
no geometric movement is still a selection gesture. It must preserve the point
selection and must not create a detached point.

### Structural drag

Dragging selected lines/faces may promote their support points and may detach
shared topology when required to protect non-selected geometry. The selection
that existed before this temporary promotion is stored independently from the
geometry history snapshot.

### Selection rectangle

Shift-drag is split into two phases:

1. **Drag phase:** update only the screen-space rectangle.
2. **Release phase:** collect hits, mutate selection, synchronize reports and
   render Plan Tracer once.

No sketch compilation, report generation or projected-sketch rebuild belongs in
the per-pixel drag phase.

## Smart Snap cache ownership

`PlanTrace2DSnapTargetsService.invalidate_geometry_cache()` is the central reset
for:

- compiled live snap targets;
- structural and fast signatures;
- local screen-space target index;
- stable filtered target tuples;
- geometry generation revision.

Sketch synchronization calls this reset only when geometry actually changes.
Drag release additionally clears the frozen target pool. If a release event is
consumed by another UI layer, `_active_full_targets()` compares the frozen cache
with `ctx.selection.state.grab_active` and repairs the stale state lazily.

## Performance guardrails

- Selection-box move events do not call Plan Tracer `_sync_reports()`.
- Selection-box move events do not call Plan Tracer `_render()`.
- VTK rectangle actor membership is checked at gesture start, then at most every
  500 ms while the gesture remains active.
- VTK rectangle renders are limited to 60 Hz and identical rectangles are
  ignored.
- Semantic drag handling remains O(1); the v144 headless benchmark measured
  approximately 2.2 microseconds per event over 10,000 events.

## Regression coverage

`tests/test_v144_plan_tracer_selection_snap_performance.py` verifies:

- point selection survives press/release without duplication;
- 1,000 selection-box move events trigger no full report or sketch render;
- stale drag snap caches recover when no grab is active;
- exact vertex snapping remains available after a no-op point click;
- live geometry invalidation does not rebuild the frozen drag screen index.
