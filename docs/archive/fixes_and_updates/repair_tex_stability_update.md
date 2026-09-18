# Repair + TEX + tool-exit stability update

## Tool lifecycle
- Applying a tool no longer refocuses/repositions the editor camera.
- Scene rebuild still keeps the camera, but no extra focus operation is called after Apply.

## TEX projection
- Added **Attach to mesh** toggle.
  - Off: same as before, creates a separate face decal.
  - On: stores the projected texture directly on the selected mesh.
- Texture repeat export is now handled in the engraving texture layer. UVs outside 0..1 are tiled for PNG/SVG export instead of sampling only the base bitmap.
- Repeat state is logged and preserved through texture projection metadata.

## Mesh repair
- Added **REP** modifier button and a **Modifier - Réparation** panel.
- Repair does:
  - merge very close vertices;
  - remove degenerate/tiny triangles;
  - remove duplicate triangles;
  - orient faces consistently;
  - optionally fill holes with VTK/PyVista;
  - report closed/boundary edge stats.

## Boolean robustness
- Boolean inputs are repaired before conversion to manifold3d.
- Difference cutters get a tiny internal expansion margin to avoid coplanar/tangent sliver faces.
- Boolean results are cleaned again to remove tiny/degenerate faces.
- Standalone cube/joint boolean wrapper now routes through the shared Studio boolean engine when available.

## Light UI overlay
- Transform axis hover/drag highlight now also updates the compact Light UI overlay X/Y/Z fields.
