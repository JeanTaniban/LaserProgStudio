# Pass 232 — Plan Tracer Pattern zero margin and Keep forme

## Goal

When `Edge margin` is set to `0`, Pattern motifs should be allowed to reach the selected face boundary and be clipped by the real face contour.

A new `Keep forme` boolean controls whether the original face outline is preserved.

## Behaviour

### Keep forme ON

This is the conservative/default mode. The selected face outline remains the host boundary. Motif candidates are allowed to overlap the contour when margin is exactly zero, and the generated openings are clipped to the face footprint.

### Keep forme OFF

The selected source face contour is removed from the Plan Tracer result. The union of generated motif cuts is subtracted from the selected-face footprint, and the remaining material polygons become the new direct Plan Tracer faces.

## Implementation notes

- Pattern candidate generation expands the working bounds by half a pitch when `margin <= 0`, so rectangular faces can receive boundary-clipped cells instead of only fully interior cells.
- Cell motifs switch to clipping mode at zero margin, matching slot-style motifs.
- Non-zero margins keep the previous inward safety inset behaviour.
- `Keep forme` is exposed both in the inspector and the Pattern overlay.
- `Keep forme OFF` bypasses the face-hole path and writes material-result faces marked with `plan_trace_2d.pattern.material_result`.

## Validation

- Added `tests/test_pass232_plan_tracer_pattern_zero_margin_keep_form.py`.
- Relevant Plan Tracer motif tests pass: 37 tests.
- `scripts/quality_gate.py` passes.
