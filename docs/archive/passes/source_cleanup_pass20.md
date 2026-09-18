# Source cleanup pass 20 — Hollow Creator API migration

## Goal

Finish the Hollow modifier migration with the same separation rule used for the
previous Creator API migrations: the tool runtime and inspector live in the
Creator API layer, while geometry code remains a pure backend module.

## Runtime path

Hollow now runs through:

```text
HollowCreatorTool
→ ToolContext services
→ ctx.operations.hollow(...)
→ geometry_ops/hollow.py
```

The active UI panel is the generic live declarative Creator panel.

## Removed legacy paths

The pass removes the old Hollow-specific Qt/runtime bridges:

- `panel_hollow_modifier(...)`
- `_panel_hollow_modifier(...)`
- `generate_hollow_modifier_preview(...)`
- `_initialize_hollow_modifier_from_selection(...)`
- `_clear_hollow_modifier_state(...)`
- `_on_hollow_params_changed(...)`
- `_schedule_hollow_preview(...)`
- `_run_hollow_preview_if_current(...)`
- `_update_hollow_report(...)`
- `_hollow_selected_indices(...)`
- the old `hollow_thickness` Qt field path

## Preserved backend

`geometry_ops/hollow.py` remains the pure geometry backend. It is not legacy; it
is the implementation used by the Creator API operation.

## Validation

Added `tests/test_pass162_hollow_creator_api_migration.py` to ensure Hollow uses
the Creator runtime, has a declarative panel, stages preview/apply correctly, is
owner-isolated, and does not reintroduce legacy UI or preview-controller paths.
