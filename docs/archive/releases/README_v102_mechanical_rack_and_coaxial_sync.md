# LaserProg v102 — Coaxial synchronization and rack-and-pinion

This release fixes the kinematic identity of compound shafts and introduces the first linear mechanism in MEC.

## Rigid coaxial shaft invariant

Two gear bodies that share the same construction-plane axis and touch or overlap along the plane normal are now treated as one rigid shaft. MEC canonicalizes these groups:

- when an existing assembly is loaded;
- after gear or chain geometry changes;
- before solving Test motion;
- before generating preview meshes.

The canonical shaft identifier is propagated to gears, stages, chains, drivers, and attachments. Legacy assemblies with visually fused gears but distinct `shaft_id` values therefore repair themselves when reopened. A compound shaft is emitted as one generated mesh and receives one actor transform in Test, eliminating different speeds between stacked gears.

## Rack-and-pinion element

The Create toolbar and inspector now expose **Rack and pinion**. Its workflow is explicit:

```text
SELECT / Rack
  ├─ selected gear available ─────────────> PLACE_RACK_START
  └─ no selected gear ─> PICK_RACK_PINION ─> PLACE_RACK_START

PLACE_RACK_START ─> PLACE_RACK_END ─> SELECT
```

The user selects the pinion mesh, then clicks two points to define rack direction and length. MEC snaps the neutral pitch line tangent to the pinion pitch circle and inherits the pinion module and pressure angle.

Rack parameters include body height, thickness, and backlash. Start/end projected handles remain editable, and moving or resizing the pinion re-snaps connected racks.

## Real linear simulation

The kinematic state now contains both rotary and linear quantities:

- shaft angle in degrees and shaft speed in RPM;
- rack displacement in millimetres and rack speed in millimetres per second.

For a pinion pitch radius `r`, a shaft angle `θ` produces the no-slip rack travel `s = rθ`, with the sign derived from the construction-plane normal, contact side, and rack direction. Both scrubbed previews and the VTK live Test path translate the rack without rebuilding its mesh every frame.

## Linear Attach outputs

A rack can be selected as an Attach source. Attached scene parts inherit its translation while preserving their orientation. Attachments now persist a generic `source_element_id` in addition to legacy gear/driver fields. The kinematics layer resolves a reusable element motion transform, so future mechanism types can become Attach sources without adding another attachment schema field.

## Extension direction for more complex structures

The current motion-output layer distinguishes the transform produced by an element from the geometry used to draw it. This is the foundation for later elements:

- belt and pulley: rotary-to-rotary relation with same-direction or crossed-belt sign;
- worm and wheel: perpendicular rotary axes and ratio from worm starts / wheel teeth;
- cam and follower: angle-dependent linear displacement law;
- crank-slider / connecting rod: constrained nonlinear translation;
- lead screw: rotary-to-linear pitch conversion.

Each future element should own its geometry and constraint parameters, then expose one rotary or linear transform through the common element-motion resolver. It must not directly manipulate scene actors or duplicate Test logic.

## Verification

- 49 focused MEC tests pass across passes 319–324.
- 8 pass-324 tests cover legacy coaxial repair, identical shaft speed, compound preview grouping, rack tangent snapping, no-slip travel and speed, closed rack geometry, persistence, linear attachments, workflow states, chain-topology migration, and real tool creation clicks.
- `python scripts/quality_gate.py` passes: compilation, structure, architecture, API boundaries, tool migration, product audit, cleanup, and product-tree guard.
- The repository-wide suite still reaches the unrelated pre-existing pass-1013 transform-gizmo assertion after 212 passing tests; excluding it reveals other historical catalog-registration failures unrelated to MEC.
