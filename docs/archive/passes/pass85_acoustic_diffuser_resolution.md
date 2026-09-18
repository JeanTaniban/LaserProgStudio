# Pass 85 — Acoustic diffuser resolution control

The native Acoustic diffuser now exposes a compact **Resolution** control. It maps to the internal mesh quality used by the cylindrical skirt, vent contour tessellation, local wall tiling, and diffuser surface of revolution.

Default UI resolution is **Low** to keep interactive previews fast. Users can switch to Medium or High for smoother final exports.

The generator still keeps vents watertight and avoids global triangulation membranes: lower resolution reduces the number of regular skin tiles, vent contour points, rounded-slot corner segments, and diffuser curve sections without returning to the old pixelated-hole approach.
