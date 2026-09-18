# Pass137 – Native Box Selection API

Pass137 adds rectangle / rubber-band selection as a native creator API service instead of leaving it in historical controllers.

## Public API

New public imports:

```python
from laserprog_studio.tool_api.selection_box import (
    BoxSelectionTarget,
    BoxSelectionMode,
    BoxSelectionInsidePolicy,
)
```

Every `ToolContext` now exposes:

```python
ctx.selection_box
```

A creator tool can configure whether rectangle selection is allowed, what it can select, and how the result is applied:

```python
ctx.selection_box.configure(
    enabled=True,
    targets=[BoxSelectionTarget.TOOL_ACTORS],
    mode=BoxSelectionMode.REPLACE,
    inside_policy=BoxSelectionInsidePolicy.PARTIAL,
    owner_tool="my_tool",
)
```

Supported targets are:

- `TOOL_ACTORS`
- `SCENE_OBJECTS`
- `SCENE_FACES`
- `SCENE_EDGES`
- `SCENE_VERTICES`

Scene sub-element targets are represented in the result contract now; object selection is implemented, while faces/edges/vertices are reserved for the future picking/frustum backend.

Supported modes are:

- `REPLACE`
- `ADD`
- `SUBTRACT`
- `TOGGLE`

Supported inside policies are:

- `PARTIAL`, also called crossing selection;
- `FULL`, only fully-contained actors/objects.

## Result contract

`finish(...)` returns a typed result:

```python
result.tool_actor_ids
result.scene_object_ids
result.scene_object_indices
result.scene_faces
result.scene_edges
result.scene_vertices
```

This keeps tool actors and real scene selections separated.

## Diagnostic Lab integration

The Tool Core Diagnostic panel now exposes rectangle selection controls:

- Box enabled/disabled;
- target selection: tool actors, scene objects, or both;
- mode: replace/add/subtract/toggle;
- inside policy: partial/crossing or fully inside.

In the Creator API Lab, drag on empty viewport space to draw the selection rectangle. The Lab uses the same native `ctx.selection_box` service that creator tools will use.

## Compatibility

The creator API version is now `0.10.0`. This remains a provisional `0.x` API, so existing examples using `max_major=0` continue to load.
