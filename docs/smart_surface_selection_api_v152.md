# Smart Surface Selection API — v152 picking correctness

## Picking contract

Consumers requiring precise face selection should call:

```python
pick = ctx.pick.face_at(screen_pos, exact_screen=True)
snapshot = surface_selection.snapshot_from_pick(ctx, pick)
face_index = surface_selection.face_index_from_pick(pick, snapshot)
```

`exact_screen=True` means the backend must not search neighbouring pixels. The
returned hit must correspond to the frontmost pickable scene cell at the mapped
framebuffer coordinate.

The raw `PickResult.element_index` belongs to the displayed actor dataset. It is
not a stable document-mesh triangle identifier. Consumers must resolve it
against the canonical snapshot when persistent or semantic face identity is
required.

## Normal orientation

`SurfaceMeshSnapshot.normals` are consistently oriented per connected manifold
component. Relative face angles therefore distinguish parallel and antiparallel
surfaces.

`SurfaceSelectionProfile.hard_seed_angle_degrees` limits global angular drift
from the seed while `hard_dihedral_degrees` limits each local crossing.

## Cache policy

`SurfaceSelectionCache` retains exact seed results and accessibility fields by
default. `logical_reuse` defaults to `False`.

When enabled, logical cross-seed reuse is taught only to triangles that:

- are not incident to the learned region boundary;
- remain close to the source seed normal;
- belong to a sufficiently confident non-trivial region;
- have no active include/exclude constraints.

UI consumers must still validate a logical preview exactly before committing a
click-sensitive operation.
