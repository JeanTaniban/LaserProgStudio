# Pass 321 — Mechanical editing, curve drag, phase and Apply lifecycle

## User-facing corrections

- The selected construction face no longer locks or aligns the camera. Mechanical geometry remains coplanar, while normal orbit stays available throughout creation, editing and testing.
- A mechanical source selected before opening the tool now produces an explicit **Edit / New assembly / Cancel** decision. New assembly preserves the old mechanism and reuses its construction plane.
- Studio's generic preview Apply path is detected during tool cleanup. A successfully committed assembly is no longer overwritten by the red recoverable-draft path.
- Drivers and attached moving parts now receive persistent, labelled projected overlays. Attached meshes are outlined and linked to their motion source.
- Bézier control-point dragging uses a dedicated high-frequency overlay path. Only the curve and handle links update during drag; gear solving and mesh regeneration run once on release.
- Gear neutral phases are computed from each stage's actual centre-line angle in the construction-plane U/V frame. A driver tooth faces a driven gap for straight and curved routes. Backlash is now removed symmetrically from both flanks, so the rendered tooth centre remains equal to the solved phase.

## Architecture

- `mechanical_motion/opening.py`: startup decision boundary and Qt prompt isolation.
- `mechanical_motion/interactions.py`: drag/release policy; no solver work during curve drag.
- `mechanical_motion/rendering.py`: fast Bézier refresh plus persistent driver/moving-part overlays.
- `mechanical_motion/gear_solver.py`: direction-aware tooth/gap neutral phase.
- `mechanical_motion/session.py`: committed-state comparison used by the generic host Apply lifecycle.
- `mechanical_motion_tool.py`: lifecycle coordination only; camera release and startup resolution delegation.

## Validation

- `tests/test_pass319_mechanical_motion_tool.py`
- `tests/test_pass320_mechanical_workplane_test_overlay.py`
- `tests/test_pass321_mechanical_edit_curve_phase_apply.py`
- 25 targeted mechanical tests passed.
- `scripts/quality_gate.py`: passed.
- The first failure in the full historical suite remains the unrelated stale Transform renderer assertion in `test_pass1013_transform_gizmo_line_point_renderer.py`.
