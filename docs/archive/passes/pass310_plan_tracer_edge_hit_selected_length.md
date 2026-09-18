# Pass 310 — Plan Tracer edge hit and selected-length repair

## Symptom

Holding Shift and clicking consecutive polyline segments visually targeted the
lines, but the inspector kept `Selected length` at `—`.

## Diagnosis

The selection manager found both endpoint handles and the edge. The endpoint
handle had higher semantic priority and a 12-pixel hit radius. `_hit_is_better`
used an asymmetric priority comparison, so a point five pixels away could block
an exact zero-distance edge hit. The selected ids therefore contained points,
which are intentionally excluded from path-length measurement.

## Corrected rule

- If hit distances differ by at most 3 pixels, semantic topology priority wins:
  point > edge/curve > face.
- If the distance difference exceeds 3 pixels, the nearest geometry wins.
- Stable actor-id ordering remains the final tie-breaker.

This preserves easy corner selection while making the middle of short segments
selectable and measurable.
