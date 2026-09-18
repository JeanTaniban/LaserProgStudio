# LaserProg v149 — Smart Surface Selection API

This release introduces an isolated, reusable intelligent surface-selection API
and a dedicated product tool for testing it before any integration into Cloth or
other production tools.

## New shared API

The public `tool_api.surface_selection` facade exposes a headless solver built
on immutable triangular-mesh snapshots. The first implementation provides:

- logical-region growth from a picked triangle;
- a manual Continuity control from 0 to 1;
- an Auto mode that looks for stable selection plateaus;
- Cloth-support and strict-face profiles;
- hard barriers on sharp and invalid topology transitions;
- forced inclusion and exclusion constraints;
- logical boundary edges and loops;
- confidence, curvature and compactness metrics;
- up to three alternative automatic regions.

The core implementation imports no Qt, PyVista or VTK code and is intended to
be reused later by Cloth, engraving, material painting and other tools.

## Selection API test tool

A new hidden-by-default product tool named **Selection API test** (`SST`) is
available from toolbar customization. It does not modify the scene.

- hover previews the proposed logical surface;
- click commits a new seed and region;
- Shift+click forces a triangle into the logical surface;
- Ctrl+click excludes a triangle;
- Auto can be disabled to tune Continuity manually;
- the inspector reports confidence, selected triangle count and curvature;
- optional overlays show the proposed region and its logical boundary.

See `docs/smart_surface_selection_api_v149.md` for the test protocol, API
contract and known limitations.

## Validation

- Static quality gate passed.
- API-boundary, migration, architecture and product audits passed.
- 44 focused API, registry, toolbar, help and architecture tests passed.
- 4 new v149 regression tests cover coplanar regions, curved growth,
  inclusion/exclusion constraints and product registration.

## Previous release

The v148 Duplicate pivot and Folding snap notes are archived in
`docs/archive/releases/README_v148_duplicate_folding_interaction.md`.
