# LaserProg v114 — Folding living hinge and deferred preview

## User-visible changes

Folding now defaults to a **living-hinge fold** instead of deforming only the vertices located between two points.

The workflow remains intentionally small:

1. select the mesh;
2. select the face containing the hinge;
3. place the first hinge limit;
4. place the second hinge limit;
5. set the fold angle and Apply.

The two limits define a flexible band across the selected face. The user chooses which outside region stays fixed. The opposite outside region moves as one rigid body.

## Geometry contract

For the living-hinge mode:

- the original distance between the two limits is the hinge neutral-line length;
- the hinge centerline is mapped to a circular arc with the same length;
- transverse cross-sections are transported along that arc;
- the fixed region is left unchanged;
- the moving region receives one rigid transform matching the terminal hinge frame;
- selecting the other fixed side applies the inverse terminal transform, so that side remains unchanged instead;
- fold angles are limited to `-180° … 180°`.

This is suitable for visualising laser-cut living hinges and flexure strips. It is not a material-stress solver, collision solver, or automatic remesher. A hinge band with enough longitudinal vertices produces the smoothest preview. The neutral surface keeps its dimensions; a thick solid still represents the expected inner/outer bending strain of a real fold.

## Performance

Dragging the angle handle or moving the angle slider no longer rebuilds the mesh on every input event.

- Projected curve/limit actors update immediately through incremental coordinate updates.
- The dense target-mesh outline is installed once and is not resubmitted while the angle changes.
- One single-shot timer is restarted after every edit.
- The expensive mesh replacement runs once after **1.5 seconds of inactivity**.
- Apply cancels the timer and computes the current mesh immediately if required.
- Repeated values with an unchanged curve signature do not rebuild an already current preview.
- Headless tests without a Qt event loop execute the preview synchronously so they remain deterministic.

## UX cleanup

The viewport card now contains only:

- the current step;
- one instruction;
- a short status only when useful;
- context actions.

The inspector is empty during picking and exposes only the fold angle, fixed side, flexible width and preview state during the final adjustment step. Older free-curve fields are hidden unless an old Folding result is reopened.

The viewport shows:

- yellow hover edges before selection;
- a blue target outline;
- green and orange hinge limits;
- `FIXED` and `MOVING` labels;
- one blue angle handle;
- the resulting arc curve.

## Compatibility

Folding metadata is upgraded to version 2. Results produced by v107-v113 still reopen in a hidden legacy free-curve mode. Their original source mesh and two control offsets remain serialised and editable.

No Plan Tracer 2D source file was changed in this pass. A representative 59-test Plan Tracer cluster produced the same result in v113 and v114: 49 passes and the same 10 historical failures.

## Verification

- 35 targeted Folding, hover and live-picking tests pass.
- Repeated angle edits use incremental curve updates and do not resubmit the target triangle mesh.
- The strict Creator quality gate passes for all 20 registered tools.
