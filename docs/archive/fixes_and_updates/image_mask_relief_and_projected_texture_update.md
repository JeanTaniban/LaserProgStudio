# Image mask relief and projected texture update

## Added

- `File > Import 2D mask...` now opens a dialog to import PNG/JPG/BMP masks as real 3D relief.
- Mapping: black = 100% of height `n`, 50% gray = `n / 2`, white = void. `Invert` swaps the mapping.
- The importer builds a closed column-based height mesh and keeps a `Max grid` guard to avoid accidentally creating millions of triangles.
- Added the `Texture projection` tool to the top Tools toolbar and the Tools menu.
- The projected texture tool can browse an image, choose planar/box/cylindrical/spherical projection, set scale/rotation/offset/repeat, and preview/clear the projection on selected meshes.
- WorkMesh UVs are now converted to VTK texture coordinates for PyVista material-mode preview.

## Validation

- Added tests for grayscale mask relief generation.
- Added tests for projected texture UV/metadata attachment.
- Full suite: `80 passed, 2 skipped`.
