# Tool Core GUI/Gizmo benchmark

The benchmark compares cached glyphs, interactive LOD glyphs, batched point clouds, pooled actors, batched linework, hover-only labels, and a bad remove/add reference.
Scores penalize actor churn and full renders because those are the usual causes of slow mouse drags.
The actor-churn case is expected to be flagged; it proves the diagnostic can detect the bad pattern.

## Results

| Approach | Family | Avg ms/update | Actors + / - | Renders light/full | Score | Bugs |
|---|---:|---:|---:|---:|---:|---|
| Single PolyData point cloud | batched-points | 0.0001 | 1/0 | 60/0 | 0.62 | - |
| vtkGlyph3DMapper-style cache | gpu-glyphs | 0.0001 | 1/0 | 60/0 | 0.50 | - |
| Pooled handle actors | actor-pool | 0.0060 | 180/0 | 120/1 | 4.16 | - |
| Glyph cache with interactive LOD | gpu-glyphs-lod | 0.0001 | 1/0 | 60/1 | 0.67 | - |
| Single hover label | labels-hover | 0.0012 | 1/0 | 3/0 | 0.03 | - |
| Remove/add actor reference | bad-reference | 0.0027 | 2400/2400 | 0/40 | 94.00 | Reference anti-pattern: actor churn detected by design |
| Batched line PolyData | batched-lines | 0.0001 | 1/0 | 60/0 | 0.55 | - |
| Limited batched labels | labels | 0.0008 | 1/0 | 3/0 | 0.06 | - |

## Recommendation

Use vtkGlyph3DMapper-style cached glyphs for 3D sphere handles: one mapper, one reusable sphere source, vtkPoints updated in place during drag, low-detail glyph source during interaction when needed, and a full render only on release. Keep batched PolyData for lines/arcs/faces and make text hover-only/deferred.

## Detected issues

- Reference anti-pattern: actor churn detected by design

## Notes

- **Single PolyData point cloud**: Simulates pv.PolyData(points) kept alive; only point coordinates are modified.
- **vtkGlyph3DMapper-style cache**: Models vtkGlyph3DMapper + vtkPoints.SetPoint + Modified(); source sphere is not rebuilt.
- **Pooled handle actors**: Tests the shared GizmoManager contract: no new actors during drag, one full render on release.
- **Glyph cache with interactive LOD**: Models one vtkGlyph3DMapper with an interactive low-resolution sphere source and a high-resolution release source.
- **Glyph cache with interactive LOD**: LOD source switches: interactive=1, release=1.
- **Single hover label**: Text changed 3 time(s); raw mouse moves reuse the previous label 'P2'.
- **Remove/add actor reference**: This is intentionally bad: remove/add actors inside mouse move.
- **Batched line PolyData**: Use one PolyData with line cells for preview edges/arcs/circles instead of one actor per edge.
- **Limited batched labels**: Labels are capped and updated only on semantic changes, not every raw mouse move.

# Tool Core benchmark analysis

Parsed 8 benchmark metrics.
Detected 1 blocker(s) and 0 warning(s).
Generated 5 production rendering decision(s) for the shared tool-core layer.

## Production decisions

### 3D handle rendering
- Selected: **vtkGlyph3DMapper cached glyphs**
- Why: The measured glyph probe is fast enough for 3D sphere handles (0.000 ms/step) while keeping one actor.
- Use for: sphere handles, snap points, selected points, medium/high point counts
- Avoid for: text, per-handle custom meshes recreated on drag

### Large point sets
- Selected: **single PolyData point cloud**
- Why: The point-cloud path has the lowest live overhead (0.000 ms/step).
- Use for: background points, preview anchors, large unselected point sets
- Avoid for: selected high-visibility 3D handles

### Lines, arcs and circles
- Selected: **batched PolyData line cells**
- Why: Linework stays below the interaction budget (0.000 ms/step).
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

- **BLOCKER / ACTOR_CHURN_FORBIDDEN**: Removing and recreating actors during interaction is catastrophic.
  - Evidence: Remove/add actor reference: 0.003 ms/step, actors 2400/2400
  - Action: Production tools must reuse actor pools, update arrays in place, or hide actors instead of removing them.

## Parsed metrics

| Probe | Avg ms | Actors + / - | Bugs |
|---|---:|---:|---|
| Single PolyData point cloud | 0.000 | 1/0 | - |
| vtkGlyph3DMapper-style cache | 0.000 | 1/0 | - |
| Pooled handle actors | 0.006 | 180/0 | - |
| Glyph cache with interactive LOD | 0.000 | 1/0 | - |
| Single hover label | 0.001 | 1/0 | - |
| Remove/add actor reference | 0.003 | 2400/2400 | Reference anti-pattern: actor churn detected by design |
| Batched line PolyData | 0.000 | 1/0 | - |
| Limited batched labels | 0.001 | 1/0 | - |
