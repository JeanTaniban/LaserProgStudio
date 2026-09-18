# Pass 251 — Split Mesh product polish

Split Mesh was reviewed as a user-facing Creator tool after Repair, Simplify and Hollow.

Changes:

- Added `tooling/mesh_split/` with focused settings, presets, preflight and feedback modules.
- Converted the Split inspector to the shared product pattern:
  - quick plane presets;
  - preflight status;
  - auto-preview;
  - Recenter / Preview / Apply / Cancel actions;
  - viewport feedback toolbar.
- Kept the operation names `split` and `split_plane` for the active Creator API runtime.
- Added product tests covering presets, empty-selection preflight and preview/apply flow.

Validation:

- `python scripts/quality_gate.py`
- `python -m pytest -q tests/test_pass251_split_mesh_product_ui.py`
- `python -m pytest -q tests/test_pass248_repair_mesh_product_ui.py tests/test_pass249_simplify_mesh_product_ui.py tests/test_pass250_hollow_mesh_product_ui.py tests/test_pass251_split_mesh_product_ui.py tests/test_pass165_remaining_creator_api_migration.py`
