# LaserProg v98 — Mechanical work plane and test controls

## User-visible changes

- Mechanical Motion now begins by selecting a planar model face.
- All gears, chain curves, handles, shafts and driver axes stay constrained to that persistent plane.
- Gear geometry extrudes along the selected face normal, including vertical and inclined faces.
- Test mode opens a compact per-actuator RPM overlay.
- Every actuator receives a planar rotation ring and draggable manual handle.
- Multiple drivers can run at independent signed RPM values.
- Compound double gears are generated as one connected shaft part with no axial gap.
- Apply and Cancel preserve neutral geometry and the selected plane without saving temporary animation transforms.

## Engineering changes

The implementation adds dedicated `plane.py`, `compound_geometry.py` and `test_overlay.py` modules and extends the isolated animation, kinematics, interaction, rendering, serialization and session services. No application-wide input or rendering component was replaced.

See `docs/archive/passes/pass320_mechanical_workplane_test_mode.md` for the detailed architecture and validation report.
