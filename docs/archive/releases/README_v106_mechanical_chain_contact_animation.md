# LaserProg v106 — Mechanical chain contact and continuous animation

## User-visible correction

Generated compound gear chains no longer create two simultaneous contacts between neighbouring intermediate shafts. Each stage receives one of three axial levels, with the configured axial clearance between different levels. Coaxial gears on the same intermediate shaft are joined by a compact hub, so they remain one rigid printable and animatable part.

Test playback also keeps an accumulated driver angle. The visible angle remains wrapped for the inspector, but reduced shafts receive continuous motion and no longer jump back after every input revolution.

## Compatibility

Saved two-layer chains are re-solved when opened. Stable chain, gear, stage and shaft identifiers are preserved, along with driver, rack and attachment references.

## Validation

- 61 Mechanical Motion tests pass.
- New tests verify one physical pitch contact per stage, three-layer scheduling, axial clearance, compound hubs, v105 migration and continuous reduced-stage animation.
- `scripts/quality_gate.py` passes.
