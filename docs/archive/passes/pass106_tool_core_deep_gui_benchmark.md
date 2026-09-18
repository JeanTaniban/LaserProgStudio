# Pass106 — Tool Core deep GUI/gizmo benchmark

This pass extends the `Tool Core Diagnostic` tool into a deeper UI/gizmo benchmark.

## Approaches tested

- **vtkGlyph3DMapper-style cache**: one glyph mapper, one sphere source, `vtkPoints` updated in place.
- **Single PolyData point cloud**: one point-cloud actor using point rendering as a safe fallback.
- **Pooled handle actors**: pre-created handles, moved/hidden during interaction.
- **Batched line PolyData**: one line-cell mesh for preview lines, arcs and circles.
- **Limited batched labels**: labels are capped and updated only on semantic changes.
- **Actor churn canary**: intentionally bad remove/add actor path, used to prove the diagnostic flags the anti-pattern.

## What the diagnostic measures

- average update time;
- actor creations and removals;
- position-only updates;
- light renders versus full renders;
- detected bugs/flags;
- recommended approach.

## Rules enforced by the benchmark

- No actor creation during drag.
- No actor deletion during drag.
- No face solving during raw mouse move.
- Full render should happen on release, not on every mouse event.
- Text labels must be limited; labels are not a per-frame primitive.

## Expected direction

The benchmark is expected to recommend cached VTK glyphs for true 3D sphere handles when available, with batched PolyData points as fallback. Sketch lines, arcs and circles should use one batched line-cell mesh. Text remains limited and should be updated only when the displayed information changes.

## Diagnostic report

Running **Deep bench** or **Live bench** exports:

```txt
diagnostics/tool_core_gui_benchmark.md
```

This file is intended to be copied back into the conversation when debugging performance.
