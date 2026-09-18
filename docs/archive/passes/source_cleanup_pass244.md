# Pass 244 — Plan Tracer Creator UI review

## Goal
Move Plan Tracer further into the current Creator API product model after the Vent Generator work.

## Changes
- Rebuilt the Plan Tracer right-inspector as a declarative Creator panel.
- Added user-facing controls for mode, smart snap, grid snap, grid size, live status, sketch counts, metric status and actions.
- Registered Plan Tracer modes in `ctx.modes` so audits and hosts can see the real state machine.
- Synchronized inspector mode changes with the viewport toolbar and internal state.
- Removed the old dedicated Qt Plan Tracer panel module from the active product tree.
- Added tests for the new Plan Tracer Creator UI contract.

## Validation
- `python scripts/quality_gate.py`
- `pytest -q`
