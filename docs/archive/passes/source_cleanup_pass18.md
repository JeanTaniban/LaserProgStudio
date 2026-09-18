# Source cleanup pass 18 — Repair Mesh Creator API migration

## Goal

Continue the tool migration sequence with the same rule used for the previous
Creator API migrations: move the active tool to the Creator runtime and remove
its historical Qt/controller path immediately.

Vent Generator and Plan Tracer remain intentionally excluded because they are
unfinished special cases.

## Migrated tool

- `TOOL_MOD_REPAIR` / Repair Mesh

## New Creator API implementation

- `src/laserprog_studio/tooling/repair_tool.py`
  - `RepairMeshCreatorTool`
  - `RepairMeshTool`
  - `format_repair_line(...)`

The tool now uses:

- `ctx.inspector` for the declarative panel;
- `ctx.workflow` for select/preview state;
- `ctx.scene_selection` for selected scene objects;
- `ctx.document` for committed and preview meshes;
- `ctx.operations.repair(...)` for the repair operation;
- `ctx.preview_session` for Apply/Cancel integration;
- `ctx.view` and `ctx.status` for view focus and feedback.

## Removed legacy paths

Removed from runtime sources:

- `controllers/mesh_repair_tool.py`
- `MeshRepairToolMixin`
- `panel_repair_modifier(...)`
- `preview_repair_selected_meshes(...)`
- `_initialize_repair_modifier_from_selection(...)`
- `_clear_repair_modifier_preview_state(...)`
- legacy Qt fields such as `repair_tolerance`, `repair_fill_holes` and
  `repair_remove_tiny`

`tool_panel_catalog.py` now routes Repair Mesh to the generic Creator panel:

```text
panel_declarative_creator_tool
```

## Backend kept intentionally

The pure mesh repair backend remains unchanged:

- `geometry_ops/mesh_repair.py`

This is domain logic, not UI/controller legacy. The Creator tool calls it when
building the preview mesh list.

## Regression guard

Added:

- `tests/test_pass160_repair_creator_api_migration.py`

It verifies that Repair Mesh:

- uses the Creator runtime adapter;
- has no legacy open/close hooks;
- uses the declarative panel;
- stages repair through preview meshes and commits through Apply;
- has no legacy Qt panel/controller/window-method residues;
- does not access `ctx.owner` from the Creator tool implementation.
