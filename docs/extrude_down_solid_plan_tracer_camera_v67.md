# v67 – Extrude Down solid mesh and Plan Tracer camera framing

## Extrude Down

Extrude Down now treats horizontal face/sheet inputs as filled sections, not as
edge-only outlines.  The geometry backend rebuilds polygons from coplanar
triangles, preserves inner holes, then creates a welded solid prism with:

- top cap;
- bottom cap;
- outer vertical walls;
- inner vertical walls for holes.

Cap triangulation uses Shapely constrained Delaunay triangulation when
available.  This prevents bottom/top caps from bridging holes or leaving an
apparently empty shell.

The standard volumetric cut path still clips the upper mesh and welds the
vertical extrusion to the cut contour.  Bottom caps now use the same constrained
triangulation helper.

## Plan Tracer 2D

When a face is picked to lock the drawing plane, Plan Tracer now passes the
bounds of the object owning that face to the camera-alignment API.  The host
camera stays orthographic/perpendicular to the picked face, but frames the
entire object in the viewport instead of only centering on the picked point.
