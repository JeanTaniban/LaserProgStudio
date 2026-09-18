# Pass 247 - Gizmo Catalog product presets

## Goal

Make Gizmo Catalog easier to use as a product/reference tool instead of a raw checklist of Creator UI families.

## Changes

- Added `tooling/gizmo_catalog/` helper package.
- Added named view presets:
  - All motifs
  - Tool author essentials
  - Interaction tuning
  - Viewport feedback
  - Clean viewport
  - Custom
- Added compact reports for family counts, active/hidden families and visible families.
- Selecting a preset updates the family toggles without rebuilding the motif scene.
- Manually editing family toggles switches the view selector to Custom.
- Show all / Hide all now map to product presets.

## Validation

- `tests/test_pass169_gizmo_catalog_tool.py`
- `tests/test_pass247_gizmo_catalog_product_presets.py`
- `scripts/quality_gate.py`
- Full test suite was validated by chunks because the monolithic command can exceed the execution window in this environment.
