# Pass 33 — Vent 180° Pivot, Always-Compact Routing, Local Flares, and Planar View Restore

This pass stabilizes the audio vent generator after practical serpentine testing.

## Changes

- Rectangular/square vents always use compact shared-wall routing. The former Compact UI option was removed from the user interface and kept only as an internal compatibility alias.
- One-point 180° turnarounds now use the middle waypoint as a true circular pivot. The radius is tied to the compact centerline spacing, so a U-turn stacks cleanly instead of folding the duct over itself.
- The validation model rejects turnarounds whose available diameter is too small for the inner width plus the minimum wall thickness.
- Flare is now local to the real inlet/outlet segments:
  - inlet flare transitions only between the first and second clicks;
  - outlet flare transitions only between the penultimate and final double-clicked endpoint.
- Wall-only rectangular vents now generate a fused 2D wall footprint and extrude it as closed solids. This closes/fuses enclosed wall volumes created by serpentine routing instead of leaving loose wall sheets.
- Leaving Plan Tracer or Vent Generator restores the camera pose that was active before entering the locked planar tool.

## Compatibility

The legacy `compact_wall_fusion` field remains on `VentPathDraft` for old data and tests, but rectangular vents ignore it and always use shared-wall compact spacing. Round vents remain conservative and do not use wall fusion.
