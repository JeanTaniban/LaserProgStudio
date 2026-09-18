# 21 — Projected drawing 2D API

`laserprog_studio.tool_api.projected_drawing` draws world-space geometry and lightweight interactive handles as persistent 2D viewport graphics. It remains separate from the historical `ctx.preview`, `ctx.gizmos` and Creator actor painter, so tools can be migrated progressively.

## Public entry point

```python
from laserprog_studio.tool_api import projected_drawing as draw2d

scene = ctx.projected_drawing.for_tool(self.id)
scene.replace_all(
    (
        draw2d.point("cursor", (0.0, 0.0, 0.0)),
        draw2d.line("preview", (0.0, 0.0, 0.0), (20.0, 0.0, 0.0)),
        draw2d.face(
            "face0",
            ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (14.0, 12.0, 0.0)),
            fill_opacity=0.24,
        ),
    )
)
```

No VTK, PyVista or Qt object is accepted or returned.

## Unit primitives

All positions are world coordinates `(x, y, z)`.

| Factory | Geometry | Typical use |
|---|---|---|
| `point(id, position, ...)` | one point | cursor, selected point, moving handle |
| `line(id, start, end, ...)` | one segment | dynamic preview |
| `polyline(id, points, ...)` | connected open/closed chain | small editable contour |
| `face(id, vertices, holes=..., ...)` | one polygon, optionally perforated | small editable face |
| `circle(id, center, radius_point, ...)` | sampled circle with circle hit testing | circular actor |
| `arc(id, points, ...)` | sampled open arc | angular actor |
| `handle(id, position, ...)` | screen-constant handle | selectable/grabbable control |
| `drag_arrow(id, position, direction, ...)` | directional handle | constrained translation |
| `text(id, value, position, ...)` | persistent world-anchored label | dimensions, values, warnings |
| `triangle_mesh(id, vertices, triangles, ...)` | indexed triangle surface | renderer-neutral mesh preview |

Colours use `#RRGGBB`. Point sizes and line widths are pixels and therefore remain visually constant during zoom.

Faces may contain holes without flattening them into independent filled polygons:

```python
draw2d.face(
    "plate",
    outer_loop,
    holes=(inner_loop_a, inner_loop_b),
    interaction="selectable",
)
```

`triangle_mesh()` accepts only world-space vertices and triangle indices. It intentionally does not accept VTK or PyVista objects; tools extract their geometry at the application boundary.

## Dense packed primitives

Large static or mostly static scenes must not create one Python object per visual element. The packed factories store many same-style elements in one declaration and one renderer batch:

```python
scene.replace_all(
    (
        draw2d.point_cloud("sketch-points", point_positions, size_px=5.0),
        draw2d.segment_batch("sketch-lines", line_segments, width_px=1.5),
        draw2d.face_batch(
            "sketch-faces",
            polygons,
            fill_opacity=0.25,
            outline_color="#8FD4FF",
        ),
    )
)
```

| Factory | Packed input |
|---|---|
| `point_cloud(id, positions, ...)` | many same-style points |
| `segment_batch(id, segments, ...)` | many independent same-style segments |
| `face_batch(id, polygons, ...)` | many same-style polygons |

Optional `item_ids` preserve application-level element identifiers without creating one renderer declaration per item.

The intended Plan Tracer split is:

- packed clouds/batches for committed sketch points, lines and faces;
- a few unit primitives for cursor, active preview and selected elements;
- `update_many()` for related unit-primitive changes in one revision and one renderer synchronization;
- explicit packed-coordinate patches when only a few items inside a dense batch move.

## Registry operations

```python
scene = ctx.projected_drawing.for_tool(self.id)

snapshot = scene.replace_all(primitives)
scene.add(primitive)
scene.add_many(primitives)
scene.update(updated_primitive)
scene.update_many((updated_cursor, updated_preview))
scene.patch_point_cloud("sketch-points", ((point_index, new_position),))
scene.patch_segment_batch("sketch-lines", ((segment_index, (new_start, new_end)),))
scene.patch_face("editable-face", ((vertex_index, new_position),))
scene.patch_face_batch("sketch-faces", ((face_index, updated_polygon),))
scene.update_positions({"cursor": new_cursor, "label": new_label_position})
scene.hide("primitive-id")
scene.show("primitive-id")
scene.remove("primitive-id")
scene.remove_many(("a", "b", "c"))
scene.set_visible(False)
current = scene.snapshot()
current_item = scene.get("primitive-id")
all_items = scene.items()
scene.clear()
```

`update_many()` is important for interactive unit primitives: several changed declarations are journaled under one revision and cause only one synchronization. For packed primitives, the `patch_*` methods carry exact changed coordinates to the renderer, avoiding an O(n) comparison of the whole cloud/batch. Packed references can use integer indices or stable `item_ids`. Face patches must preserve the number of vertices; structural changes still use `update()` or `replace_all()`. Unknown identifiers, out-of-range indices and duplicate identifiers are rejected explicitly.

