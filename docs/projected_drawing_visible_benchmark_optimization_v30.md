# Projected Drawing 2D — visible benchmark and dense-scene optimization (v30)

## Diagnostic conclusion from v29

The v29 diagnostic showed that actor creation and snapping were not the dominant costs. The previous backend projected every world point through a scalar VTK conversion and repeated that full projection after any registry change. Examples from the supplied Windows run:

- 3,000 points: about 22 ms of projection during a one-element update;
- 10,000 points: about 73 ms of projection during a one-element update;
- 300 faces: about 18 ms of projection;
- 2,000 points split across 128 styles: additional actor creation and ordering cost.

The benchmark itself also created, measured and removed a case before Qt could paint it, so only interface stalls were visible.

## v30 changes

- visible show/measure/clear state machine with explicit pauses;
- dense `point_cloud`, `segment_batch` and `face_batch` declarations;
- one poly-vertex cell per point batch;
- persistent NumPy-backed display buffers;
- camera-matrix vector projection per batch;
- primitive-to-batch span index;
- compatible `update` and `update_many` paths that dirty only changed coordinates;
- no actor reorder when style/layer order is unchanged;
- convex triangulation fast path and cached concave triangulation;
- schema-v2 diagnostic with projected-coordinate counts.

## Migration rule

Use packed declarations for committed sketch geometry. Keep only cursor, pending segment/arc and selected-edit handles as unit primitives. Do not rebuild committed batches during ordinary pointer movement.
