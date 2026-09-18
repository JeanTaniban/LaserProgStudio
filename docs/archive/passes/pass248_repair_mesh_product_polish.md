# Pass 248 — Repair Mesh product polish

Repair Mesh has been promoted from a minimal modifier panel to a product-facing Creator API tool.

## Changes

- Added a dedicated `tooling.mesh_repair` subsystem:
  - `settings.py` validates repair settings;
  - `presets.py` owns product presets;
  - `preflight.py` checks scene/selection targets before preview/apply;
  - `feedback.py` publishes the viewport feedback overlay.
- Added repair presets:
  - Custom;
  - Safe scan cleanup;
  - Balanced repair;
  - Aggressive print fix;
  - Surface preserve.
- Added non-destructive preflight messaging to the inspector.
- Added auto-preview and explicit Preview / Apply / Cancel actions.
- Added a Creator overlay with current preset, settings, selection and status.
- Added regression tests in `tests/test_pass248_repair_mesh_product_ui.py`.

## Validation

- `python scripts/quality_gate.py`: OK.
- Tool product audit: 19/19 OK.
- Focused Repair Mesh tests: 3 passed.
- Full pytest collection: 908 tests collected.
