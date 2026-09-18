# Source cleanup pass 19 — Simplify Creator API migration

## Goal

Move the Simplify modifier to the Creator API and remove the remaining legacy Qt
panel / preview-controller path for that tool.

## Runtime path after this pass

Simplify now follows the API-only tool path:

```text
SimplifyCreatorTool
  -> ctx.inspector declarative panel
  -> ctx.operations.simplify(...)
  -> ctx.preview_session
  -> ctx.document
  -> ctx.scene_selection
  -> ctx.view
```

The backend geometry implementation remains in:

```text
src/laserprog_studio/geometry_ops/simplify.py
```

That module is intentionally kept as the pure algorithmic layer.

## Removed legacy paths

The following legacy UI/controller symbols were removed from runtime sources:

- `panel_simplify_modifier`
- `_panel_simplify_modifier`
- `generate_simplify_modifier_preview`
- `_initialize_simplify_modifier_from_selection`
- `_clear_simplify_modifier_preview_state`
- `_on_simplify_params_changed`
- `_schedule_simplify_preview`
- `_run_simplify_preview_if_current`
- `_update_simplify_report`
- `_simplify_selected_indices`
- `simplify_slider`
- `simplify_preserve_topology`
- `simplify_strength_label`

## Tests

Added:

```text
tests/test_pass161_simplify_creator_api_migration.py
```

The test verifies the Creator runtime registration, declarative panel routing,
preview/apply behaviour, owner isolation, and absence of the old legacy UI path.
