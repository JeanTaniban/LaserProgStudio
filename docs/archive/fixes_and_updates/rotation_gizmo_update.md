# Rotation gizmo update

This update adds the first interactive rotation gizmo.

## Behavior

- Rotate mode now displays three foreground rings around the selected part.
- X ring rotates around the world X axis.
- Y ring rotates around the world Y axis.
- Z ring rotates around the world Z axis.
- Rings are rendered in the same foreground renderer as the translation axes, so they remain visible over the 3D mesh.
- Dragging a ring applies the rotation directly to the mesh vertices.

## Implementation notes

- The rotation is computed from the mouse ray projected onto the plane perpendicular to the selected world axis.
- The delta angle is accumulated incrementally to avoid a jump at the -180 / +180 degree boundary.
- The actual vertex rotation uses an axis-angle quaternion formula.
- The gizmo is not rebuilt during every drag frame. Only the active mesh polydata points are updated, then the scene is rendered.
- If the rotation plane is viewed edge-on and the ray projection is unstable, a simple mouse-drag fallback still allows rotation.

## Current limitation

This first version uses world axes only. Local part axes can be added later with a World / Local toggle once the project stores a reliable per-part orientation state.
