# Projected Drawing 2D — indexed faces and staged benchmark (v32)

## Face rendering defect

`vtkPolyDataMapper2D` did not reliably tessellate the native concave polygon cells introduced in v31. A radial concave loop was rendered as a fan from one vertex, producing long crossing triangles even though the source vertex order was correct.

v32 compiles filled loops into explicit triangle cells:

- convex loops use a linear fan;
- concave loops use Shapely/GEOS constrained Delaunay triangulation;
- triangle coordinates are mapped back to the original local vertex indices;
- outlines keep their original closed polyline;
- coordinate patches update the persistent point buffers and do not retriangulate.

Invalid or self-intersecting loops are left without a fill instead of producing a corrupt fan; their outline can still be displayed.

## Transition hitch investigation

The v31 benchmark performed all of the following in one Qt callback before the first displayed frame: garbage collection, public primitive construction, an isolated cold compile, `replace_all`, three warm compiles and a viewport render. The Windows report shows that normal actor creation was only about 0.17–0.60 ms. The artificial 128-style case was the exception, with about 8.4 ms spent creating 128 actors.

v32 changes the benchmark pipeline to:

1. build public declarations;
2. precompile face/index topology;
3. synchronize and display the scene;
4. take one timing sample per Qt turn;
5. patch, replace and clear in separate turns.

The renderer also stops removing and re-adding actors immediately after their initial creation when they already appear in the required order. Dense point input reuses canonical immutable `(float, float, float)` tuples to reduce public API allocation overhead.
