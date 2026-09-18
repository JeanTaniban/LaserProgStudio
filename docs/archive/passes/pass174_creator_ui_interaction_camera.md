# Pass174 - Creator UI interaction and camera policy

## Problem

The public Creator UI motifs were visible, but the catalog did not yet behave like Tool Core Analysis:

- actor motifs could not be hovered, selected or grabbed through the standard Creator API;
- hiding every family could leave stale painter actors visible until the tool was cancelled;
- camera-axis orientation and field-of-view scaling existed in the Tool Core Analysis painter, but the public API direction did not clearly make it native for Creator tools.

## Direction fixed

The official path is now:

```text
Tool Core Analysis validates visual + interaction + camera policy
    ↓
tool_api.ui_catalog documents it
    ↓
tool_api.ui_motifs builds and refreshes it
    ↓
tool_api.interaction handles hover/select/grab
    ↓
tool_api.gizmos.refresh_creator_ui_camera handles camera-axis orientation and FOV scale
    ↓
Gizmo catalog displays the result without inventing UI
```

## API additions

- `tool_api.interaction.hover_select_grab_actors(...)`
  - read-only hit-test before press;
  - returns `handled=False` on miss so camera drag still works;
  - owns hover id, selected ids, grabbed ids and incremental drag movement.

- `tool_api.gizmos.refresh_creator_ui_motifs(...)`
  - redraws handles/previews/overlays after interaction;
  - preserves existing `ToolActor` positions, so dragging does not reset the catalog layout.

- `tool_api.gizmos.refresh_creator_ui_camera(...)`
  - re-renders Creator UI after camera movement;
  - uses the shared Tool Core Analysis painter, including axis-locked billboard basis and pixel-to-world scaling from the current field of view.

## Application integration

The Qt/VTK interaction bridge now forwards active Creator-tool pointer events to the tool adapter. It also refreshes active Creator UI after wheel zooms and camera-drag release paths.

## Catalog cleanup

When every family toggle is disabled, the Gizmo catalog clears both API-owned motifs and the Creator viewport painter actors. This avoids stale blue point batches remaining in the viewport.
