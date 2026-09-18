# Pass103 — Shared viewport tool core foundation

This pass adds a non-invasive shared foundation for future tool migration. No
existing tool is forced to use it yet. The goal is to provide stable services so
Plan Tracer, Transform, Extrude and future tools can progressively move to one
common interaction layer.

## New package

`src/laserprog_studio/tool_core/`

Main layers:

- `ToolContext`: one clean access point for viewport, snap, gizmos, overlay,
  preview, selection, commands, sketch and diagnostics.
- `ToolBase` / `ToolModeBase`: standard tool and mode lifecycle.
- `SelectionManager`: shared selection registry.
- `GizmoManager`: optimized handle layer with interactive updates and backend
  reuse contract.
- `SnapManager`: Smart snap / Grid snap switches with provider priority.
- `PreviewManager`: temporary line/polyline/face/mesh previews.
- `OverlayManager`: declarative button/panel state with exclusive groups.
- `SketchDocument`: pure 2D sketch model.
- `FaceSolver`: first robust loop detection for independent line contours and
  circle faces.
- `CommandStack`: undo/redo ready command execution.
- `RenderScheduler`: throttled light renders vs full renders.
- `ToolProfiler`: counters and event timings to stop guessing about lag.

## Migration rule

Existing tools should migrate progressively. The first target should be Plan
Tracer because it needs all layers: snap, gizmos, sketch model, faces, preview,
selection and overlay.

Tools should eventually request services from `ToolContext` instead of directly
creating actors, widgets, snap caches or preview objects.
