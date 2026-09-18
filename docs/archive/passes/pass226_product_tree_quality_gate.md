# Pass 226 — Product tree and quality gate

Goal: prepare the repository for stricter destructive migration passes and a
future Windows executable build without changing runtime behavior.

## Changes

- Moved historical markdown reports out of `diagnostics/` into
  `docs/archive/passes/`.
- Reserved `diagnostics/` for generated runtime/setup logs only.
- Added `scripts/quality_gate.py` as the static pre-migration gate.
- Added `scripts/product_tree_guard.py` to prevent archive/runtime boundary
  regressions.
- Extended `scripts/audit_architecture_health.py` with JSON output and
  legacy/compatibility hotspot reporting.
- Added package metadata and `MANIFEST.in` entries for application assets,
  presets, and settings.
- Added a PyInstaller spec under `packaging/pyinstaller/`.
- Added `docs/architecture_debt_register.md` to list the next hard targets.

## Validation

- `python scripts/quality_gate.py` passes.
- Focused tests pass:
  - `tests/test_refactor_static.py`
  - `tests/test_pass226_product_quality_gate.py`
  - `tests/test_pass150_box_creator_api_migration.py`
  - `tests/test_pass105_tool_core_ui_showcase.py`
  - `tests/test_pass106_tool_core_gui_benchmark.py`
  - `tests/test_pass107_tool_core_feedback_analysis.py`
  - `tests/test_pass173_creator_ui_direction_clarity.py`

## Remaining debt

Largest next targets:

1. `tool_core/overlay/qt_adapter.py`
2. `tool_api/ui_motifs.py`
3. `tooling/texture_projection_creator_tool.py`
4. `application/tool_core_diag_scene.py`

Compatibility hotspots are now visible in the architecture health report.
