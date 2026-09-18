# 04 - Snap and SceneCache

`ctx.scene_cache` is the shared cache used by smart snap and tool guides.

```python
ctx.scene_cache.rebuild(ctx, scope="snap")
points = ctx.scene_cache.points()
segments = ctx.scene_cache.segments()
targets = ctx.scene_cache.snap_targets()
summary = ctx.scene_cache.summary()
```

It currently collects:

- sketch snap points and segments when the sketch document exposes them;
- registered tool actors from `ctx.selection`;
- optional scene hooks such as `snap_points()`, `snap_segments()` and `bounds_for_snap()`;
- extra snap targets added by tools;
- UI snap points for temporary overlay/gizmo/guide snapping.

The cache is versioned:

```python
ctx.scene_cache.version
ctx.scene_cache.valid
ctx.scene_cache.invalidate()
```

Use `ctx.snap.smart(...)` for the default snap behavior:

```python
result = ctx.snap.smart(event.world_pos, event.screen_pos, ctx)
```

By default, `ctx.snap.smart(...)` rebuilds the scene cache if it is invalid. You can force or prevent that behavior:

```python
ctx.snap.smart(world, screen, ctx, rebuild_cache=True)   # force refresh
ctx.snap.smart(world, screen, ctx, rebuild_cache=False)  # use current cache exactly
```

Exclude the object currently being edited or moved:

```python
result = ctx.snap.smart(
    event.world_pos,
    event.screen_pos,
    ctx,
    exclude_ids=ctx.selection.ids(),
)
```

Add temporary world snap targets without writing a provider:

```python
from laserprog_studio.tool_api import snap

result = ctx.snap.smart(
    event.world_pos,
    event.screen_pos,
    ctx,
    extra_targets=[
        snap.point("temporary_center", (20, 0, 0), priority=10),
        snap.segment("temporary_axis", (0, 0, 0), (50, 0, 0)),
    ],
)
```

Add temporary UI/GUI snap targets:

```python
result = ctx.snap.smart(
    event.world_pos,
    event.screen_pos,
    ctx,
    extra_targets=[
        snap.ui_point("overlay.crosshair", screen_pos=(420, 180), world_pos=(20, 0, 0)),
    ],
)
```

A UI snap point may omit `world_pos`. In that case, the returned snap position remains the queried world position, but `source` and `source_id` identify the UI target. This is useful for guide overlays that influence interaction without creating real geometry.

For advanced tools, register a provider with `ctx.snap.add_provider(...)`.

## Pass124 clarification: source semantics

Smart snap now separates UI targets from geometry targets. This is important for
external tools because a world-space actor should never look like a GUI element.

Common sources:

| Source | Meaning |
|---|---|
| `TOOL_ACTOR_POINT` / `TOOL_ACTOR_EDGE` | Actors registered through `ctx.selection` / `actors.*` |
| `TOOL_TEMP_POINT` / `TOOL_TEMP_EDGE` | Persistent construction targets owned by a tool |
| `UI_POINT` / `UI_EDGE` | Screen-space overlay, GUI or gizmo targets |
| `SCENE_POINT` / `SCENE_EDGE` | Geometry exposed by the document/scene |
| `SKETCH_POINT` / `SKETCH_EDGE` | Sketch document snap targets |
| `CUSTOM_POINT` / `CUSTOM_EDGE` | One-shot custom targets passed to `ctx.snap.smart(...)` |

For construction geometry that should survive a cache rebuild:

```python
ctx.scene_cache.add_point("my_tool.midpoint", (10, 0, 0), owner_tool=self.id)
ctx.scene_cache.add_segment("my_tool.axis", (0, 0, 0), (20, 0, 0), owner_tool=self.id)
```

These targets stay available after `ctx.scene_cache.rebuild(...)`. Clear them
explicitly when the tool resets or closes:

```python
ctx.scene_cache.clear_tool_targets(self.id)
```

For one-shot snap targets during a single query, keep using `extra_targets`:

```python
ctx.snap.smart(
    world,
    screen,
    ctx,
    extra_targets=[snap.tool_point("hover.midpoint", (10, 0, 0), owner_tool=self.id)],
)
```

`exclude_ids` is now a query-time filter. It does **not** rebuild the cache. This
means it is safe to use during drag:

```python
ctx.snap.smart(world, screen, ctx, exclude_ids=ctx.selection.ids())
```
