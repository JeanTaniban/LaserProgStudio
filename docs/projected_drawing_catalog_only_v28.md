# Projected drawing catalog-only pass v28

## Goal

Remove the historical Creator UI motif scene from `gizmo_catalog` and make the tool display only content declared through the new projected drawing 2D API.

## Changes

- `GizmoCatalogCreatorTool.on_open()` clears the complete tool-owned state before building the scene.
- The tool no longer imports or calls `tool_api.ui_motifs`, family metadata or catalog presets.
- No `ctx.gizmos`, `ctx.transform_gizmos`, `ctx.preview`, `ctx.selection` or `ctx.overlay` entry is created.
- The right panel contains only projected-scene visibility, rebuild and diagnostic fields.
- The sample now contains 11 points, 7 line primitives and 3 faces, all submitted through `ctx.projected_drawing.for_tool("gizmo_catalog")`.
- The sample is initially centred on the current camera focal point and sized from the current field of view because `vtkActor2D` props do not contribute ResetCamera bounds.

## Interaction

The scene remains render-only. Projected actors are non-pickable and `on_event()` returns `False`, leaving camera navigation to the host.

## Validation

The projected drawing API test now verifies that stale legacy preview state is removed, every historical tool-owned service remains empty, the inspector has no family presets/toggles, visibility is reversible without rebuilding, and normal close cleanup removes the projected primitives.
