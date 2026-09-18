# UI parts highlight and primitive update

## Parts list selection

The left Parts list now mirrors the 3D selection state.

- Single selection highlights one row.
- Shift multi-selection highlights every selected row.
- The active part remains the current row.
- Clearing the 3D selection clears the list selection.

## Primitive generator

The primitive tool now provides additional primitive types:

- Box/Cube
- Cylinder
- Sphere
- Cone
- Pyramid
- Triangular prism
- Hex prism

Default dimensions are now 40 x 40 x 40 mm. Cylinder, cone, and hex prism use X/Y as diameter dimensions and Z as height.

## Light UI toggle

A Light UI toggle button was added to the top 3D toolbar. It switches between the compact light transform overlay and the normal open inspector when no tool or preview is active.
