# LaserProg v116 — Folding extended angles

## Change

The living-hinge terminal angle now accepts values from `-720°` to `+720°`. The previous `±180°` clamp has been removed.

## Interaction

The blue terminal handle uses continuous angle unwrapping. Crossing `+180°` continues to `181°`, and crossing `-180°` continues to `-181°`, rather than jumping to the opposite signed half-turn. Numeric inspector edits and restored project metadata use the same limits.

## Geometry

Complete revolutions are preserved in the tangent-angle profile. The neutral line remains length-preserving, the fixed region remains unchanged, and the moving region remains rigid. Values beyond `|180°|` may naturally make the folded mesh intersect itself; Folding warns but does not alter the requested geometry or run collision resolution.

## Validation

Regression coverage includes 270° and 450° curves, rigid-region preservation, serialized values above 180°, clamping at ±720°, and terminal-handle continuity across the ±180° boundary.
