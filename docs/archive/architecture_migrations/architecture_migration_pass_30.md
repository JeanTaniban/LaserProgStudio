# Architecture Migration Pass 30 — Vent geometry stabilization

This pass fixes the audio vent generator after real-world serpentine tests.

## Problems addressed

- Generic smoothing could fold a duct back onto itself at tight U-turns.
- Clearance validation could miss the footprint of the segment currently being added.
- Flared openings needed to be checked as local widened footprints, not as a global duct width.
- Rectangular `Only walls` mode generated side faces but not closed wall solids.

## Changes

- Added `planar_tools/vent_path_geometry.py`.
- Vent centerlines now use circular tangent bends for generated preview/mesh sampling.
- Vent validation checks both editable waypoints and the sampled final corridor.
- Candidate clamping now validates the whole proposed corridor, including the active ADD segment.
- A minimum bend radius is enforced so a single waypoint cannot create an impossible 180° fold.
- `Only walls` now creates closed side-wall solids by adding wall-thickness caps along each wall strip.

## UX contract

- A compact 180° path should be drawn with enough pivot geometry to fit the bend radius.
- If the requested waypoint would make the duct cross itself or violate wall clearance, the point is clamped or the operation is rejected.
- Outlet flare is still local to the finalized outlet and is only activated after double-click finalization.

## Tests

Added `tests/test_vent_geometry_stabilization_pass30.py`.
