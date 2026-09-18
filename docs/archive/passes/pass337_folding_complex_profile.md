# Pass 337 — Folding complex profile

## Goal

Replace the living-hinge-only circular guide with an editable smooth profile without sacrificing neutral-line length, rigid outer parts or deferred mesh performance.

## Implementation

- Added versioned shape-angle controls to `FoldingCurve`.
- Added 1/3/5/7-handle profile detail.
- Interpolated the tangent-angle profile with cubic Hermite segments.
- Integrated the neutral centerline with unit arc-length increments.
- Transported active mesh cross-sections along the sampled local frame.
- Kept the terminal tangent equal to the global fold angle.
- Added purple projected shape handles and an endpoint angle handle.
- Kept mesh rebuilding behind the existing 1.5 s idle debounce.
- Upgraded Folding metadata from version 2 to version 3.

## Regression coverage

`tests/test_pass337_folding_complex_profile.py` verifies:

- S-shaped profiles with positive and negative curvature;
- exact neutral polyline length;
- rigid moving-region distances;
- profile-detail resampling;
- metadata round-trip;
- dynamic Projected Drawing handles.
