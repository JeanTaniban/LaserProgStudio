# LaserProg v83 — Projected Overlay Scene Rebuild Reattach

This pass fixes a shared Projected Drawing 2D overlay failure affecting Plan Tracer 2D and Texture Projection.

## Fixed

- Cached `vtkActor2D` overlays are now reattached automatically if a PyVista / VTK scene rebuild clears renderer props directly.
- The repair applies to:
  - Plan Tracer 2D projected handles / guides,
  - Texture Projection projected overlays,
  - Split / projected drawing based modifiers,
  - any Creator tool using `ctx.projected_drawing`.
- The normal no-op / camera-only fast paths remain enabled, but they no longer keep a cleared overlay invisible.

## Diagnostics

New projected overlay diagnostics:

- `renderer.reattach_missing_actors`
- `renderer_reattach_count`
- `last_renderer_reattached_actors`

## Validation

- Targeted Projected Drawing actor reattach regression test: passed.
- Texture Projection projected drawing migration tests: passed.
- Plan Tracer projected drawing migration tests: passed.
- Modifier projected drawing tests: passed.
- `scripts/quality_gate.py`: passed.
