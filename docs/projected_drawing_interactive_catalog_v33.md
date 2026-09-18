# Projected Drawing 2D — interactive catalog v33

This version adds the first interaction layer to the projected 2D API while keeping the VTK graphics non-pickable and persistent.

## Public interactive declarations

- `interaction="fixed"`, `"selectable"` or `"grabbable"` on point, line, circle, arc, polyline and face actors;
- `handle(...)` for screen-constant point handles;
- `drag_arrow(...)` for directional translation arrows;
- `ProjectedActorKind`, `ProjectedInteraction`, `ProjectedHandleShape`, `ProjectedDragConstraint` and `ProjectedVisualState` enums;
- owner-scoped snapshots and metadata remain the public output contract.

## Historical catalog coverage

The projected renderer now reproduces the old actor kinds:

- point;
- line;
- circle;
- arc;
- polyline;
- filled/custom face.

It also reproduces the eleven historical point/handle forms:

- solid;
- ring;
- target;
- diamond;
- square;
- arrow;
- axis;
- chevron;
- triad;
- minimal;
- translate arrow.

## Drag behaviour

- regular grabbable actors use the native free world-delta path;
- handles support free, XY-plane, X-axis, Y-axis and Z-axis constraints;
- X/Y/Z movement is derived from the projected screen axis, so a Z arrow remains usable even when pointer world coordinates are sampled on the ground plane;
- hover, selection, grabbed and release states update the persistent handle actor without replacing it;
- mixed Shift-selections keep regular actors moving while constrained handles apply their own axis rule.

## Gizmos Catalog

`GizmoCatalogTest` replaces the automatic scene carousel with an explicit inspector choice. Interactive scenes remain present until the user selects another test.

Available tests cover:

- overview;
- handle shapes;
- actor kinds;
- interaction modes;
- drag arrows;
- dense points;
- dense lines;
- dense faces;
- dense mixed scene.

Benchmarks are now manual through **Benchmark selected** or **Benchmark all**.
