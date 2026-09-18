# Pass 324 — Coaxial shaft repair and extensible linear mechanisms

## Problem repaired

Some stacked gears looked fused but retained different shaft identifiers. The Test solver therefore propagated different angular speeds through what was physically one compound shaft.

`shafts.py` now detects gears that are coaxial in the selected work plane and whose axial bodies touch or overlap. A union-find pass chooses one stable canonical shaft and migrates every dependent reference. This normalization is an invariant at load, edit, solve, and preview boundaries.

## New rack domain and geometry

`RackSpec` stores the neutral pitch-line endpoints, pinion reference, module, thickness, body height, backlash, pressure angle, contact side, phase, and color. `rack_geometry.py`:

- snaps the rack tangent to the pinion pitch circle;
- builds a trapezoidal tooth profile;
- triangulates and extrudes it as a closed mesh;
- computes rack bounds and motion orientation.

## Kinematics

`KinematicState` now reports rack displacement and velocity. The rack/pinion relation uses pitch radius and shaft rotation, so a 90° pinion turn produces `πr/2` of translation. Preview generation, live actor transforms, overlays, and attached parts all consume the same state.

`element_motion_transform()` is the common output boundary for mechanisms. Gear, driver, chain output, and rack sources resolve to either rotation or translation. New mechanism types should extend this resolver instead of adding type-specific motion code to Attach or the renderer.

## UX states

The MEC state machine adds:

- `PICK_RACK_PINION`;
- `PLACE_RACK_START`;
- `PLACE_RACK_END`.

The toolbar, inspector, contextual workflow overlay, scene-mesh selection, projected actors, endpoint drag, Cancel transitions, Apply/Cancel persistence, and element count all include racks.

## Compatibility

Mechanical serialization schema 3 adds racks and generic attachment sources. Missing rack data remains valid for older assemblies. Opening old content also performs coaxial shaft repair before Test.

## Regression coverage

`tests/test_pass324_mechanical_coaxial_rack_structures.py` verifies:

1. touching coaxial gears receive one angle and one RPM;
2. legacy serialized assemblies repair on open and generate one compound shaft mesh;
3. rack pitch-line tangent distance and no-slip motion;
4. manifold rack geometry and schema-3 roundtrip;
5. scene-part linear attachment without rotation;
6. explicit pinion/start/end workflow states;
7. rack pinion migration and re-snap after chain topology changes;
8. end-to-end creation through the actual Creator tool mode and two viewport clicks.
