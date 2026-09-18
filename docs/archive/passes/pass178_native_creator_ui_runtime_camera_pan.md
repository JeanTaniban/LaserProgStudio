# Pass 178 - Native Creator UI runtime and camera pan performance

## Goal

The Creator UI interaction policy must be native to the API/runtime, not copied
inside individual tools.  Tool authors register official actors/motifs; they do
not decide whether a mouse move should call a full motif rebuild, an interaction
refresh, a drag fast path or a camera refresh.

## Changes

- `CreatorStudioToolAdapter` now runs the mandatory native Creator UI actor
  runtime before tool-local `on_event` code.
- `tool_api.interaction.handle_native_creator_ui_event(...)` owns the optimized
  event policy:
  - hover / press / release / empty-click clearing use
    `refresh_creator_ui_interaction(...)`;
  - grabbed actor mouse-move uses `refresh_creator_ui_drag(...)`;
  - unchanged hover state does not repaint;
  - empty camera drags return `handled=False` and do not rebuild Creator UI.
- `GizmoCatalogCreatorTool.on_event` no longer contains a private hit-test,
  drag or repaint strategy; it remains a viewer.
- `application.creator_pointer_interaction` skips Creator hit-testing during
  left-button camera pan/orbit when no Creator actor is grabbed.  This removes
  the new pan-camera lag and matches the Tool Core Diagnostic end-only camera
  refresh policy.
- Camera orientation and FOV scaling stay API-owned through
  `refresh_creator_ui_camera(...)`, called once after camera drag/wheel bursts.

## Rule

The non-optional native path is:

```text
registered ToolActor / official motif
    ↓
CreatorStudioToolAdapter
    ↓
handle_native_creator_ui_event(...)
    ↓
refresh_creator_ui_interaction / refresh_creator_ui_drag
    ↓
end-of-camera refresh_creator_ui_camera only after camera movement
```

A Creator tool may still handle domain-specific events after the native runtime
returns `False`, but it must not replace the UI actor interaction path.
