# Tool Core benchmark analysis

Parsed 11 benchmark metrics.
Detected 2 blocker(s) and 0 warning(s).
Generated 5 production rendering decision(s) for the shared tool-core layer.

## Production decisions

### 3D handle rendering
- Selected: **vtkGlyph3DMapper cached glyphs**
- Why: The measured glyph probe is fast enough for 3D sphere handles (1.424 ms/step) while keeping one actor.
- Use for: sphere handles, snap points, selected points, medium/high point counts
- Avoid for: text, per-handle custom meshes recreated on drag

### Large point sets
- Selected: **single PolyData point cloud**
- Why: The point-cloud path has the lowest live overhead (0.302 ms/step).
- Use for: background points, preview anchors, large unselected point sets
- Avoid for: selected high-visibility 3D handles

### Lines, arcs and circles
- Selected: **batched PolyData line cells**
- Why: Linework stays below the interaction budget (0.283 ms/step).
- Use for: sketch edges, arc/circle sampling, temporary previews, snap guides
- Avoid for: one actor per line

### Text rendering
- Selected: **semantic / hover-only labels**
- Why: The benchmark policy treats live label rendering as the slow path, so text must not be part of raw mouse-move redraws.
- Use for: single hover tooltip, dimension label after release, Qt side/overlay panel, static annotations
- Avoid for: dozens of add_point_labels rebuilt in drag, text actor churn

### Render scheduling
- Selected: **light render during drag, full render on release**
- Why: The scoring penalizes full renders because they are a main source of perceived drag latency.
- Use for: mouse move, point drag, preview drag
- Avoid for: full scene rebuild while dragging

## Findings

- **BLOCKER / TEXT_LABELS_TOO_SLOW**: Live viewport text labels are too slow for mouse-move interaction.
  - Evidence: limited text labels: 31.879 ms/step
  - Action: Do not update PyVista/VTK labels during drag. Use hover-only labels, Qt overlay labels, or deferred labels updated on release.
- **BLOCKER / ACTOR_CHURN_FORBIDDEN**: Removing and recreating actors during interaction is catastrophic.
  - Evidence: actor churn canary: 199.008 ms/step, actors 240/216
  - Action: Production tools must reuse actor pools, update arrays in place, or hide actors instead of removing them.

## Parsed metrics

| Probe | Avg ms | Actors + / - | Bugs |
|---|---:|---:|---|
| Single PolyData point cloud | 0.000 | 1/0 | - |
| vtkGlyph3DMapper-style cache | 0.000 | 1/0 | - |
| Pooled handle actors | 0.021 | 180/0 | - |
| Remove/add actor reference | 0.017 | 2400/2400 | - |
| Batched line PolyData | 0.000 | 1/0 | - |
| Limited batched labels | 0.003 | 1/0 | - |
| batched PolyData points | 0.302 | 1/0 | - |
| vtkGlyph3DMapper cached spheres | 1.424 | 1/0 | - |
| batched line PolyData | 0.283 | 1/0 | - |
| limited text labels | 31.879 | 1/0 | Average step above 16 ms; likely visible lag |
| actor churn canary | 199.008 | 240/216 | Actor churn detected by design; production tools must avoid this pattern |