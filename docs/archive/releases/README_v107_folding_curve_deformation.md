# LaserProg v107 — Folding curve deformation

## User workflow

1. Open **Folding** and select the mesh to deform.
2. Select a face to define the local deformation plane. The camera remains free to orbit.
3. Place the start and end points of the affected interval.
4. Drag the two projected curve handles, or edit their offsets in the inspector.
5. Use **Apply** to commit the editable folded mesh or **Cancel** to restore the original geometry.

## Geometry

The start/end direction defines the longitudinal axis in the selected face plane. A smooth quintic displacement curve joins the unchanged geometry with zero displacement and zero tangent offset at both boundaries. Mesh cross-sections inside the interval are transported along the curve in a vectorized operation; vertices before the start and after the end are preserved exactly.

## Architecture

The implementation follows the built-in Creator API and is split into dedicated modules for models, state transitions, geometry, serialization, projected rendering, inspector declarations and lifecycle coordination. Applied meshes store an undeformed source plus the curve and plane parameters, allowing the same fold to be reopened without accumulating deformation.

## Validation

- Folding lifecycle and five-state workflow tests.
- Camera-drag guard tests.
- Boundary preservation, smooth tangent and serialization tests.
- Tool registry, toolbar asset, product-contract and help-document tests.
- Full static quality gate.
