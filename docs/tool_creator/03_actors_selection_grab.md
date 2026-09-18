# 03 - Actors, selection and grab

Create actors through `tool_api.actors` and register them through `ctx.actor_registry(tool_id)`. Actors are the semantic objects that the native Creator runtime can hover, select and grab.

```python
from laserprog_studio.tool_api.scene import actors

registry = ctx.actor_registry(self.id)
registry.add(actors.point("p1", (0, 0, 0), interaction="grabbable", point_style="target"))
registry.add(actors.point("p2", (50, 0, 0), interaction="grabbable", point_style="target"))
registry.add(actors.line("edge", (0, 0, 0), (50, 0, 0), interaction="selectable"))
```

Available factories:

- `actors.point(...)`
- `actors.line(...)`
- `actors.circle(...)`
- `actors.arc(...)`
- `actors.polyline(...)`
- `actors.make_actor(...)` for advanced custom cases

## Interaction modes

A fixed actor never reacts. A selectable actor can be picked but not moved. A grabbable actor moves only after it is selected.

| Mode | Can select | Can move | Typical use |
|---|---:|---:|---|
| `fixed` | no | no | Guides, decorations, locked references |
| `selectable` | yes | no | Lines, constraints, reference geometry |
| `grabbable` | yes | yes, after selection | Points, handles, editable vertices |

`grabbable` intentionally means “selectable first, movable second”. This prevents accidental moves and keeps multi-selection behavior predictable.

## Native runtime

For a `CreatorTool` registered with `register_tool(...)`, actor interaction is native. The application calls the API runtime before `on_event`, so a normal tool does not implement:

- hover hit-testing;
- selected / hover / grabbed visual states;
- drag deltas;
- fast drag rendering;
- empty-click selection clearing;
- camera pan/orbit passthrough.

The tool only registers actors and updates its own domain data when needed.

## Reading selection

Tools may read selection state for business logic:

```python
selected = ctx.selection.selected_actors(owner_tool=self.id)
selected_ids = ctx.selection.ids(owner_tool=self.id)
```

Tools may explicitly set or clear selection for command-like actions:

```python
ctx.selection.clear_selection(owner_tool=self.id)
ctx.selection.select("p1", replace=True)
```

Do this for semantic actions, not for reimplementing the pointer state machine.

## Low-level helpers

`ctx.selection.select_at(...)`, `ctx.selection.move_selected(...)`, `interaction.select_or_grab(...)` and `interaction.hover_select_grab_actors(...)` remain available for tests, diagnostics and owner-method adapters. They are not the recommended path for external Creator tools because they make the tool author choose behaviour that the native runtime already owns.
