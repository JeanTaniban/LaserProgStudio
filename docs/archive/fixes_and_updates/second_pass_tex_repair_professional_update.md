# Second pass: TEX, repair, camera stability and boolean robustness

## Scope
This pass consolidates the previous feature additions instead of adding only surface-level UI changes.

## Changes

### Editor camera stability
- The render camera button no longer refocuses/moves the editor view when selecting or creating the camera object.
- Tool apply/close already rebuilds with `keep_camera=True`; this pass keeps camera placement controls non-invasive too.

### TEX placement mode cleanup
- Switching **Attach to mesh** ON removes any old decal for the same source mesh before applying the texture directly to the mesh.
- Switching **Attach to mesh** OFF clears the source mesh texture metadata before creating the decal.
- Texture projection metadata now stores a `placement` field: `mesh` or `decal`.
- This prevents double-texture states such as “attached texture + floating decal at the same time”.

### Texture repeat robustness
- VTK texture repeat is configured more explicitly using both setter and On/Off style calls when available.
- Cached textures are reconfigured every time they are reused, so changing Repeat in TEX cannot keep stale wrap mode.

### Mesh repair
- The repair report now includes non-manifold edge deltas and whether an optional Trimesh repair backend was used.
- The repair pipeline optionally uses Trimesh when it is installed, but the app still works without making it a hard dependency.
- The repair tool summary is more actionable for boolean/subtraction problems.

### Tests
- Added regression tests for switching TEX between decal and attached modes.
- Added a regression test for the extended mesh repair report.
