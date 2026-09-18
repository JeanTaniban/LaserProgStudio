# Pass 47 — Transform translation drag performance

## Problem

In Light UI, dragging an object with the translation gizmo became slow on large scenes. The live drag path still did too much work per mouse move:

- full inspector refresh;
- Box metrics refresh through the inspector;
- full light overlay sync;
- scene-wide smart snap scan over all other mesh vertices;
- immediate PyVista render for every mouse event.

## Fix

Translation drag now uses a lightweight live path:

1. Smart snap targets are cached once at drag start.
2. The drag loop only recomputes the moving selection anchors.
3. Full inspector refresh is skipped during mouse move.
4. Position/light overlay readout is throttled.
5. PyVista rendering is throttled during drag.
6. Full inspector/gizmo/style refresh still runs once at drag release.

## Files

- `src/laserprog_studio/snapping.py`
- `src/laserprog_studio/_window_deps.py`
- `src/laserprog_studio/controllers/transform_drag.py`
- `tests/test_transform_translation_perf_pass47.py`

## Validation

`276 passed, 3 skipped`
