# Cloth reliable faces and curve cover — v132

## Problem clarified

Two parallel arcs recovered from Plan Tracer are not one planar polygon. The
intended result is a textile band spanning both curves, similar to a skin laid
across two curved rails. Sending the complete outline through a generic polygon
triangulator can connect unrelated vertices, create long diagonal fans, twist
the surface or project it onto the wrong plane.

## Ruled surface between two rails

Mesh trace now splits selected source edges into connected components. **Cover**
becomes active only when the selection contains exactly two usable components:

- each component is open;
- each component is connected;
- no vertex branches into more than two selected edges;
- both rails have a non-zero length and remain separated.

The two chains are ordered from endpoint to endpoint. Both possible directions
of the second rail are evaluated, including endpoint distance, bridge-width
variation and tangent agreement. The direction with the lowest twist risk is
selected automatically.

Each rail is parameterised by normalised arc length. Knots from both source
meshes are merged and both rails are resampled on the same parameter values.
This supports different tessellation densities without pairing vertex index 7
from one mesh arbitrarily with vertex index 7 from another.

The final cover is built interval by interval. Each interval forms one regular
quadrilateral Cloth panel when planar, or two local planar panels if that single
cell is measurably non-planar. Adjacent cells reuse their transverse edge and
therefore remain connected through the existing fold graph. The operation is
transactional: a failed cell restores the complete document state.

A translucent green surface and sampled transverse ribs preview the predicted
pairing before validation.

## Reliable curved loops

Curved closed-loop creation now uses one shared geometric analysis path for
automatic discovery, Face repair and mesh generation:

- adaptive circular-arc tessellation bounded by chord error;
- exact inclusion of the user arc control point;
- stable Newell frame fitted from the complete ordered boundary;
- self-intersection and planarity checks;
- constrained Delaunay triangulation when available, with deterministic ear
  clipping as fallback;
- conservative ambiguity handling when several similarly sized loops are valid.

When the user intent is genuinely ambiguous, Cloth keeps the curves and asks for
an explicit Face repair selection rather than silently filling the wrong side.
The two-rail Cover case is not ambiguous and does not require additional input.

## Modify selection and deletion

Modify now hit-tests points first, then edges, then the smallest projected face
under the pointer. Shift toggles additive selection. Selected points, edges and
faces have distinct highlighted overlays.

Delete applies topology-safe cascading rules:

- deleting a point removes incident curves;
- deleting an edge removes dependent faces and relations;
- deleting a face keeps reusable boundary curves;
- dependent folds and seams are removed;
- only points orphaned by this operation are cleaned;
- unrelated construction points are preserved.

## Mesh trace completion

Both **Trace** and **Cover** now finish the Mesh trace sub-tool after successful
materialisation. Temporary source highlights are cleared, the contextual overlay
is hidden and Cloth returns to **Modify**.

## Validation

Targeted Cloth validation covers:

- double-click and first-node Polyline closure;
- point, edge and face selection/deletion;
- curved annular-sector triangulation;
- ambiguous curved auto-face refusal;
- same-mesh and two-mesh parallel arc rails;
- different rail tessellation densities;
- reversed rail orientation;
- branching-chain rejection;
- ruled-strip 3D mesh generation;
- fold connectivity and linked flat-pattern generation;
- Cover/Trace return to Modify.

The complete project test run reports 59 pre-existing failures, matching the
v131 baseline category count. No Cloth-targeted regression is present.
