# Plan Tracer intelligent additive Mirror — v145

## Contract

Mirror receives a frozen source scope and an infinite two-point axis. It returns
only additions. It must never directly delete, move or rewire source primitives.

- Non-empty selection at activation: mirror the expanded selected topology.
- Empty selection at activation: complete the entire sketch bilaterally.
- Existing counterpart: skip the candidate.
- Entity on the axis: skip it as self-symmetric.
- Crossing open curve: split at every interior axis intersection, then reflect
  every side-contained subcurve.

This is a **bilateral completion** operation. Given source set `S`, axis reflection
`R`, and current sketch geometry `E`, the requested geometric result is the union
`E ∪ R(S)`, with duplicate geometry suppressed. When `S = E`, the final union is
symmetric because it contains both `E` and `R(E)`.

## Geometry kernel

`mirror_geometry.py` is UI-free and uses semantic 2D coordinates.

### Lines

Signed distances of both endpoints classify the line. Opposite signs produce one
exact linear interpolation point on the axis and two reflected subsegments.

### Circular arcs

The three authored arc points recover the exact circle and oriented sweep. The
axis/circle intersections are filtered by the arc parameter interval. Each
subarc is emitted as start, end and exact mid-sweep control point, preserving the
circular primitive rather than flattening it into a polyline.

A degenerate three-point arc falls back to an equivalent cubic Bézier so the
operation remains safe instead of emitting an invalid circle.

### Cubic Bézier curves

Signed distances of the four control points form a cubic polynomial in the curve
parameter. Real roots strictly inside `[0, 1]` are found, deduplicated and used by
de Casteljau subdivision to retain exact cubic subcurves.

### Circles and points

A point on the axis is self-symmetric. A circle is self-symmetric precisely when
its centre lies on the axis; otherwise its centre and radius point are reflected
as one circle, including when the original circle intersects the axis.

## Duplicate suppression

The v145 index avoids the former O(n²) candidate scan:

- quantised position buckets for points;
- canonical supporting-line buckets for line coverage and subsegments;
- centre/radius buckets for circles and circular arcs;
- endpoint and bounding-box filtering before expensive Bézier containment.

Type-aware coverage prevents a line chord from being mistaken for a circle or a
standalone point from being swallowed merely because it lies on an edge.

## UI state machine

`mirror_state.py` owns three explicit states:

1. `AXIS_START`
2. `AXIS_END`
3. `PREVIEW`

Escape from Axis end or Preview restarts the axis. Escape from Axis start exits to
Modify. The compact popover exposes Apply, New axis and Cancel only; selection is
performed beforehand with Modify.

## Commit safety

The service snapshots the complete sketch and its ID counters before insertion.
All additions are created first and the shared topology compiler runs once. On
any exception, the snapshot is restored and no partial symmetry remains. On
success, one history command is recorded, snap geometry is invalidated and the
new entities become the Modify selection.

## Regression scenarios

- asymmetric line crossing the axis;
- exact circular arc crossing and self-symmetric arc;
- cubic Bézier with multiple crossings;
- axis-aligned line, axis point and centred circle;
- whole sketch containing one complete counterpart and one unmatched entity;
- selected-only application through the real Plan Tracer tool;
- asymmetric rectangle spanning the axis and face reconstruction;
- synthetic compiler rejection and full transactional rollback.
