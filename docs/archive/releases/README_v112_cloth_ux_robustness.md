# LaserProg v112 — Cloth UX and robustness polish

This pass verifies the complete Cloth V1 workflow and hardens the parts most likely to create confusing or expensive interactions.

## UX refinements

- The viewport palette is now stage-aware instead of showing every command at once.
- Opening shows only existing-Cloth/plane choices.
- Plane selection shows only plane choices and Back.
- Drawing shows the six edit modes, Change plane, preview and Apply.
- Polyline completion actions appear only while a polyline is active:
  - `Finish open` after two points;
  - `Close panel` after three points.
- The active mode is visibly checked.
- The palette reports the current primitive, panel/fold/curve counts and Apply readiness.
- Back and Escape leave the initial mesh-plane picker correctly instead of looping in the same state.
- Fold-angle editing is enabled only while a fold is actually selected in Fold mode.

## Performance

- Cloth surface triangulation is cached by document identity and revision.
- Topology validation is cached by document identity and revision.
- Hovering curves or points no longer rebuilds the same surface mesh or revalidates the whole document.
- No-op point moves no longer increment the document revision or trigger a new preview build.
- Point drag renders only when the point position really changes.
- Existing Cloth hover checks the lightweight metadata header before deserializing the complete source document.

## V1 correctness boundaries

Apply is now blocked before mesh generation when the document contains geometry unsupported by Cloth V1:

- panel holes;
- self-intersecting panel contours;
- degenerate three-point circular arcs;
- duplicate panel boundaries;
- closed fold cycles;
- duplicate fold relations on one curve.

The user receives a specific reason in the palette instead of a late triangulation or unfolding failure.

## Packaging and shared overlay repair

The `laserprog_studio.diagnostics` source package, referenced by Projected Drawing, Plan Tracer and performance diagnostics, is restored to the product tree. Its omission from v110/v111 could cause import failures in tests and code paths that load Projected Drawing diagnostics.

Projected Drawing actor reattachment and live-audit helpers now tolerate partially initialized/headless renderer instances. Normal runtime behavior is unchanged; the related static-sync regression test now passes.

## Validation

- 33 Cloth foundation/integration/polish tests pass.
- 16 Projected Drawing/diagnostic regression tests pass.
- A representative 40-test Plan Tracer cluster has the same single historical camera-alignment failure as v111: 39 passed, 1 failed.
- Full suite: 1526 passed, 68 failed, 3 skipped. No Cloth test fails; remaining failures are existing toolbar/UI expectations, the historical Plan Tracer camera-alignment case and tests requiring `manifold3d`.
- Strict quality gate passes with all 20 tools recognized as Creator runtimes.
