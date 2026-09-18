# Projected drawing ground placement and benchmark v29

## Goal

Place the Gizmos Catalog projected drawing scene on the real application floor and create a repeatable diagnostic suite for evaluating the new `vtkActor2D` approach before migrating Plan Tracer.

## Ground placement

- Every catalog and benchmark coordinate is declared on world XY with `Z=0`.
- Camera focal X/Y chooses the initial centre only.
- Camera field of view chooses a readable initial scale only.
- Camera orientation no longer changes primitive orientation.

## Automated benchmark

Opening Gizmos Catalog automatically runs 24 staged cases in separate Qt event-loop turns. The test owner is isolated from the visible sample and is cleaned after every case and when the tool closes.

Measured paths include:

1. Python primitive construction.
2. Pure style/layer batch compilation.
3. Cold `replace_all()` including actor and topology creation.
4. Real VTK frames with unchanged camera state.
5. Real VTK frames after `camera.Modified()`, forcing reprojection.
6. Cached explicit sync.
7. Updating one primitive in a large registry.
8. Replacing identical geometry.
9. Renderer disposal.
10. Style fragmentation up to 128 persistent actors.

The renderer exposes internal diagnostic counters without changing the public API. The generated `diagnostics/projected_drawing_2d_benchmark.json` contains raw samples, percentile summaries, environment and camera metadata, a source fingerprint, actor/batch topology counts, global projected-drawing audit timers and automatic frame-budget crossings.
