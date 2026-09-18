# Plan Tracer 2D — Pass 223 curve intent hardening

## Goal

Continue the Plan Tracer cleanup after the metric split by removing the last
implicit arc/half-circle policy from drawing and metric rebuild code.

The weak point was that arcs only stored start/end/control points while metric
editing also needed to know the user's intent:

- which side of the chord the curve belongs to;
- whether an arc is minor or major;
- whether an angle field means line orientation or arc sweep.

## Changes

- Added `tooling/plan_trace_2d/curve_intent.py`.
  - Defines `ArcIntent` and `HalfCircleIntent`.
  - Owns side detection, major/minor sweep detection, and control-point rebuilds.
  - Provides metadata helpers for generated sketch arcs.
- Extended `_PlacementMetricDraft` with optional curve intent objects.
- Updated arc and half-circle placement to attach explicit curve-intent metadata.
- Updated metric rebuilds to preserve side and major/minor intent instead of recomputing from scattered heuristics.
- Updated arc metric field parsing so the arc angle field is treated as a sweep value in `0..360`, not as a normalized signed orientation angle.
- Made several Plan Tracer service imports safer during built-in tool registry startup.
  - `overlay.py` still uses the public `tool_api.visual` facade, but imports it lazily.
  - `dimensions.py`, `history.py`, `selection.py`, and `snap.py` no longer force `tool_api.core` during service construction.

## Result

The Plan Tracer now has an explicit curve intent boundary:

- `drawing.py` places curves and records intent;
- `metrics.py` owns the edit session lifecycle;
- `metric_field_policy.py` interprets metric fields;
- `metric_rebuilders.py` rebuilds draft geometry;
- `curve_intent.py` owns side/major/control-point policy.

This does not yet add UI buttons for flip side or major/minor selection, but it
prepares the model cleanly so those controls can be added without another large
rewrite.

## Validation

- Added `tests/test_pass223_plan_tracer_curve_intent.py`.
- Full test suite: `835 passed, 3 skipped, 81 warnings`.
- `python -m compileall -q src tests` passes.
