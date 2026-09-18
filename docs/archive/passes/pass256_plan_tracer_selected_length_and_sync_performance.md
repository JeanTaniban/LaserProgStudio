# Pass 256 — Plan Tracer selected path length and sync performance

## Selected length

The Plan Tracer inspector now reports the exact combined length of selected
lines, polyline segments, circular arcs and full circles.  Connectivity is
computed from canonical sketch endpoint ids, so end-to-end mixed line/arc
selections are reported as one contiguous chain.

## Performance audit

The audit found three unnecessary update patterns:

1. standalone Point placement invoked the complete topology and face solver;
2. line, arc, circle and half-circle completion requested a second compile after
   the successful compile had already completed;
3. generated faces received new ids on every face solve, forcing unchanged face
   actors to be removed and recreated;
4. each necessary compile re-registered every existing projected actor, even
   when only one point or edge had changed.

The pass replaces standalone point compilation with an incremental point actor
sync, removes duplicate/no-op compile requests, and reuses generated face ids by
stable geometric signature.  A second visual-signature cache keeps unchanged
points, lines, curves, dimensions and faces in place after a valid topology
compile.  The circle/rectangle arrangement solver and its face partitioning
rules are unchanged.

## Synthetic benchmark

Median of five deterministic ToolContext runs compared with v90:

- 80 isolated points: 232.1 ms -> 18.5 ms;
- 40 completed open lines: 232.5 ms -> 174.1 ms.

The benchmark is intentionally synthetic; the Windows runtime remains the final
validation environment.
