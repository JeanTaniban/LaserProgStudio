# Pass125 - Professional Creator API Hardening

Pass125 turns the Pass124 creator API from a useful facade into a more professional SDK contract.

## Main changes

- Public creator API versioning with `TOOL_API_VERSION`, `TOOL_API_STABILITY` and `require_tool_api(...)`.
- Public exception hierarchy:
  - `ToolApiError`
  - `ToolApiValidationError`
  - `ToolApiUsageError`
  - `ToolApiCompatibilityError`
- `ToolManifest` for external-style plugins and examples.
- `ctx.actors` and `ctx.actor_registry(owner_tool)` as safer wrappers around the low-level selection manager.
- Actor registry duplicate protection: replacing an actor is now explicit with `replace=True`.
- Actor registry automatically attaches `owner_tool` and invalidates `ctx.scene_cache`.
- Dynamic inspector field states:
  - `ctx.inspector.set_enabled(...)`
  - `ctx.inspector.set_visible(...)`
  - `ctx.inspector.set_readonly(...)`
  - `ctx.inspector.set_error(...)`
  - `ctx.inspector.clear_error(...)`
- Qt inspector adapter respects enabled/visible/readonly/error field states.
- Command transactions now roll back already-executed commands if an exception occurs inside the transaction.
- Static import audit helpers to keep external examples away from Qt, PyVista, `tool_core`, `ui`, controllers and window internals.
- Tool creator examples now declare an API requirement and a manifest.

## Recommended external-tool shape

```python
from laserprog_studio.tool_api import (
    CreatorTool,
    ToolContext,
    ToolManifest,
    actors,
    inspector,
    interaction,
    require_tool_api,
)

TOOL_ID = "com.example.my_tool"
require_tool_api("0.5.0", max_major=0)

TOOL_MANIFEST = ToolManifest(
    id=TOOL_ID,
    label="My Tool",
    entrypoint="my_package.my_tool:create_tool",
    api_min="0.5.0",
)

class MyTool(CreatorTool):
    id = TOOL_ID

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.panel(
                "My Tool",
                id=self.id,
                owner_tool=self.id,
                sections=[
                    inspector.section("Geometry", [
                        inspector.float_field("length", "Length", default=80.0, unit="mm"),
                    ]),
                ],
            )
        )
        ctx.actor_registry(self.id).add(
            actors.point("my_tool.handle", (0, 0, 0), interaction="grabbable")
        )

    def on_event(self, event, ctx: ToolContext) -> bool:
        return interaction.select_or_grab(event, ctx, owner_tool=self.id)


def create_tool() -> MyTool:
    return MyTool()
```

## Public import rule

External tools should import from:

```python
from laserprog_studio.tool_api import ...
```

External tools should not import:

- `PySide6`
- `pyvista`
- `vtk`
- `laserprog_studio.ui`
- `laserprog_studio.window`
- `laserprog_studio.controllers`
- `laserprog_studio.tool_core`

If an external tool needs one of those imports, the public API is missing a capability and should be extended instead.

## Safer actor registration

Prefer:

```python
registry = ctx.actor_registry(self.id)
registry.add(actors.point("handle", (0, 0, 0)))
```

Instead of:

```python
ctx.selection.register_actor(...)
```

The registry attaches ownership, invalidates the scene cache and rejects silent overwrites.

## Transaction safety

If a transaction fails, earlier commands in the same transaction are undone automatically.

```python
with ctx.commands.transaction("Create profile"):
    ctx.commands.do("add point", do=..., undo=...)
    ctx.commands.do("add edge", do=..., undo=...)
```

This prevents invisible half-applied tool states.
