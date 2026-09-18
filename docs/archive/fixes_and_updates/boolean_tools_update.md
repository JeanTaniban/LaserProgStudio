# Boolean tools update

This update adds two immediate boolean operations in the 3D toolbar.

## Buttons

- `SUB`: subtract the active selected part from every touching part.
- `ADD`: union all selected parts into one part.

These actions do not use the Transform inspector and do not create a preview. They apply
immediately to the committed scene.

## Subtract touching

The active selected mesh is used as the cutter. LaserProg finds every other mesh whose
world bounds touch or overlap the cutter bounds, then replaces each target with:

```text
target - cutter
```

The cutter remains in the scene.

## Union selected

All selected meshes are unioned into one mesh. The active mesh is used as the base color.
The original selected meshes are removed and the new union mesh is inserted at the first
selected index.

## Requirements

The boolean engine uses `manifold3d`. The operation expects closed manifold solids.
If a mesh is open, self-intersecting, or not watertight, the operation may fail and show
a warning.
