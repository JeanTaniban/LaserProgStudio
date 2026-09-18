# Folding v129 validation

## Functional coverage

- sparse two-triangle sheet gains real curved stations;
- exact hinge boundaries are inserted into crossing faces;
- generated UVs remain aligned with generated vertices;
- zero-angle living hinge returns the original topology exactly;
- preserve mode keeps a disconnected internal tetrahedral detail rigid to
  floating-point precision;
- uniform mode visibly deforms the same detail;
- deformation behaviour persists through `folding_source` schema 5;
- the inspector exposes and applies the behaviour switch;
- legacy free-curve, living-hinge, complex profile, extended-angle, grouped
  multi-mesh and selection-opening tests remain green.

## Representative measurements

- sparse source: 4 vertices / 2 triangles;
- automatically refined result: 297 vertices / 548 triangles with 21 distinct
  curve-height stations;
- isolated-detail maximum pair-distance error:
  - uniform: about 0.100 mm on the test feature;
  - preserve structure: below `9e-16` mm;
- 4,000-triangle planar grid, headless CPU geometry pass:
  - uniform: about 0.087 s;
  - preserve structure: about 0.134 s.

The complete application suite retains the same 63 pre-existing failures as the
v128 baseline, while the new release adds four passing Folding regressions.
