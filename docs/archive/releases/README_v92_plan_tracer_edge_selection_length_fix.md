# LaserProg v92 — Plan Tracer edge selection length fix

Fixes `Selected length` remaining at an em dash when users Shift-click line or
polyline segments in Plan Tracer Modify mode.

## Root cause

The length calculator was correct, but the generic semantic hit comparator was
asymmetric. A high-priority point handle inside its large hit radius could keep
an exact edge hit from replacing it, even when the edge was several pixels
closer. Shift-click therefore selected endpoint points instead of line actors.

## Fix

- Semantic priority now resolves only geometrically ambiguous hits inside a
  3-pixel distance band.
- Outside that band, the actually nearest actor wins.
- Exact/coincident corner clicks still prefer vertices over edges.
- Exact segment clicks now select the edge and update the inspector length.

## Validation

- Real Plan Tracer polyline Shift-click regression test.
- Coincident point/edge priority test retained.
- Nearest-edge-over-nearby-point test added.
- Selection, drag, delete, topology and projected-drawing tests: 28 passed.
- Quality gate: OK.
