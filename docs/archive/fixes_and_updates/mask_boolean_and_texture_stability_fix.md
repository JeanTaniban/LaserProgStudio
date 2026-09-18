# Mask relief boolean + texture projection stability fix

- Rebuilt `Import 2D mask` relief meshes as boolean-safe heightfield islands.
- Pixel centres keep the exact grayscale-derived height while neighbouring active pixels share manifold edges.
- Diagonal-only contacts no longer share topology, preventing non-manifold vertices/edges.
- Added explicit VTK texture coordinates and forced actor texture reattachment after scene/style/display refreshes.
- Added texture diagnostics (`[TEXTURE] ...`) to identify loading, UV tuple count, and actor attachment state.
