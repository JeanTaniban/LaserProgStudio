# Plan Tracer sketch kernel architecture

The Plan Tracer is no longer a viewport-only drawing helper.  It is built on a
small pure-Python sketch kernel that owns the geometry/topology rules, while the
Creator API owns overlay, snap, picking, dimensions and visual registration.

This split is intentional: a tool should describe *what* it wants to create, not
reimplement snap candidates, face solving, Qt widgets or curve intersections.

## Module boundaries

| Layer | Module | Responsibility |
|---|---|---|
| Public Plan 2D API | `tool_api.plan2d` | plane helpers, coordinate mapper, plan actors, snap, public sketch facade, dimensions, metrics and curve intent |
| Sketch model | `tool_core.sketch.entities`, `tool_core.sketch.document` | serializable points, lines, arcs, circles, faces, dimensions and snapshot/undo copies |
| Compiler | `tool_core.sketch.compiler` | normalize topology: merge, split, rebuild polylines/faces, attach validation notes |
| Face solver | `tool_core.sketch.face_solver` | classify closed loops, holes and nested islands |
| Validation | `tool_core.sketch.validation` | reference/invariant checks for diagnostics and tests |
| Curve math | `tool_core.geometry.circular_topology` | line/circle/arc intersections and circular arc helpers |
| Snap core | `tool_core.snap.*` | typed snap targets/results, midpoint/intersection/curve snap candidates |
| Dimensions core | `tool_core.dimensions.*` | units, reference picking, passive measurement and label layout |

A Creator tool may import the public API facades.  It must not import Qt,
PyVista, VTK or private renderer/controller objects to implement sketch logic.

## Compiler pipeline

`SketchCompiler.compile(sketch)` applies the same normalization after drawing,
modifying, deleting and undo/redo restore:

1. merge duplicate points within tolerance;
2. remove degenerate straight edges;
3. insert line-line intersection vertices;
4. insert line/curve and curve/curve intersection vertices;
5. split lines at all vertices that lie on them;
6. split arcs at all vertices that lie on them;
7. convert intersected circles into arc chains;
8. remove degenerate curves and duplicate lines;
9. rebuild polylines from the normalized edge graph;
10. solve closed faces, holes and nested islands;
11. validate references and append compact diagnostics to the compile report.

The compiler is UI-free.  It may mutate the sketch topology, but it never creates
widgets, actors or status messages directly.

## Topology invariants after compile

The following invariants are expected after a successful compile:

- every line endpoint references an existing point;
- every arc start/end/control point references an existing point;
- every circle center/radius point references an existing point;
- a point lying on a line or arc is connected by a split edge;
- an intersection between two supported primitives has a real sketch point;
- a circle with split vertices is represented by arc edges so faces can use it;
- closed loops become faces unless their stable signature was suppressed;
- closed loops inside an outer loop become holes;
- islands inside holes become filled faces again;
- dimensions reference live topology or are removed/invalidated by the owning operation.

`tool_core.sketch.validation.validate_sketch(...)` checks the reference and basic
geometry invariants.  It is deliberately conservative: open chains and unused
construction points are valid while the user is drawing.

## Face and hole semantics

A `SketchFace` stores:

- `boundary_entity_ids`: the outer loop entities;
- `polygon_points`: sampled outer polygon points used for display/hit-test;
- `hole_polygons`: sampled polygons for empty loops inside the face;
- `hole_boundary_entity_ids`: the topology that generated each hole.

Deleting a face does **not** delete its boundaries.  Instead the document stores
a stable face signature in `suppressed_face_signatures`; the next compile then
avoids recreating the same fill.

## Curve semantics

Curves are first-class topology:

- `SketchArc` is an edge with start/end/control points;
- `SketchCircle` is a construction entity that becomes a closed polyline when it
  is untouched, or an arc chain when intersections/vertices lie on the circle;
- intersection snap and compile use the same circular topology math, so visual
  snap and persistent geometry do not disagree.

The current curve kernel supports point-on-arc split, line-circle, line-arc,
circle-circle, circle-arc and arc-arc intersections.  Future work should focus on
visual triangulation quality, editable dimensions and constraint solving rather
than duplicating curve math in tools.

## Undo/redo rule

Undo/redo is snapshot based at the Plan Tracer level.  A single user action must
record one snapshot pair even if the compiler performs many internal operations
such as splitting several edges and rebuilding faces.  Compiler-generated details
must not appear as separate undo steps.

## Documentation rule for future passes

When adding a new sketch capability, update the relevant layer and this document:

- model/entity change → `tool_core.sketch.entities` / `document`;
- topology normalization → `tool_core.sketch.compiler`;
- public author-facing API → `tool_api.*` facade plus `00_api_map.md`;
- visual registration → `tool_api.plan2d.actors` and Plan Tracer doc;
- user workflow → `17_plan_tracer_2d.md`.


## P217 metric overlay integration

Metric placement is now a complete temporary transaction for the main drawing
primitives.  After the visual click placement, tools can show an API-owned metric
overlay, edit fields, rebuild from a clean base snapshot, then validate the final
geometry as one undoable action.

The metric subsystem is deliberately split across `tool_core.metrics` modules:

- `types.py` for field/session dataclasses;
- `parser.py` for unit parsing and formatting;
- `session.py` for standard Line/Rectangle/Circle/Half-circle/Arc sessions;
- `geometry.py` for pure 2D reconstruction helpers;
- `tool_api.metrics` for the public overlay-building facade.

Creator tools should not implement native text widgets or unit parsing.  They
should accept `on_overlay_field_changed(...)` commits and delegate value parsing
to `tool_api.plan2d.metrics.parse_metric_value(...)`.
