# LaserProg v91 — Plan Tracer selected length and performance

## Selected path length

The Plan Tracer inspector now displays the exact total length of selected
end-to-end sketch edges.  Supported entities are:

- lines and individual polyline segments;
- circular arcs;
- full circles;
- mixed contiguous line/arc selections.

Connectivity is derived from canonical sketch endpoint ids.  The inspector also
reports whether the selection is one contiguous path, a closed path, or several
separate chains.

## Plan Tracer update audit

The performance review found four avoidable update paths:

1. standalone points invoked the complete topology and face solver;
2. several completed drawing gestures requested a second compile;
3. generated face ids changed on every solve, recreating unchanged overlays;
4. every valid topology compile re-registered every point, edge, curve and face,
   even when only one new segment had changed.

The v91 changes keep topology solving where correctness requires it, but perform
incremental projected-actor synchronisation afterward.  A point placed on an
existing line still invokes the compiler so that line is split correctly.

## Synthetic comparison

A deterministic ToolContext benchmark was run five times against the v90 source
and this v91 source.  Median results:

| Scenario | v90 | v91 | Change |
|---|---:|---:|---:|
| 80 standalone points | 232.1 ms | 18.5 ms | about 12.5× faster |
| 40 completed open lines | 232.5 ms | 174.1 ms | about 25% faster |

These figures are synthetic and do not replace validation on the Windows/VTK
runtime, but they confirm that redundant topology and projected-overlay work was
removed.

## Validation

- 9 new selected-length and incremental-sync tests pass.
- 33 targeted Plan Tracer selection/topology/projected-drawing tests pass.
- The broad historical Plan Tracer suite has exactly the same 23 existing
  failures as v90, with the new tests added as passes.
- `scripts/quality_gate.py` passes.
