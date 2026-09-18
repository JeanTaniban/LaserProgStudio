# Pass 93 - Clean Extrude Down mesh

## Problem
The Extrude down modifier used to append a downward support prism to the untouched source mesh. This produced a visually plausible preview, but the exported mesh contained two independent shells touching at the slice plane. Geometry below the plane also stayed inside the result, which looked like two parts grouped together rather than one clean solid.

## Changes
- The selected mesh is now clipped at the chosen plane before generating the downward extrusion.
- Source geometry below the plane is removed.
- Cut-plane vertices are reused by the generated vertical walls so the extrusion is welded to the remaining upper mesh.
- Bottom-cap vertices are shared with the vertical walls instead of duplicated.
- The result is a single connected triangle surface for normal closed parts.

## Validation
Added regression tests for a closed cube:
- extrusion creates one welded surface component;
- no duplicate coordinates are left at the cut or bottom rings;
- every edge is used by exactly two triangles on the simple closed mesh.
