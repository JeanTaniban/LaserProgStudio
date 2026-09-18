# Plan Tracer Duplicate Prefabs — v136

## Selection model

The visible selection remains semantic. Selecting a face does not silently select
its boundary points, which preserves face-only deletion. When a drag begins from
a support point, Plan Tracer promotes the required points into the native drag
set just before the interaction runtime starts.

## Safe detachment

Before a group move, the selection service analyses point-to-curve incidence.
Unselected branches are rewired to stationary duplicate points. A shared boundary
between selected and unselected generated faces receives a stationary boundary
copy. Compilation is deferred until release because coincident points are
intentionally merged by the sketch compiler.

A no-motion click restores the exact pre-drag snapshot, so merely grabbing a
shared point never changes topology.

## Portable payload

Clipboard and prefabs use the same versioned `SketchPayload`. Geometry is stored
relative to a pivot and contains points plus authored line, arc, circle and cubic
Bézier relationships. Generated face records are not serialized; faces are
re-solved from the pasted closed boundaries.

## Persistent library

User prefabs are written atomically to
`settings/plan_trace_2d_prefabs.json`. The file is outside the project document,
so the same prefabs are available in every project. A temporary file is replaced
only after complete JSON serialization.

## Pivot capture interaction

Since v148, pivot capture is not a dialog validation step. After the source
selection is accepted, the viewport shows one instruction-only prompt asking
the user to click the prefab pivot. No validation, Done or Apply button is
available in that phase. The name modal opens only after a real pivot click has
created the relative `SketchPayload`.

## Placement

Connected open curves are stitched through their authored endpoint IDs. Branches
are intentionally split into deterministic simple paths. Distances are measured
along sampled curve length and tangent rotation is derived at each placement.

Face fill computes a dense prefab footprint, including sampled curved geometry.
A candidate pivot is accepted only when the complete footprint lies in the face
and outside every hole. Placement is capped at 5,000 instances.
