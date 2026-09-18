# LaserProg v85 — Overlay Deep Diagnostics

This version adds heavy debug instrumentation to understand why Plan Tracer 2D and Texture Projection overlays are invisible.

## What to test

1. Enable debug mode in LaserProg.
2. Open Plan Tracer 2D.
3. Click a face.
4. Place a few points.
5. Open Texture Projection and try to display its projection frame.
6. Close/export diagnostics.

## Files to send back

Please send:

- `diagnostics/projected_overlay_debug.jsonl`
- `diagnostics/plan_trace_2d_timings.md`
- `diagnostics/plan_trace_2d_timings.json`
- `diagnostics/application_performance_audit.md`
- `diagnostics/laserprog_studio_v18.log` or the latest normal app log

## New information in diagnostics

The trace now records the whole overlay state chain:

```text
tool primitives -> ProjectedDrawingManager -> ProjectedDrawing2D renderer -> VTK/PyVista actors -> projection -> visibility
```

It also records Creator UI fallback/persistent painter events, because Plan Tracer 2D and Texture Projection share the same overlay infrastructure.
