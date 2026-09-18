# Texture rotation gizmo pick and size fix

The TEX rotation ring is now picked with a forgiving screen-space circle test before falling back to the generic VTK prop picker. This avoids the mesh/decal actor stealing clicks from the thin torus and makes the ring much easier to grab.

The ring radius is now computed from a fixed pixel target instead of the transform-gizmo world length. Camera zoom refreshes rebuild the ring so it keeps a stable apparent size on screen.

Changes:
- screen-space picker for `texrot` with practical pixel tolerance;
- ring radius based on desired screen pixels;
- texture ring included in camera-scaled overlay refreshes;
- final refresh after camera moves while TEX preview is active.
