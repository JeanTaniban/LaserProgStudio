# Smart Surface Selection API — v150 performance diagnostic pass

## Scope

The selection engine remains isolated from Cloth. This pass adds enough
instrumentation to locate lag on real complex meshes without guessing, while
correcting three redundant computations that were directly visible in v149.

## Diagnostic capture

The **Selection API test** panel exposes:

- **Capture performance diagnostics**: enable or disable the in-memory trace;
- **Reset**: clear the current trace before reproducing one problem;
- **Export**: write JSONL, JSON summary and Markdown summary files;
- **Last hover**: end-to-end latency for the latest hover operation;
- **Last click**: end-to-end latency for the latest click operation.

Capture is enabled by default in v150. The trace is bounded to the most recent
12,000 events. Mouse moves do not perform synchronous diagnostic disk writes.

## Trace stages

### End-to-end operations

- `hover`
- `click`

Every operation has `operation.start` and `operation.end` entries with an
operation identifier. This makes it possible to reconstruct one complete slow
interaction in the JSONL timeline.

### Picking and snapshot

- `pick.face_at`
- `pick.face_index`
- `snapshot.cache`
- `snapshot.total`
- `core.snapshot.build`

The snapshot build entry reports separate times for vertex conversion,
triangle conversion, triangle geometry, edge incidence and adjacency.

### Selection solver

Manual mode emits `core.select.solve`.

Auto mode emits `core.auto.solve` with:

- total Auto time;
- candidate-generation, grouping and scoring times;
- the selected tolerance and region size;
- one compact timing record for each of the 40 continuity levels;
- region-growth queue pops and crossing evaluations;
- boundary and metric timings per level.

### Overlay and UI

- `render.overlay`
- `sync.total`

`render.overlay` separates selected mesh generation, hover mesh generation,
logical-boundary line generation and projected drawing replacement/rendering.
This is important because a complicated contour may create a large number of
individual line primitives even when the region solver itself is fast.

## Files

- `diagnostics/smart_surface_selection_performance.jsonl`: chronological raw
  events grouped by operation ID.
- `diagnostics/smart_surface_selection_performance.json`: machine-readable
  aggregate statistics, P50/P95/max values and the slowest operations.
- `diagnostics/smart_surface_selection_performance.md`: compact report intended
  to be sent with a bug report.

## Reproduction protocol

1. Start the Selection API test.
2. Reset diagnostics.
3. Hover the same complex region repeatedly for roughly ten seconds.
4. Click that region at least three times.
5. Disable **Show logical boundary** and repeat the same movement and clicks.
6. Export diagnostics.
7. Send the three files and the normal app log.

The comparison with and without the boundary overlay will distinguish solver
latency from projected-overlay latency.

## Confirmed v149 inefficiencies corrected

### Duplicate click solve

`SurfaceSelectionSession.bind(...)` already computed a result. The tool then
called `recompute(...)` immediately afterward, executing Auto twice. v150 uses
exactly one solve.

### Hover proposal recomputed on click

When the click confirms the same object and triangle currently shown in green,
the session adopts that immutable result directly. This should make the blue
commit immediate unless overlay rendering itself is the bottleneck.

### Complete-area sum inside every graph crossing

The v149 crossing score calculated `sum(snapshot.areas)` for every neighbor
visited by the graph. Total and mean area are now cached once in the immutable
snapshot, together with edge lookup maps.

## Still intentionally unchanged

Auto still evaluates 40 continuity levels. The new real-world traces will show
whether the next optimization should be:

- one minimax graph traversal shared by all thresholds;
- caching results by seed/configuration;
- hover throttling/coalescing;
- super-face preprocessing;
- batching logical-boundary overlay geometry;
- or a combination of these.

The next algorithmic pass should be selected from measured user traces rather
than synthetic assumptions.
