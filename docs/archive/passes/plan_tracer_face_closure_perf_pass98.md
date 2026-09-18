# Pass 98 - Plan tracer face closure and drag performance

## Problem

The Plan tracer could still feel slow while dragging, and four independently drawn lines did not reliably become a closed 2D face unless their endpoints were mathematically identical.

## Changes

- Replaced mesh-glyph/sphere gizmos with lightweight VTK point-cloud gizmos using `render_points_as_spheres`.
- Batched independent Plan tracer element lines into one actor and element control points into one actor.
- Added a lightweight interactive preview path used during pointer move/drag.
- Skipped expensive region triangulation/fill recomputation during drag; face fills update again on full redraw/release.
- Added a practical sketch join tolerance for face detection, so visually connected line endpoints form a region even with small placement offsets.
- Reworked region node clustering to merge endpoints by distance rather than round-to-grid keys.
- Removed the dragged point itself from the smart-snap drag cache to avoid sticky self-snap while modifying points.

## Validation

- Added tests for nearly-touching four-line loops becoming closed faces.
- Added static tests for lightweight interactive preview and self-snap avoidance.
