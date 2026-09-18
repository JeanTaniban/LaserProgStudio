# Pass169 - Creator API Gizmo catalog tool

Added a built-in `gizmo_catalog` CreatorTool that displays the public viewport/UI vocabulary offered by the Creator API.

## Changes

- Added `TOOL_GIZMO_CATALOG = "gizmo_catalog"`.
- Registered the tool, panel and toolbar-palette entry (`GZM`).
- Added `GizmoUiFamily` / `GizmoCatalogItem` metadata in `tool_core.gizmos.catalog`.
- Re-exported catalog helpers from `laserprog_studio.tool_api.gizmos`.
- Implemented Tool-panel checkboxes for the four UI families:
  - point styles;
  - manipulators;
  - preview primitives;
  - overlay windows.
- Documented the catalog in `docs/tool_creator/16_gizmo_catalog_tool.md` and linked it from the visual API docs.

## Contract

The catalog tool is intentionally implemented through public Creator API services only: `ctx.gizmos`, `ctx.preview`, `ctx.overlay`, `ctx.inspector`, `ctx.workflow` and `ctx.status`.
