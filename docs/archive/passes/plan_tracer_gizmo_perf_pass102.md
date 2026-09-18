# Pass102 — Plan tracer gizmo performance

The Plan tracer handle renderer now keeps VTK glyph actors alive instead of rebuilding mesh glyphs on every mouse move.

## Rationale

The previous Pass101 path cached the sphere template, but still called `cloud.glyph(...)` and `plotter.add_mesh(...)` for each handle group on every preview refresh. This keeps the old 3D sphere look, but it is still CPU-heavy during drag because the glyph mesh is rebuilt and actors are replaced.

The new path uses persistent `vtkGlyph3DMapper` actors:

- one actor per handle group/color;
- one reusable `vtkPoints` input per actor;
- update positions with `SetPoint(...)`;
- notify VTK with `points.Modified()` and `polydata.Modified()`;
- hide unused actors instead of removing them;
- keep the former PyVista `cloud.glyph(...)` path as a fallback.

This is closer to how interactive CAD handles should behave: only the changed coordinates move, not the whole visual pipeline.