A snapshot contains the owner, monotonic revision, visibility and immutable primitive declarations. It also exposes filtered views for unit primitives and packed collections: `points`, `lines`, `faces`, `point_clouds`, `segment_batches` and `face_batches`.

## Rendering and performance contract

The renderer:

1. groups declarations by kind, style and layer;
2. keeps `vtkActor2D`, topology and NumPy display buffers persistent;
3. represents a same-style point batch with one VTK poly-vertex cell;
4. triangulates filled faces into stable indexed triangles; convex loops use a direct fan and concave loops use constrained Delaunay triangulation;
5. keeps the original face point array, so coordinate patches update points without rebuilding triangle cells;
6. projects complete batches through camera-matrix NumPy operations instead of one VTK call per point;
7. coalesces fragmented style batches into one matrix projection pass per image;
8. tracks primitive spans inside batches;
9. applies packed coordinate patches directly to affected array indices;
10. on camera changes, reprojects all coordinates but never rebuilds topology or actors;
11. skips actor removal/reinsertion when the current renderer order already matches the requested order.

`vtkPolyDataMapper2D` can fan-tessellate a concave polygon from one vertex, creating crossing wedges. Projected Drawing therefore sends explicit triangle indices. Coordinate patches preserve that topology and remain proportional to the number of changed vertices. Structural face edits—adding/removing vertices or polygons—recompile the affected declaration.

## Recommended usage for Plan Tracer

Do not call `replace_all()` for every mouse move. Keep committed geometry in packed batches and dynamic geometry in separate unit primitives:

```python
scene.replace_all((committed_points, committed_lines, committed_faces, cursor, preview))

# During pointer movement:
scene.update_many((new_cursor, new_preview), render=True)
```

Rebuild packed committed batches only when a point/segment/face is committed, deleted or structurally edited. Camera movement uses the projection-only path automatically.

## Interaction and lifecycle

The API is no longer render-only: semantic hit targets are now available without making the VTK actors pickable.

Unit points, lines, circles, arcs, polylines and faces accept `interaction="fixed"`, `"selectable"` or `"grabbable"`. The projected VTK actors remain non-pickable; the manager mirrors only the semantic world geometry into Tool Core `ToolActor` entries for native hit testing. This keeps rendering and interaction independent.

Screen-constant handles are created with:

```python
handle = draw2d.handle(
    "origin",
    (0.0, 0.0, 0.0),
    shape="target",
    interaction="grabbable",
    constraint="plane_xy",
)

x_arrow = draw2d.drag_arrow(
    "translate-x",
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    constraint="axis_x",
    color="#F26D6D",
)
```

Supported handle shapes are `solid`, `ring`, `target`, `diamond`, `square`, `arrow`, `axis`, `chevron`, `triad`, `minimal` and `translate_arrow`. Handle visual states are `normal`, `hover`, `selected`, `grabbed` and `disabled`.

A Creator tool that uses constrained handles exposes the registry resolver:

```python
def resolve_drag_positions(self, event, ctx):
    return ctx.projected_drawing.for_tool(self.id).resolve_drag_positions(event)
```

The native Creator runtime synchronizes moved actors and handle states back into the projected registry, then issues one final viewport render. Regular grabbable points, lines, arcs, circles, polylines and faces use free world-delta movement; handles apply their declared axis or plane constraint. X/Y/Z axis constraints convert pointer motion along the projected screen axis back into a world-axis distance, so camera orientation does not disable the Z arrow.

High-level manipulator factories replace the historical `ctx.gizmos` builders:

```python
move = draw2d.translate_gizmo("move", origin)
rotate = draw2d.rotate_gizmo("rotate", origin)
scale = draw2d.scale_gizmo("scale", origin)
plane = draw2d.plane_gizmo("plane", origin, normal=(0, 0, 1))
triad = draw2d.triad_gizmo("axes", origin)
bounds = draw2d.box_bounds_gizmo("bounds", (xmin, xmax, ymin, ymax, zmin, zmax))

scene.add_manipulator(move)
```

Each factory returns an immutable `ProjectedManipulator` containing its primitive declarations and stable handle identifiers. The registry stores the primitives, not a backend object.

`ctx.cleanup_tool(tool_id)` clears declarations, selection actors, persistent VTK actors and the render observer.

## Gizmo Catalog benchmark

Gizmos Catalog contains only this API. A `GizmoCatalogTest` selector keeps one interactive or dense scenario active. Benchmarks are started manually for the selected scenario or for the complete suite, and run visible passes in distinct Qt event-loop turns:

1. show the generated scene;
2. hold it visibly;
3. measure cold/warm compilation, synchronization, camera reprojection and updates;
4. clear the scene;
5. show an empty pause before the next case.

The generated `diagnostics/projected_drawing_2d_benchmark.json` uses schema version 4. Python declaration generation, face precompilation, cold VTK synchronization and repeated samples run in separate Qt turns so the benchmark does not manufacture one large UI stall. The report records packed scenes, complex faces, style fragmentation, exact projected-coordinate counts, projection-group coalescing and direct coordinate-patch costs.
