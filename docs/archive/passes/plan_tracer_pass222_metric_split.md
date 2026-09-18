# Plan Tracer 2D — Pass 222 metric split

This pass continues the service-structure cleanup started in P218-P221.

## Goal

`metrics.py` had become the next local centre of gravity after the monolith split. It still owned three concerns at once:

- metric edit sessions and overlay lifecycle;
- field-level policy such as radius/diameter and arc radius/angle synchronisation;
- geometry rebuilds for line, rectangle, circle, half-circle, and arc drafts.

The pass separates those concerns without changing user behaviour.

## Changes

- Added `metric_rebuilders.py`.
  - Owns temporary sketch reconstruction for metric drafts.
  - Keeps shape-specific rebuild policy out of `metrics.py`.
  - Exposes `distance_xy` and `line_metrics_from_xy` as small local helpers.
- Added `metric_field_policy.py`.
  - Owns parsing + linked field updates.
  - Keeps radius/diameter and arc radius/angle synchronisation out of the overlay service.
- Added `metric_rebuilders` to `PlanTrace2DServices`.
- Reduced `metrics.py` to session creation, overlay lifecycle, validation, cancellation, rollback orchestration, and delegation.

## Result

The metric service remains the public tool-facing entry point for editable metric overlays, but the geometry rebuild and field policy are now independently readable and testable.

The next cleanup targets remain:

- arc/half-circle intent model;
- a more explicit state machine table;
- real Qt interaction tests for focus, Enter, Escape, and invalid text-field commits.
