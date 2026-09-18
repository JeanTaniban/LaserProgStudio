# Plan Tracer v126 — curve topology and complex curves

## Closed faces touching circles and arcs

The face arrangement previously polygonized sampled circles and arcs. A line
endpoint snapped to a displayed sample segment could remain slightly outside the
analytic curve. The contour looked closed, but GEOS still saw a microscopic gap
and did not create a face.

The v126 solver now:

- detects line endpoints within the Plan Tracer join tolerance of a circle or a
  circular arc;
- projects the contact onto the exact analytic curve only inside the face
  arrangement (the authored sketch point is not moved);
- injects the exact same contact coordinate into both the line and the sampled
  curve before noding and polygonization;
- gives exact arc snap targets priority over display-only sampled segments.

This applies both at curve endpoints and at contacts along the interior of a
circle or arc. For finite arcs, the nearest valid point is selected from the
radial projection and the two authored arc endpoints; a point just outside the
sweep therefore closes against the endpoint rather than the corresponding
infinite circle. Boundary entity attribution also uses a very narrow tolerant
corridor to absorb floating-point noding noise without changing the geometry.

## Complex Curve mode

A new **Curve** button (internal mode `bezier`, shortcut **B**) creates a cubic
Bézier curve. Click in this order:

1. start point;
2. end point;
3. first curvature handle;
4. second curvature handle.

The preview shows the chord and both handles. Cubic Béziers can form asymmetric
curves, inflections and S-curves that a single circular arc cannot represent.
The four authored points remain selectable and draggable in Modify mode.

Bézier curves participate in:

- face construction and extrusion;
- selection and deletion;
- snap targets and selected-path length measurement;
- undo/redo snapshots;
- editable-source save/reopen serialization;
- incremental Projected Drawing 2D updates.

## Validation

The release includes dedicated regression tests for near-circle contacts,
near-arc endpoint contacts, near-arc interior contacts, Bézier face closure,
serialization, four-click creation, selection measurement and exact-arc snap
priority. A targeted validation run passed 158 relevant tests; one unrelated
gizmo-catalog registration test fails identically in the v125 baseline. A wider
Plan Tracer suite passed 118 tests with the same seven legacy expectation
failures already present in v125.
