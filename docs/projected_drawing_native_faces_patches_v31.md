# Projected Drawing 2D — native faces and direct patches (v31)

## Conclusion from the v30 Windows diagnostic

The dense representation and vector projection solved the original scaling issue:

- 10,000 points: cold synchronization about 6.6 ms; camera reprojection about 1.6 ms median;
- 3,000 segments: cold synchronization about 7.3 ms;
- a 3,000-element mixed scene: cold synchronization about 13.5 ms;
- steady synchronization remains close to zero.

The remaining over-budget cases were coordinate edits of large faces. They still rebuilt a changed face's Python triangulation and compared the complete immutable declaration even when only one vertex moved. A 256-vertex concave face reached about 20 ms for one update, and a 2,000-vertex face reached about 141 ms.

## v31 changes

- filled faces are stored as native VTK polygon cells;
- Python ear clipping and constrained triangulation are removed from the Projected Drawing renderer;
- `patch_point_cloud`, `patch_segment_batch`, `patch_face` and `patch_face_batch` expose exact coordinate changes;
- patch journal entries update only addressed NumPy rows and projected points;
- camera reprojection concatenates fragmented style batches into one matrix operation;
- benchmark schema v3 measures the direct-patch path rather than manufacturing a complete replacement declaration.

## Plan Tracer rule

Use dense batches for committed geometry. Use direct patches only for coordinate-preserving edits. Use unit primitives for cursor and previews. Rebuild a face batch only when its structure changes (new/deleted face or changed vertex count).
