# LaserProg v115 — Folding complex living-hinge curve

## User-visible changes

Folding is no longer limited to a circular arc. The final step now exposes:

- one blue terminal-angle handle;
- purple curve-shape handles;
- 1, 3, 5 or 7 profile controls;
- a `Reset shape` action;
- S-curves and locally concentrated bends.

The default profile remains identical to the v114 circular behavior. Existing v114 projects therefore reopen without a visual change until a purple handle is moved.

## Geometry

The new centerline is generated from a smooth tangent-angle profile and integrated with unit-length steps. Its neutral length is preserved by construction, even when the profile contains inflection points or negative local curvature.

The two outside regions keep the v114 contract:

- one region is unchanged;
- the other receives one rigid transform;
- its terminal rotation is the global fold angle;
- its translation is the endpoint of the custom centerline.

## Performance

Shape-handle drags update only lightweight Projected Drawing actors. The target mesh is still recalculated once after 1.5 seconds without interaction, or immediately on Apply.

## Persistence

`folding_source` metadata is upgraded to version 3 and stores the profile-angle offsets. Version-2 living hinges migrate to a zero-offset profile, reproducing their original circular arc. Version-1 legacy free curves remain supported.
