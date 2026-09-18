# Plan tracer complete sketch direction — Pass 99

This pass prepares the Plan tracer for a more complete CAD-like 2D sketch workflow.

## Design rules kept for the next passes

- Visible points are first-class handles, not decorative dots.
- Smart snap has priority over grid snap so endpoint coincidence is preserved.
- Grid snap is a fallback placement aid, not a destructive post-process.
- Closed profiles must be detected from connected primitives, not only from the legacy polygon path.
- Drag preview must avoid full sketch reconstruction and heavy face triangulation.
- Rendering should use batched GPU point/line actors instead of one actor or one mesh sphere per handle.

## Future feature slots

- Rectangle tools: 2-point, 3-point, center rectangle.
- Constraint badges: coincident, horizontal, vertical, tangent, radius/diameter.
- Construction geometry toggle.
- Project/include selected 3D edges into the sketch.
- Profile list/selection when multiple closed faces exist.
- Dimension input for length, angle, radius and diameter.
