# 16 — Projected Drawing 2D catalog

The built-in **Gizmos Catalog** is the reference and diagnostic tool for the new projected 2D API. It no longer creates the historical `ctx.gizmos`, `ctx.preview` or overlay motifs. Every visible primitive is declared through `ctx.projected_drawing`; interactive primitives are mirrored into Tool Core selection actors only for hit testing and drag state.
Rendering still uses persistent `vtkActor2D` batches. Show and Hide only change visibility, without rebuilding actors.

Only `ctx.projected_drawing` owns viewport content in this catalog. Tool Core selection actors are semantic hit targets only; the visible VTK graphics remain non-pickable. There are no family presets.

## Explicit scenario selector

The inspector exposes a `catalog_test` choice backed by the `GizmoCatalogTest` enum. A scenario remains visible until another one is chosen, which makes hover, selection and drag tests practical. Opening the catalog does **not** start an automatic carousel or benchmark.

Available scenarios:

- **Overview** — representative point, line, arc, face and drag handles;
- **Handle shapes** — all historical point styles: `solid`, `ring`, `target`, `diamond`, `square`, `arrow`, `axis`, `chevron`, `triad`, `minimal` and `translate_arrow`;
- **Actor kinds** — point, line, circle, arc, polyline and filled face;
- **Interaction modes** — fixed, selectable and grabbable variants;
- **Drag arrows** — screen-projected X-, Y- and Z-constrained arrows plus free-XY handles;
- **Dense points**, **Dense lines**, **Dense faces** and **Dense mixed scene** — packed high-volume representations.

All geometry lies on the world **XY plane at `Z=0`**. Camera state is used only to choose the initial centre and readable world scale. Projected `vtkActor2D` content does not participate in `ResetCamera`, so the catalog computes its own readable ground-frame scale.

## Interaction

The public projected primitives can use:

```python
interaction="fixed"
interaction="selectable"
interaction="grabbable"
```

Screen-constant handles use the native Creator interaction path. Hover, selection, grabbed state and release are reflected by colour and size without replacing the VTK actor. Directional handles can constrain motion to `axis_x`, `axis_y`, `axis_z`, `plane_xy` or `free`. Axis drag uses the projected screen direction, so the Z arrow remains usable even when pointer world coordinates are sampled on the ground plane.

The catalog panel reports the current hover, selection and grabbed identifiers. Empty clicks clear the current projected selection according to the normal Creator API policy.

## Benchmarks

Benchmarks are manual:

- **Benchmark selected** runs the performance case corresponding to the active scenario;
- **Benchmark all** runs the complete staged suite;
- **Stop** cancels the current sequence and restores the selected catalog scenario.

Each benchmark case is prepared, compiled, shown, measured and cleared in separate Qt turns. The output remains:

```text
diagnostics/projected_drawing_2d_benchmark.json
```

## Migration strategy

Committed Plan Tracer geometry should use `point_cloud`, `segment_batch` and `face_batch`. Cursor, active preview, selected points and drag handles should stay as a small number of unit primitives. See `21_projected_drawing_2d.md` for the complete API contract.
