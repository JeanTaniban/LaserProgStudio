# Pass 320 — Mechanical work plane and multi-actuator test mode

## Scope

This pass hardens the Mechanical Motion Creator tool around a persistent planar reference and expands test mode into a multi-actuator controller.

## Planar placement contract

A mechanism now starts in `pick_plane`. The first viewport click raycasts a real planar model face through the same public Plan Tracer 2D surface API, stores a versioned `MechanicalWorkPlane`, and aligns the camera to that face.

The plane stores its normal, local U/V axes, depth, anchor, and support object identity. Every subsequent gear centre, chain endpoint, Bézier control, shaft marker, driver axis and dragged actor is resolved by scene raycast and clamped back to this frame. Gear extrusion and test rotation both use the stored normal instead of world Z.

Once geometry exists, the plane is locked for the assembly. Resetting the assembly is required before choosing a different face, preventing accidental reorientation of an existing mechanism.

## Separated modules

- `plane.py`: face picking, persistent plane data, local/world conversion and constrained placement;
- `compound_geometry.py`: one connected mesh per shaft, including manifold union of coaxial stages;
- `test_overlay.py`: compact per-actuator RPM overlay;
- `animation.py`: independent angle/speed integration for every driver;
- `kinematics.py`: arbitrary-axis transforms and multi-driver propagation;
- `interactions.py`: planar placement/drag and manual rotation handles;
- `rendering.py`: planar markers and transform-like test overlays.

The Creator runtime remains a lifecycle coordinator. Geometry, input, persistence, kinematics and overlay construction remain isolated from each other.

## Test mode

Entering Test pauses by default and opens a compact overlay in the viewport. Each referenced rotary driver receives an editable signed RPM field. Negative RPM reverses only that driver. Play/Pause, Reset and Exit Test are local overlay actions.

Every actionable driver also receives a planar transform-style rotation ring, arm and draggable handle. Manual dragging pauses live animation and updates only that actuator angle. The preview is always rebuilt from the immutable baseline, so no cumulative transform drift is possible.

Apply and recoverable Cancel always serialize neutral geometry; temporary test angles are never committed into the scene.

## Compound shafts

Intermediate chain shafts still carry two coaxial gears on alternating contiguous layers. Their axial intervals now touch exactly, then receive a small internal overlap before Boolean union. The scene exposes one generated `WorkMesh` per shaft, with compound metadata retaining both logical gear identifiers.

## Validation

- `tests/test_pass319_mechanical_motion_tool.py`: 12 passed;
- `tests/test_pass320_mechanical_workplane_test_overlay.py`: 5 passed;
- combined mechanical regression suite: 17 passed;
- `python scripts/quality_gate.py`: Quality gate OK;
- Creator migration/product audits: 18/18 tools OK, no forbidden imports or critical boundary issue.

The historical global suite still stops first on the pre-existing Transform gizmo source assertion in `test_pass1013_transform_gizmo_line_point_renderer.py`; this pass does not modify that subsystem.
