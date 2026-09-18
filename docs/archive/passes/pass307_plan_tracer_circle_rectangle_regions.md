# Pass 307 — Plan Tracer circle/rectangle region reconstruction

## Failure

The Shapely arrangement solver was intended to node every line/circle crossing and polygonize every bounded cell. Three timing helpers were accidentally missing from `arrangement_faces.py`:

- `_face_timing_enabled`
- `_time_now_if_enabled`
- `_record_elapsed_if_enabled`

Every face solve therefore raised `NameError` before reading the geometry. `FaceSolver` caught the exception and silently selected the old candidate-loop fallback. That fallback can draw a circle and rectangle independently, but it cannot reliably reconstruct all cells of their planar arrangement.

## Repaired state machine

1. Sketch entities are authored and remain stable.
2. The live compiler keeps circles intact (`split_curve_intersections=False`, `split_curves_at_vertices=False`).
3. The arrangement solver samples curves, nodes crossings with GEOS and polygonizes the graph.
4. Each bounded cell becomes one `SketchFace` with stable source boundary IDs.
5. Faces are non-overlapping and independently selectable.
6. Deleting a face suppresses only its stable geometric signature; the circle and rectangle linework remain editable.

Unexpected arrangement failures are now counted in debug mode as `sketch.face_solver.arrangement_fallback` and the legacy fallback faces carry `arrangement_fallback_error` metadata.
