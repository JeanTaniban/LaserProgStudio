# Pass 50 — EVT rectangular mesh stability

This pass fixes two recurring EVT mesh issues:

- **Fill area could cap or block duct sections** because the inner airway cut was subtracted only as the visible inner corridor. In a global bounding box this could leave closed caps when the inlet/outlet did not clearly pass through the stock boundary.
- **Non-fill rectangular vents could miss roof/floor cap triangles** because the Shapely cap triangulation was unconstrained. Around holes, notches and fused wall areas, the top/bottom triangulation could fail to align with the vertical side walls.

## Changes

- Added a shared material-footprint builder for rectangular EVT:
  - normal mode: outer duct footprint minus an inlet/outlet-open airway cutter;
  - Fill area mode: global stock bounding box minus the same open airway cutter.
- The airway cutter extends past the first and last waypoint before subtraction, so the inlet and outlet are always open and cannot be capped by the fill stock.
- Mesh caps now use Shapely constrained Delaunay triangulation when available, instead of unconstrained triangulation.
- Preview outlines can now draw the same material footprint used by Apply, including open cuts and multiple rings.
- Added regression tests for curved rectangular vents, local mouths, Fill area, open airway routing and closed meshes.

## Validation

`284 passed, 3 skipped`
