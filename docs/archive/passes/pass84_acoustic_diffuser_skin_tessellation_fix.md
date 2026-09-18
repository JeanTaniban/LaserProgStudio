# Pass 84 — Acoustic diffuser vent skin tessellation fix

The previous clean vent implementation generated accurate circular/rounded openings, but the cylindrical inner and outer skins were triangulated as one global developed-surface membrane. Delaunay triangles could stretch from vent contours to distant top or bottom border vertices. After wrapping those large flat triangles back onto the cylinder, the holes looked clean but the cylinder skins appeared warped.

This pass keeps the clean opening contours and changes only the wall meshing strategy:

- the developed cylinder is now triangulated in small local tiles instead of one global polygon;
- hole topology is confined near each vent opening;
- top and bottom annular caps reuse the exact boundary splits from the side wall;
- vent tunnel faces reuse the exact split boundary edges from the side wall;
- no OpenSCAD or external CAD boolean dependency is introduced.

A regression test checks that vented inner/outer cylindrical skin triangles remain locally tessellated, preventing large chord-like faces from deforming the visual cylinder surface.
