# Pass 37 — EVT preview contour follows the edited curve

## Problem

When the user edited a segment in **MOD** with the `Curve radius` / `Curve force` sliders, the selected centerline segment moved correctly, but the two exterior preview contours could detach from the curve and visually cross each other.

The cause was the preview offset algorithm. It rebuilt the exterior lines by offsetting each sampled segment and intersecting neighboring offset segments. That miter-style reconstruction is fragile on Bezier-like bends because the intersection points can jump away from the sampled curve, especially around tight turns.

## Change

The preview contours are now calculated point-for-point from the same sampled centerline that is drawn on screen:

1. sample the centerline with the active per-segment curve settings;
2. compute a local tangent at each sample;
3. offset the sample along the local normal by the exterior half-width;
4. draw those two sampled offset polylines.

This keeps the visible contours glued to the waypoint curve while the sliders are moved.

## Scope

This is a preview/snap correction only. It does not change mesh generation or the final Apply pipeline.

## Validation

Added a regression test checking that the two preview edges have the same number of samples as the curved centerline and remain exactly one half-width away from every centerline sample.
