# LaserProg v110 — Cloth architecture foundation

This release starts the Cloth surface editor without exposing an unfinished toolbar tool.

Implemented foundations:

- complete French product and technical specification in `docs/tool_creator/24_cloth_tool.md`;
- neutral tracing API shared by future drawing tools;
- Plan Tracer mode normalization migrated to the shared contract;
- piecewise-planar Cloth document with points, lines, arcs, polylines, panels, folds and seams;
- separate workflow, primitive and fold state machines;
- manifold/planarity/fold validation;
- rigid panel unfolding that preserves lengths;
- surface-only folded and flat mesh generation;
- versioned editable metadata;
- headless Apply plan containing the current-scene mesh and requested flat-pattern scene output.

The interactive Cloth Creator adapter is intentionally deferred until drawing-plane picking, overlays, incremental rendering and atomic multi-scene creation are available end to end.

Validation:

- 14 Cloth architecture tests pass;
- 46 Cloth/API compatibility tests pass;
- static quality gate passes.
