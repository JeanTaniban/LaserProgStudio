# Cloth Boolean Pattern Pipeline — v146

## Problem

Older Cloth outputs were open panel surfaces. Generic booleans require closed
manifold solids, so a subtraction could be rejected with `NotManifold`. Even if a
3D boolean succeeded after an external repair, the raw result no longer
contained the panel graph required for unfolding.

## Contract

The editable `ClothDocument` remains the source of truth. A folded output is a
closed thin solid carrying a serialized copy of that document. A boolean result
must preserve the source and append a reproducible cutter modifier. Rebuilding
from the source applies each cutter to the panel regions before producing folded
and flat geometry.

## Solidification

Open panel surfaces are thickened around their mid-surface. Top and bottom skins
are generated at half the selected material thickness and boundary side walls
close the volume. A closed mid-surface receives an outer and a reversed inner
shell, preserving a hollow thin-sheet volume rather than becoming a filled
block.

Before the solid enters the generic boolean engine, every indexed edge must have
exactly two incident triangles. Topology-authored Cloth meshes bypass generic
coordinate welding, because it can reconnect unrelated pattern cuts.

## Modifier projection

A stored cutter is intersected with each panel plane. Triangle-plane segments
are polygonized with GEOS precision control. Coplanar cutter triangles are
included directly. Difference subtracts the resulting 2D region from the panel;
a connected planar union may add material. Polygon and MultiPolygon results,
including holes, are constrained-Delaunay triangulated.

This representation intentionally describes through-cuts at the panel
mid-surface. A shallow 3D engraving that does not cross the mid-surface has no
well-defined flat cutting contour and is therefore outside this workflow.

## Stitch healing

The healer only considers complete single-panel straight boundaries not marked
as user/automatic cuts. Endpoint pairs must fit within the document's Stitch
tolerance. The second panel is rewired to the canonical points and curve, then a
fold relation is inferred. Flattening operates on a healed clone, so validation
is transactional and original data is not partially mutated on failure.

## Safety limits

- Stored cutter limit: 250,000 triangles; oversized cutters are rejected rather
  than truncated.
- Thickness: 0.01–20 mm.
- Stitch tolerance: 0.001–5 mm in the inspector.
- Boolean preparation rejects the linked flat-pattern mesh as a 3D target.
- Failed regeneration leaves the previous Cloth result unchanged.
