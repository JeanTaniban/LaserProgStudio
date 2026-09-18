# Folding v129 — professional deformation pass

## Problem addressed

The former Folding kernel only repositioned vertices already present in the
source mesh. A triangle spanning the complete flexible strip had no interior
sample to follow the curve. Depending on tessellation, this produced a flat
bridge, a severely stretched triangle or almost no visible fold.

## Adaptive strip refinement

Before living-hinge deformation, every triangle crossing the strip is clipped
against a set of planes perpendicular to the longitudinal axis. The first and
last planes are the exact hinge boundaries. Interior station density is derived
from total tangent variation, so concentrated bends and S-curves receive more
samples than a shallow bend.

Intersections are cached per shared edge and station. Adjacent triangles
therefore reuse the same generated vertex, preserving manifold connectivity.
Per-vertex UV coordinates are linearly interpolated.

Legacy free-curve projects retain their historical topology and kernel.

## Internal geometry modes

### Preserve internal structure

The analytic sweep first supplies the requested target fold. A topology-aware
position-based solve then reduces changes in original mesh-edge lengths while
keeping the curve as a soft positional guide.

- vertices outside the flexible strip are hard constraints;
- both outer regions remain exact rigid transforms;
- small disconnected components fully contained in the strip are fitted with a
  proper rigid transform using SVD, preserving all pairwise distances;
- connected geometry uses local edge constraints, limiting crushed holes,
  distorted ribs and irregular thickness changes;
- iteration count adapts to mesh size to keep preview time bounded.

This is a geometric local-rigidity solver, not a stress or collision simulation.

### Uniform deformation

The refined mesh is transported directly through the moving tangent frame.
Every detail follows the same continuous material field, including the expected
inner compression and outer extension of a thick fold. This is useful for soft,
rubbery or intentionally deformable internal structures.

## Persistence

`folding_source` schema version 5 stores `deformation_mode` alongside the source
mesh, plane, profile, angle, fixed side and group data. Versions 1–4 reopen
without loss; missing or unknown values normalize to `preserve_structure`.
