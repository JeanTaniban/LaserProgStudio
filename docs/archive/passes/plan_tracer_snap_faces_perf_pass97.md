# Pass 97 — Plan tracer snap, drag performance and closed faces

## Goals

- Make Plan tracer dragging responsive by avoiding full scene/snap rebuilds on every mouse move.
- Add dedicated Plan tracer snap controls: **Smart snap** and **Grid snap**.
- Extend Smart snap to target existing 2D points, scene corners and projected mesh edges.
- Treat closed 2D sketch zones as real faces so they can be previewed and extruded.

## Changes

- Added cached scene snap anchors/edges for Plan tracer. The cache is built when the tool opens or the locked plane changes, then reused during hover and drag.
- Added per-drag snap caches to avoid rescanning static scene data while moving a point.
- Throttled interactive preview redraws during pointer movement.
- Added `PlanTraceSnapButton` UI styling and two local snap buttons in the Plan tracer panel.
- Added `plan_trace_regions.py` to detect closed regions from:
  - legacy closed polygons;
  - standalone circles;
  - connected lines and 3-point arcs.
- Updated Plan tracer extrusion so closed sketch regions can become 10 mm solids even when the legacy polygon is not closed.
- Added translucent face preview for detected closed regions.

## Validation

Added `tests/test_pass97_plan_tracer_snap_faces_perf.py` covering:

- projected-edge Smart snap;
- explicit Grid snap;
- joined line loops becoming faces;
- circles becoming extrudable faces;
- controller cache/throttling hooks.
