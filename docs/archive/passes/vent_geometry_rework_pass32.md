# Vent Geometry Rework — Pass 32

This pass fixes regressions and deepens the geometry contract of the Vent Generator.

## Fixes

- Fixed the startup crash introduced in Pass 31: `vent_tool_panel.py` no longer references `self` inside the standalone panel builder.
- Compact/shared-wall mode is now the default for rectangular vents.
- The rectangular bend radius is now derived from the current centerline spacing:
  - compact rectangle: `(inner width + wall thickness) / 2`;
  - non-compact rectangle and round fallback: `(inner width + 2 * wall thickness) / 2`.
- The sampled centerline uses denser circular fillets for cleaner 90° and 180° turns.
- Validation checks the swept sampled corridor, not only editable waypoints.
- Only-walls meshes remain closed/manifold.

## Design Notes

The Vent Generator uses a centerline spacing contract rather than exterior-wall collision in compact mode. This lets two rectangular runs share a wall while still preventing the air channel from crossing or becoming too close.

A clean 180° turn is built from two tangent circular bends. A one-point hairpin is still considered invalid because it has no geometric side/pivot information.
