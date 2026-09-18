# Plan Tracer 2D — placement-preserving edit (v130)

## Problem

Transform tools bake translation, rotation and scale into `WorkMesh.vertices`.
The editable Plan Tracer source previously retained the original plane and 2D
sketch coordinates. Opening that source therefore reconstructed the volume in
its creation frame, usually near the origin.

## Placement reference

`attach_editable_source()` now records a compact placement reference containing:

- source vertex and triangle counts;
- up to 24 stable vertex indices and their source world positions;
- original world bounds.

At edit time, the indexed source/current pairs recover a 3D affine transform by
least squares. The transform is accepted only when it has full rank, a finite
non-degenerate linear part and residual error below a mesh-size-relative
threshold.

The recovered transform is applied to:

- the semantic and display drawing planes;
- sketch points and dimension label positions;
- the world anchor;
- extrusion depth;
- draft bounds;
- subtraction intact-target geometry and depth range.

An exact identity fast path avoids modifying serialized values when the object
has not moved.

## Backward compatibility

For older editable objects without placement landmarks, LaserProg rebuilds the
reference extrusion or draft placeholder from the stored sketch and matches its
vertices to the current mesh. If topology cannot be reproduced, a conservative
bounds-centre translation fallback still preserves the common moved-only case.
After the next Apply, the replacement receives the compact v130 placement
reference.

## Camera

Opening an editable volume passes the current mesh bounds to
`align_camera_to_plan_surface()`. The production camera controller centres its
focal point on those bounds, aligns perpendicular to the transformed plane and
computes parallel scale from the projected horizontal/vertical extents and the
current viewport aspect ratio.

Older host implementations that do not yet accept `focus_bounds` remain
compatible through the previous keyword/positional signatures.

## Validation

Specific v130 coverage includes:

- compact landmark persistence;
- translated edit and Apply at the current world position;
- a real sketch modification after translation without returning to the origin;
- legacy source recovery without landmarks;
- combined rotation, translation and non-uniform scale;
- camera focus bounds matching the moved object;
- existing editable Add and Subtract workflows.

Full-suite comparison against v129 in the same environment:

- v129: 1609 passed, 63 failed, 3 skipped;
- v130: 1618 passed, 59 failed, 3 skipped;
- no new failing test;
- four pre-existing camera-alignment tests are fixed;
- the additional v130 tests pass.

The remaining failures are pre-existing and include unavailable optional
`manifold3d` boolean tests in this environment.
