# Pass 96 — Plan tracer snap and visible gizmos

## Goal
Improve the Plan tracer workflow so 2D junctions are easier to place and edit.

## Changes
- Added a dedicated snap module: `src/laserprog_studio/planar_tools/plan_trace_snap.py`.
- Plan tracer smart snap now reuses:
  - polygon vertices,
  - segment/curve handles,
  - sampled polygon curves,
  - line endpoints,
  - semi-circle control points and sampled arc points,
  - circle center/radius points and sampled circle points,
  - active construction points while an element is being placed.
- Increased Plan tracer smart-snap tolerance to make junction placement less pixel-perfect.
- Added live hover preview while in ADD modes, before clicking.
- Added snap hint actors: snapped target point, raw cursor point and a link line.
- Replaced PyVista point sprites with real 3D sphere gizmos, lifted slightly toward the camera so they remain visible over coplanar faces and preview fills.
- Updated the Plan tracer panel text/tooltips to explain snap behavior without overloading the panel.
- Added tests for snap-anchor collection, endpoint reuse, snap state cleanup and sphere-gizmo rendering contract.

## Validation
`393 passed, 3 skipped`
