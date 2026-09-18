# Pass 176 - Creator UI catalog restore and drag performance

This pass fixes two regressions in the Creator API Gizmo catalog.

## Hide all / Show all

`Hide all` no longer destroys the API motif scene. It uses semantic API visibility:

- handles and previews stay registered but become invisible;
- motif `ToolActor` objects get `api_ui_visible=False`;
- the selection hit-test ignores those hidden actors;
- `Show all` restores the same persistent motifs without requiring Reset.

`Reset` remains the destructive rebuild action.

## Drag hot path

The previous catalog path was still too expensive compared with Tool Core Analysis. The gap came from doing work during drag that Tool Core Diagnostic avoids:

- sweeping all visibility toggles on every pointer move;
- allowing snap-cache rebuilds during interaction refresh;
- syncing static overlay windows during every drag render;
- keeping some interaction samples as decorative previews rather than real actors.

The corrected path is:

```python
hover_select_grab_actors(...)
refresh_creator_ui_interaction(ctx, owner_tool=tool_id)
render_creator_viewport_ui(..., sync_overlays=False)
```

Full motif rebuilds and snap cache rebuilds remain setup/reset operations, not per-mouse-move operations.
