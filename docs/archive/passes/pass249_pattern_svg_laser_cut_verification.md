# Pass 249 — Pattern/SVG laser-cut verification

## Goal

Investigate the reported symptom where a Plan Tracer pattern looks correct in LaserProg/Falcon Design Space but cuts with shifted or unstable zones on the laser.

This pass focuses on two risk areas:

1. Plan Tracer Pattern generation, especially zero-margin motifs and `Keep forme OFF` material-result faces.
2. Falcon SVG export, especially importer-fragile path data.

## Findings

### Pattern generation

- Zero-margin motif openings are intentionally clipped to the selected face boundary.
- All motif families were verified with margin `0`, rotation, and non-default aspect ratio.
- Generated openings remain valid polygons and stay inside the selected face footprint.
- `Keep forme OFF` still builds real sketch linework, survives sketch recompilation, and produces an apply/exportable mesh.

### SVG export

The previous v77 export already avoided the main Falcon pitfalls:

- real-size `mm` SVG;
- no `transform`/`matrix`;
- one cut ring per SVG `<path>`;
- smaller/inner rings exported before larger rings.

A remaining fragility was found: boolean/3MF geometry can leave redundant, duplicated, or perfectly collinear vertices in SVG paths. These micro-segments are visually invisible but can cause CAM software to optimise/cut a path less predictably.

## Changes

- SVG path coordinates are snapped to a `0.001 mm` grid.
- Cut/fill rings remove duplicate consecutive vertices.
- Cut/fill rings remove only genuinely collinear intermediate vertices.
- Cut paths no longer emit an explicit final `L` back to the starting point before `Z`.
- Duplicate cut rings are de-duplicated before writing SVG paths.
- Cut order remains stable: small rings first, then larger rings.

## Tests added

- `tests/test_pass240_pattern_svg_verification.py`
  - verifies all Pattern motif kinds at zero edge margin;
  - verifies `Keep forme OFF` material-result faces still compile and build an apply mesh.
- Extended `tests/test_falcon_svg_export.py`
  - verifies noisy/duplicated outlines export as one clean path;
  - verifies no transform/matrix output;
  - verifies no compound path for cut rings.

## Validation

- `python scripts/quality_gate.py` → OK
- `python -m pytest tests/test_falcon_svg_export.py tests/test_pass240_pattern_svg_verification.py tests/test_pass232_plan_tracer_pattern_zero_margin_keep_form.py tests/test_pass1011_plan_tracer_motif_geometry_validity.py -q` → `29 passed`

## Notes

This pass reduces software-side causes of cutting shifts. If a real cut still shifts after this version, the remaining likely causes are mechanical or CAM-order related:

- released islands moving during cut;
- air assist pushing small pieces;
- honeycomb bed support movement;
- Falcon Design Space path optimisation cutting outer contours too early;
- insufficient tab/bridge geometry for dense zero-margin patterns.
