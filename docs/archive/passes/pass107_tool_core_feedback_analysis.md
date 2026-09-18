# Pass107 - Tool Core benchmark feedback analysis

This pass consumes the benchmark feedback returned from Pass106 and converts it into enforceable rendering policy for the shared GUI/tool-core layer.

## Returned benchmark verdict

- Launch log: OK
- App log: OK
- Parsed metrics: 11
- Blockers: 2
- Warnings: 0

## Critical findings

- **TEXT_LABELS_TOO_SLOW** (blocker): Live viewport text labels are too slow for mouse-move interaction.
  - Evidence: limited text labels: 31.879 ms/step
  - Action: Do not update PyVista/VTK labels during drag. Use hover-only labels, Qt overlay labels, or deferred labels updated on release.
- **ACTOR_CHURN_FORBIDDEN** (blocker): Removing and recreating actors during interaction is catastrophic.
  - Evidence: actor churn canary: 199.008 ms/step, actors 240/216
  - Action: Production tools must reuse actor pools, update arrays in place, or hide actors instead of removing them.

## Production choices

- **3D handle rendering**: vtkGlyph3DMapper cached glyphs
  - The measured glyph probe is fast enough for 3D sphere handles (1.424 ms/step) while keeping one actor.
- **Large point sets**: single PolyData point cloud
  - The point-cloud path has the lowest live overhead (0.302 ms/step).
- **Lines, arcs and circles**: batched PolyData line cells
  - Linework stays below the interaction budget (0.283 ms/step).
- **Text rendering**: semantic / hover-only labels
  - The benchmark policy treats live label rendering as the slow path, so text must not be part of raw mouse-move redraws.
- **Render scheduling**: light render during drag, full render on release
  - The scoring penalizes full renders because they are a main source of perceived drag latency.

## Implementation added in Pass107

- Added `tool_core/diagnostic/analysis.py` to parse benchmark markdown and produce decisions/finding codes.
- Added deterministic benchmark cases for interactive LOD glyphs and hover-only labels.
- Added live viewport probes for cached glyph LOD and a single hover text label.
- Added diagnostic panel actions: `Analyze` and `Analyze file`.
- Exported reports now include a `Tool Core benchmark analysis` section.

## Policy for the next migration

1. Handles: use `vtkGlyph3DMapper` cached glyphs when true sphere handles are needed.
2. Large unselected point sets: use a single batched PolyData point cloud.
3. Lines/arcs/circles/faces: use batched PolyData line cells and one mesh per visual family.
4. Text: do not use `add_point_labels` inside mouse move. Use hover-only text, Qt overlay text, or update labels after release.
5. Actor churn: production tools must never remove/recreate actors during drag.
6. Render scheduling: light render during drag, full render only after release or semantic changes.