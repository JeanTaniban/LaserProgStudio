# Box selection

Creator tools can opt into native rectangle selection with `ctx.selection_box`.

```python
from laserprog_studio.tool_api.selection_box import (
    BoxSelectionTarget,
    BoxSelectionMode,
    BoxSelectionInsidePolicy,
)

ctx.selection_box.configure(
    enabled=True,
    targets=[BoxSelectionTarget.TOOL_ACTORS],
    mode=BoxSelectionMode.REPLACE,
    inside_policy=BoxSelectionInsidePolicy.PARTIAL,
    owner_tool=self.id,
)
```

The rectangle is evaluated in screen-space. For tool actors, the service projects actor points using the `world_to_screen` function supplied by the runtime. For scene objects, the service projects object bounds.

## Targets

Use `TOOL_ACTORS` when the tool owns points, lines, arcs, circles or polylines. Use `SCENE_OBJECTS` when the tool needs to select real scene meshes. The result keeps these selections separated.

```python
result = ctx.selection_box.finish(event.screen_pos, world_to_screen=ctx.viewport.world_to_screen)
print(result.tool_actor_ids)
print(result.scene_object_ids)
```

## Modes

- `REPLACE`: replace current selection.
- `ADD`: add hits to the current selection.
- `SUBTRACT`: remove hits from the current selection.
- `TOGGLE`: invert the selection state of hits.

The Tool Core Diagnostic Lab maps `Shift` to additive rectangle selection.

## Fixed actors

Fixed actors are ignored by box selection when `selectable_only=True`, which is the default recommended policy.
