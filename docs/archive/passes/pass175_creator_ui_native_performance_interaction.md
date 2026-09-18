# Pass175 - Creator UI native interaction performance

## Problem

The catalog finally displayed the Tool Core Analysis motifs, but interaction still did not match the diagnostic workbench:

- only obvious point-like items were practically draggable;
- handle-style motifs, manipulator handles and other grabbable UI pieces were not all exposed as `ToolActor` entries;
- the catalog refreshed by rebuilding the full motif scene on hover/drag, which caused poor performance compared with Tool Core Analysis;
- clicking on empty viewport space did not clear the Creator-tool selection through the public API.

## Direction fixed

Interaction is now fully part of the Creator API contract:

```text
ToolActor / official motif handles
    ↓
tool_api.interaction.hover_select_grab_actors(...)
    ↓
tool_api.gizmos.refresh_creator_ui_interaction(...)
    ↓
shared Tool Core Analysis persistent painter
```

A tool should not implement local hit-tests, local empty-click clearing or local full-scene rebuilds during drag.

## API additions and corrections

- `SelectionManager.clear_selection(owner_tool=...)`
  - clears selected ids without unregistering actors;
  - can be scoped to the active Creator tool;
  - leaves registered motifs intact.

- `tool_api.interaction.hover_select_grab_actors(...)`
  - keeps the read-only press hit-test so camera misses still work;
  - detects empty click versus empty camera drag;
  - clears tool selection only for an empty click;
  - keeps empty camera drag from clearing selection;
  - only requests a light render when no explicit persistent visual refresh callback is provided.

- `tool_api.gizmos.refresh_creator_ui_interaction(...)`
  - updates hover/select/grab visuals in place;
  - does not clear handles, previews or overlays;
  - is the required path during mouse move / drag.

- `tool_api.gizmos.refresh_creator_ui_motifs(...)`
  - remains available for full rebuild/reset cases;
  - should not be used every frame during interaction.

## Motif extraction update

Official grabbable handles from Tool Core Analysis are now registered as real `ToolActor` objects:

- point-style grab handles;
- snap anchors;
- manipulator handles;
- grabbable actor-kind motifs such as lines and polylines.

The visual handle id and the actor id are the same for actor-backed handles, so the public interaction helper can move them through the same code path as normal actors.

## Catalog update

The Gizmo catalog no longer calls the full motif refresh from its event path. It now uses:

```python
refresh_creator_ui_interaction(ctx, owner_tool="gizmo_catalog")
```

for hover, selection and drag, then renders through the shared persistent painter. Full motif rebuilds are reserved for opening/resetting the catalog or rebuilding after family toggles require it.

## Documentation update

The Creator UI direction docs now state explicitly:

- empty click selection clearing belongs to `tool_api.interaction`;
- persistent hover/drag refresh belongs to `refresh_creator_ui_interaction(...)`;
- `refresh_creator_ui_motifs(...)` is a full rebuild path, not a drag loop path;
- Creator tools must not invent local UI interaction or repaint policies.
