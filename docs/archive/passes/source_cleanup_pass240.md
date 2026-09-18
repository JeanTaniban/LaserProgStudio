# Pass 240 — Vent Generator live route state machine

Vent Generator received a product-focused interaction pass.

Changes:

- Added a pure Creator/API route state machine:
  - `VentRouteMachine`
  - `VentRouteResult`
  - route summary helpers
  - selected waypoint text helper
- Vent Generator now handles headless `ToolEvent` world-position edits for:
  - ADD waypoint
  - MOD select/move waypoint
  - SUPP delete waypoint
  - RST reset route
- The declarative inspector was improved:
  - route summary field
  - selected waypoint field
  - selected bend fields hidden until useful
  - direct `Apply mesh` action beside preview/reset
- Curve radius/force now write to the selected route segment through the same settings path.
- Added focused tests for headless route interactions and the state machine.

Validation:

- `python scripts/quality_gate.py`: OK
- `python -m pytest -q`: 881 passed, 3 skipped
