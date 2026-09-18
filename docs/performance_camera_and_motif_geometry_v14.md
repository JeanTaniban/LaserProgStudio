# Performance / geometry pass v14 — camera drag + Plan Tracer motifs

## Camera drag fluidity

The central render scheduler introduced in v9 correctly coalesces expensive scene
refreshes, but it also throttled anonymous `plotter.render()` calls to the normal
optimized budget. VTK camera navigation emits exactly those anonymous render
calls while the mouse is held down, so camera pan/orbit could feel less fluid
than before.

This pass adds an interactive mouse-drag budget in
`laserprog_studio.rendering.render_scheduler.CentralRenderScheduler`:

- normal application refreshes keep the optimized cadence;
- while Qt reports a mouse button down, render requests use a faster interactive
  cadence;
- requests are still coalesced, so geometry refresh storms do not come back.

New diagnostic counters:

- `render.central.mouse_drag_budget`
- `render.central.interactive_fast_path`

## Plan Tracer 2D motif geometry

The reported broken motifs were the slot/clipped families:

- Triangles
- Briques décalées
- Anneaux concentriques
- Fentes horizontales
- Vagues sinusoïdales
- Living hinge droit
- Living hinge treillis
- Living hinge sinueux

The root cause was that several motif candidates were either touching the target
face boundary after clipping, sharing edges with neighbouring holes, or using
fragile single-ring representations. Plan Tracer stores face perforations as
interior `hole_polygons`; those holes must be closed, valid, and strictly inside
the face boundary.

This pass changes the motif generator so the broken families produce stable
interior rings:

- slot-style clipping now uses an inward face footprint instead of clipping on
  the real outer boundary;
- triangles are generated as independent holes with material wall around each
  triangle;
- brick rows no longer emit partial boundary bricks;
- concentric rings are emitted as stable C-shaped bands with one controlled seam;
- sinusoidal motifs clamp amplitude so adjacent slots do not overlap/touch;
- clipped results are cleaned with duplicate/collinear vertex removal before
  becoming hole polygons.

Regression tests validate that all reported motifs generate valid Shapely
polygons inside a triangular Plan Tracer face and do not touch the outer
boundary.
