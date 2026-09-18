# Pass 246 — Material Painter product polish

## Goal

Review Material Painter as a user-facing Creator tool, not only as a registered runtime.

## Changes

- Removed the remaining hand-built Qt material panel from `ToolPanelFactory` and `UIToolPanelsLayer`.
- Rebuilt Material Painter around API-first helpers:
  - `tooling/material_painter/settings.py`
  - `tooling/material_painter/presets.py`
  - `tooling/material_painter/preflight.py`
  - `tooling/material_painter/feedback.py`
- Added user presets for common visual materials.
- Added explicit target scope: selected parts or all parts.
- Added preflight checks before preview/apply.
- Added a Creator overlay status window for material, target, selection and action feedback.
- Material preview now also synchronizes `mesh.color` with `mesh.material.base_color` for downstream display/export consistency.
- Material tool selection policy is now multi-selection with open-without-selection allowed.

## Validation

- `python scripts/quality_gate.py` OK.
- Product audit: 19/19 tools OK.
- Added `tests/test_pass246_material_painter_product_ui.py`.
- Tests were run by chunks because a single process exceeds the execution window in this environment.
