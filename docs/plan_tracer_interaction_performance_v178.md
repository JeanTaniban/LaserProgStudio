# Plan Tracer 2D — Interaction Performance v178

## Scope

v178 targets two latency classes that became visible as Plan Tracer sketches grew:

1. pointer hover over generated faces;
2. deletion of a generated face or structural sketch entity.

The common architectural issue was global work being performed for a local interaction.

## Hover: root causes

The native selection layer previously projected every selectable Plan Tracer actor from world space to screen space for every hit-test. Filled faces also reprojected every hole polygon. Therefore a `MouseMove` over a large sketch had cost proportional to the entire sketch, and a heavily patterned face could be expensive even when only one local region was relevant.

The same mouse event then continued into Plan Tracer cursor handling, where Modify mode could execute the broader Smart Snap target/alignment path again.

### v178 design

`SelectionManager.hit_test()` now supports a projection-keyed screen-space spatial index.

The index:

- is built from projected actor bounds;
- stores small actors in screen-grid cells;
- indexes face holes independently so hole exclusion remains exact;
- retains a fallback bucket for actors too large to distribute cheaply;
- is invalidated only when selectable geometry changes or the projection/camera signature changes;
- is not invalidated by re-registering non-selectable transient cursor actors.

Exact point/segment/circle/polygon predicates are still applied to the local candidates. The index is only a broad phase.

Modify cursor handling now uses the existing local snap-target screen index for idle hover. Nearby point/edge/curve snapping remains active, but expensive global alignment-target work is not rebuilt for each idle pixel movement. During an actual drag, the complete Smart Snap resolver remains active.

A second O(N) hover path existed in projected-drawing visual synchronization: whenever the hovered face changed, `sync_interaction_state()` scanned every projected primitive to discover that only the old and new hover needed a style change. v178 carries the interaction delta through the native runtime and limits that style synchronization to the old/new hover, selected actors and grabbed actors.

## Hover benchmark

Synthetic headless benchmark using identity projection:

| Scenario | v177 | v178 warm index |
| --- | ---: | ---: |
| 100 faces | ~0.41 ms / hit-test | ~0.08 ms |
| 1,000 faces | ~4.21 ms | ~0.08 ms |
| 5,000 faces | ~21.14 ms | ~0.08 ms |
| 10,000 faces | ~42.51 ms | ~0.08 ms |
| 1 face, 5,000 holes | ~14.89 ms | ~0.005 ms |
| Hover visual-state sync, 10,000 faces | ~3.11 ms | ~0.0024 ms |

The first hit-test after a geometry or camera change must build the index. In the intentionally extreme 10,000-face synthetic case this was approximately 108 ms once; subsequent pointer movement reuses it. This trades repeated per-pixel global work for an explicit rebuild only when the projected scene actually changes.

## Delete: root causes

Three independent costs were present.

### 1. History snapshots

A normal edit could deep-copy the complete `SketchDocument` four times around one history command. `copy.deepcopy()` also traversed immutable tuples and all entity containers recursively.

v178 implements an explicit structural clone for `SketchDocument` and avoids cloning already-detached before/after snapshots again when recording history.

Synthetic sketch with roughly 4,000 points and 4,000 lines:

- v177 clone median: ~53.1 ms;
- v178 clone median: ~2.3 ms;
- improvement: about 23x.

Nested mutable metadata remains detached; immutable coordinate/id tuples can be shared safely.

### 2. Generated-face deletion

Deleting a generated face does not modify its boundary curves. v177 nevertheless ran the complete sketch compiler and then performed redundant synchronization/render work.

v178 treats generated-face-only deletion as a local operation:

- remember the face signature as suppressed;
- remove the generated face and its actor;
- update selection/apply state;
- record one undoable history command;
- render once;
- do not recompile topology.

Deleting a structural entity (point, line, arc, circle, etc.) still recompiles because topology genuinely changed.

### 3. Topology compiler broad phases

Structural deletion still exposed quadratic preprocessing in the sketch compiler:

- duplicate-point merge scanned point pairs globally;
- line intersection insertion scanned line pairs globally;
- line splitting projected every point onto every line.

At 100 independent rectangles, representative phase costs were roughly:

- duplicate-point merge: 16 ms;
- line-pair intersection pass: 54 ms;
- point-on-line split pass: 116 ms.

v178 replaces only the broad phases:

- tolerance-cell spatial hashing for candidate duplicate points;
- bounding-box sweep for candidate line intersections;
- sorted-X range lookup plus Y bounds for candidate point-on-line splits.

The exact geometric predicates, tolerances, ordering of accepted intersection pairs, and resulting entity operations remain unchanged.

## Structural delete benchmark

Representative compile after deleting one structural line from independent rectangles:

| Sketch size | v177 | v178 |
| --- | ---: | ---: |
| 25 rectangles | ~20.8 ms | ~4.4 ms |
| 50 rectangles | ~51.9 ms | ~8.2 ms |
| 100 rectangles | ~194.5 ms | ~17.5 ms |
| 500 rectangles | quadratic growth becomes impractical | ~113.9 ms |

At 100 rectangles the compiler portion is about 11x faster.

## Correctness validation

The compiler optimization was checked against the untouched v177 compiler on 30 deterministic random sketches containing line intersections. For each case the comparison normalized and compared:

- final point coordinates;
- final line-segment geometry;
- generated face count.

Result: 30/30 outputs were identical.

A focused regression suite covering interaction, native selection, Plan Tracer snapping, deletion persistence, motif/curved faces, cursor performance, and sketch topology reports 50/50 passing tests.

New v178 tests additionally cover:

- reuse/invalidation of the projected hit index;
- local projected hover visual-state synchronization;
- indexed hole exclusion for patterned faces;
- local Modify hover snapping without the global idle target path;
- generated-face deletion without topology recompilation;
- bounded history cloning;
- detached `SketchDocument` clone semantics.

## Behavioral guarantees

v178 intentionally preserves:

- visible Modify cursor;
- exact local vertex/edge/curve snapping on hover;
- full Smart Snap behavior while dragging;
- face-hole exclusion during hit-testing;
- undo/redo for deletions;
- full topology recompilation whenever a structural entity actually changes.

The optimization principle is that interaction cost should track the affected local geometry rather than total document size whenever correctness allows it.
