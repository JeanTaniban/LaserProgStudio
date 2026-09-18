# Pass110 - Tool Core persistent gizmo styles and camera-aware sizing

This pass promotes the Pass109 no-flicker diagnostic behavior into the shared Tool Core layer.

## Added

- `tool_core.gizmos.styles`
  - 5 official point styles: `solid`, `ring`, `target`, `diamond`, `square`.
  - Semantic states: fixed, grabbable, hover, grabbed, selected, disabled.
  - Central color/radius resolution.

- `GizmoManager.update_visual_state(...)`
- `GizmoManager.update_interaction_state(...)`

Production tools should use these APIs for hover/grab changes instead of clearing and rebuilding viewport actors.

## Camera-aware sizing

- `tool_core.gizmos.camera_scale`
  - converts a desired pixel radius into a world-space radius near a handle.
  - supports perspective and parallel cameras.
  - used by the diagnostic painter for guide rings/crosses/diamonds/squares.

This prepares true 3D handles to stay readable as the camera zoom/FOV changes, like the Transform tools.

## Diagnostic demo

The Tool Core Diagnostic panel now shows a focused handle demo with five size/style rows:

- XS / solid
- S / ring
- M / target
- L / diamond
- XL / square

Each row still includes fixed points, grabbable points, a standalone line, a line between fixed points, a line between grabbable points and a circle with a grabbable radius point.

## Rule for future tools

A tool must not rebuild actors to express hover/grab/selection changes. It should update semantic state through Tool Core and let the persistent renderer update actors in place.
