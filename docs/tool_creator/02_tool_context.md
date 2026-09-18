# 02 - ToolContext

`ToolContext` is the stable toolbox passed to runtime tools.

```python
ctx.viewport      # screen/world conversion and render requests
ctx.selection     # actors, selection, grab state
ctx.gizmos        # persistent viewport handles
ctx.snap          # smart snap and grid snap
ctx.scene_cache   # cached points/segments/bounds for snap and guides
ctx.overlay       # floating viewport UI
ctx.preview       # temporary lines, faces, text, meshes
ctx.inspector     # right Tool panel, declarative and Qt-free
ctx.commands      # undo/redo stack
ctx.sketch        # 2D sketch entities and face solving
ctx.profiler      # counters and timings for diagnostics
ctx.style         # shared visual language
ctx.scene         # optional app scene reference
ctx.document      # creator-facing document facade for meshes/preview/apply
ctx.scene_selection # selection of real scene objects
ctx.pick          # object/face/edge/vertex/ray picking facade
ctx.preview_session # preview/apply/cancel sessions
ctx.operations    # previewable operation runner
ctx.jobs          # progress-aware job wrapper
ctx.status        # user-facing info/warning/error/progress messages
```

The creator-facing contract is: if a tool needs something outside this context, add a capability to the API instead of coupling to the main window.
