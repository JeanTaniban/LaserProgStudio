# Source cleanup pass 16 — Cavity Volume Creator API migration

## Goal

Finish the next tool migration without leaving a compatibility shadow behind. Vent Generator and Plan Tracer remain excluded because they are unfinished special cases.

## Migrated tool

- `TOOL_VOLUME_MEASURE` / Cavity Volume

## New Creator API implementation

- `src/laserprog_studio/tooling/cavity_volume_tool.py`
  - `CavityVolumeCreatorTool`
  - `CavityVolumeTool`
  - `format_cavity_volume_report(...)`

The tool now follows the same clean runtime path as the already migrated Creator tools:

```text
CreatorTool
→ ToolContext services
→ pure geometry backend
```

Specifically, the tool uses:

- `ctx.inspector` for the declarative panel
- `ctx.workflow` for the select/measure steps
- `ctx.scene_selection` for selected scene objects
- `ctx.document` for committed meshes
- `ctx.operations.cavity_volume(...)` for the measurement operation
- `ctx.status` for user feedback

## Removed legacy paths

Removed from runtime sources:

- `controllers/cavity_volume_tool.py`
- `CavityVolumeToolMixin`
- `panel_volume_measure_tool(...)`
- `update_cavity_volume_report(...)`
- `_refresh_cavity_report_from_selection(...)`
- `volume_measure_button`
- `volume_measure_report`
- volume-measure lifecycle hooks in the registry spec

`tool_panel_catalog.py` now routes Cavity Volume to the generic Creator panel:

```text
panel_declarative_creator_tool
```

## Kept backend

The pure geometry backend remains unchanged and is still the canonical measurement implementation:

- `geometry_ops/cavity_volume.py`

## Regression guard

Added:

- `tests/test_pass158_cavity_volume_creator_api_migration.py`

It verifies that Cavity Volume:

- uses the Creator runtime adapter;
- has no legacy open/close hooks;
- uses the declarative panel;
- has no legacy Qt panel/controller/window-method residues;
- keeps the existing report formatting semantics.
