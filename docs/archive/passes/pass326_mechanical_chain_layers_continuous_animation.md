# Pass 326 — Mechanical chain layers and continuous animation

## Root causes

1. Chain stages used `stage_index % 2`. For adjacent compound shafts, the gears from stages `N-1` and `N+1` therefore returned to the same axial layer and could form a second unintended pitch contact.
2. `GearChainSpec.axial_clearance_mm` was not applied to generated gear centres.
3. The animation controller wrapped the physical driver angle with `% 360`. Every downstream reduced angle was recomputed from the wrapped input, causing later stages to jump back and appear to rock in place.

## Changes

- Added a three-layer distance-two stage schedule: `0, 1, 2, 0, ...`.
- Applied axial clearance in `MechanicalWorkPlane.gear_center`.
- Added a closed annular/solid compound hub spanning separated coaxial gears.
- Migrated saved chains through the parametric solver on open while preserving identifiers and references.
- Kept animation angles unbounded internally and wrapped only the inspector display angle.

## Tests

`test_pass326_mechanical_chain_layers_continuous_animation.py` covers collision-free contacts, hub generation, saved-chain migration and accumulated animation angles.
