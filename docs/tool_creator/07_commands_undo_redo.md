# 07 - Commands, undo and redo

Use `ctx.commands` for actions that must be reversible.

```python
from laserprog_studio.tool_api import FunctionCommand

ctx.commands.execute(
    FunctionCommand(
        label="Move point",
        do_func=lambda: move_point(new_position),
        undo_func=lambda: move_point(old_position),
    )
)
```

Keep preview-only changes outside the command stack. Commit only real document/scene mutations.

Recommended rule:

- mouse move: preview/light render;
- drag end or Apply button: command/undoable mutation/full render.

## Creator-friendly helpers

Use `ctx.commands.do(...)` for simple actions:

```python
ctx.commands.do(
    "Move point",
    do=lambda: move_point(new_pos),
    undo=lambda: move_point(old_pos),
)
```

Use a transaction when one user action changes several things:

```python
with ctx.commands.transaction("Create profile"):
    ctx.commands.do("Add p1", do=..., undo=...)
    ctx.commands.do("Add p2", do=..., undo=...)
```

The transaction appears as a single undo entry.
