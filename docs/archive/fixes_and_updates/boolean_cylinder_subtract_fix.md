# Boolean cylinder subtraction fix

This update fixes boolean subtraction failures when the cutter is a cylinder or cone.

## Problem

The generated cylinder/cone primitives were closed meshes, but their side faces were wound in the opposite direction from their caps. PyVista still displayed them correctly, but manifold3d could interpret them as inverted/invalid solids. Typical symptom:

```text
Subtract touching failed
No part could be subtracted. Check that the meshes are closed solids.
```

The failure was most visible with cube - cylinder cuts.

## Fix

- Cylinder primitive side triangles are now generated with outward winding.
- Cone primitive side triangles are now generated with outward winding.
- The boolean engine now repairs triangle winding before converting meshes to manifold3d.
- The repair is topology-preserving: it only flips triangle index order and does not move vertices.
- Old saved scenes or imported meshes with the previous broken cylinder winding can still be subtracted.

## Validation

Added `tests/test_boolean_cylinder_subtract_fix.py`.

Validated with:

```text
pytest -q
```

Result:

```text
79 passed, 1 skipped
```
