# Smart Surface Selection API — v151 incremental solver and progressive cache

## Scope

The API remains isolated from Cloth. This pass replaces repeated Auto solves,
adds bounded progressive caches and keeps the dedicated test tool as the only
interactive consumer.

## Accessibility field

`SurfaceAccessibilityField` stores the minimum minimax cost required to reach
each face from one seed. The path cost is the maximum crossing cost encountered
along that path. A minimax Dijkstra traversal therefore solves all continuity
thresholds at once.

The field contains:

- one cost per mesh face;
- faces sorted by required continuity cost;
- corresponding sorted costs for binary threshold lookup;
- traversal counters and elapsed time;
- mesh geometry signature, profile and exclusions.

`faces_at(tolerance)` uses a binary search and returns the prefix accessible at
that continuity.

## Incremental Auto sweep

Auto retains forty user-facing continuity samples. Internally:

1. one accessibility field is built or retrieved;
2. each level reads a prefix count with `bisect_right`;
3. repeated counts are grouped into stable plateaus;
4. area, boundary length, compactness and angular metrics for all nested
   regions are accumulated in one pass;
5. exact boundary loops are built only for the few candidates that can become
   the winner or one of the visible alternatives.

This keeps the semantic behavior of stable-region selection without rebuilding
boundaries and metrics forty times.

## Progressive cache

`SurfaceSelectionCache` is a bounded reusable object. It stores:

- accessibility fields;
- exact Auto results;
- exact manual-tolerance results;
- learned logical-region membership.

Keys include:

- object identifier;
- explicit revision token;
- deterministic geometry signature;
- complete profile signature;
- seed face;
- inclusion/exclusion constraints;
- tolerance for manual results.

### Logical-region reuse

When Auto produces a high-confidence nontrivial region, the cache associates
its member faces with that region. Hovering another member face can reuse the
same topology while recomputing seed-relative metrics. Alternatives are cleared
for a retargeted result because they belong to the original seed.

Logical reuse is deliberately skipped for:

- regions containing one face;
- almost-whole-mesh regions;
- low-confidence regions;
- selections with manual inclusion or exclusion constraints.

The test tool exposes a toggle so correctness can be compared with and without
this optimization.

## Geometry invalidation

Every `SurfaceMeshSnapshot` contains a BLAKE2 geometry signature generated from
all vertex coordinates and triangle indices. Core selection caches use this
signature in addition to the optional application revision token.

The interactive tool also keeps multiple recent snapshots instead of discarding
all other objects whenever one mesh is visited.

## Snapshot precomputation

The immutable snapshot now includes:

- `neighbor_local_angles` aligned with each neighbor list;
- `sliver_factors` per triangle;
- `geometry_signature`;
- existing area and edge lookup aggregates.

The accessibility solve precomputes the seed-relative portion of the crossing
score once per face, then combines it with cached local edge angles.

## Manual continuity

When a `SurfaceSelectionCache` is supplied, manual selection uses the same
accessibility field as Auto. Moving the continuity slider for one seed therefore
does not rerun graph traversal.

Calls without a cache retain the original direct threshold-limited solver for
simple standalone use.

## Constraint behavior

Exclusions are compatible with the incremental field and are part of its key.
Required-face path construction is less naturally monotonic; Auto temporarily
retains the proven forty-level implementation when required faces are active.
This interaction is infrequent and will be redesigned after the unconstrained
hover path is validated.

## Overlay batching

The test tool renders the logical boundary with one `segment_batch` primitive.
The previous implementation created one projected line primitive per boundary
edge, which could dominate click synchronization on complex contours.

## Diagnostic additions

`auto.solve` reports:

- `incremental`;
- `cache_kind`;
- `field_cache_hit`;
- `field_ms` and raw field-build time;
- `sweep_ms`;
- `finalize_ms`;
- field queue pops and crossing evaluations;
- forty compact level records for schema continuity.

The level records no longer represent forty independent solves in incremental
mode; their face counts describe the threshold sweep.

## Known limits

- logical-region reuse is heuristic and must be tested on concave, highly
  curved and overlapping semantic regions;
- required-face Auto still uses the legacy path;
- snapshots still operate on triangles rather than future super-faces;
- region caches are in-memory only;
- the API is not yet integrated into Cloth.
