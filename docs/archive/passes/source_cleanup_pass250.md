# Pass 250 — Hollow Mesh product polish

Hollow Mesh was promoted from a basic Creator modifier to a product-facing tool.

Changes:

- Added `tooling/mesh_hollow/settings.py` for validated wall settings.
- Added `tooling/mesh_hollow/presets.py` for quick wall thickness presets.
- Added `tooling/mesh_hollow/preflight.py` for selection and thickness checks.
- Added `tooling/mesh_hollow/feedback.py` for viewport status overlay.
- Updated `tooling/hollow_tool.py` with auto-preview, preset handling, Apply/Cancel actions and overlay commands.
- Added `tests/test_pass250_hollow_mesh_product_ui.py`.

Validation:

- Focused Hollow tests pass.
- The tool remains a declarative Creator API modifier using `panel_declarative_creator_tool`.
