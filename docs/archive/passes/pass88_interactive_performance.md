# Pass 88 - Interactive performance pipeline

This pass adds the optimization layer requested after the boolean cold-start fix.

## Slider debounce

Heavy preview-producing controls no longer recompute on every `valueChanged` event.
Simplify, Relief, Extrude down and Hollow now wait for a short quiet period before
launching their preview. This prevents dozens of expensive mesh updates during one
slider drag while keeping the UI responsive.

## Background workers

A small `BackgroundTaskManager` owns one geometry worker thread and marshals
results back to the Qt main thread with a polling `QTimer`. Worker functions only
receive copied mesh data and never touch Qt widgets, VTK actors or the live scene.

Worker-backed operations now include:

- boolean union / subtract touching / separate;
- Simplify preview;
- Extrude down preview;
- Hollow preview;
- Acoustic diffuser preview.

## Automatic display LOD

The scene renderer now applies a display-only LOD for very dense meshes. It keeps
the original vertex array and only thins the rendered triangle list, so live
transform updates can still replace `polydata.points` safely. The authoritative
`WorkMesh` is not modified; export and geometry operations keep using full data.

Default thresholds can be overridden with:

- `LPS_LOD_THRESHOLD_TRIANGLES`;
- `LPS_LOD_TARGET_TRIANGLES`.
