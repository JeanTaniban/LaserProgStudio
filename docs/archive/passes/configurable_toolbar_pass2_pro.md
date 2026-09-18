# Configurable toolbar pass 2

This pass makes the new top toolbar a cleaner extension point for upcoming tools.

## Main concepts

- `ui/toolbar_catalog.py` is the single contract for toolbar items.
- Built-in tools are registered through the same registry as future extension tools.
- Extension code can call `register_toolbar_item(...)` during startup.
- Persisted toolbar ids are sanitized against the current registry, so stale ids from removed extensions are ignored safely.
- The toolbar remains capped by `TOOLBAR_MAX_ITEMS = 20`.

## Adding a future tool

1. Add a runtime tool id / tool panel implementation if needed.
2. Register a `ToolbarItemSpec`:

```python
register_toolbar_item(
    ToolbarItemSpec(
        id="tool:my_tool",
        code="MYT",
        name="My tool",
        description="Short user-facing description.",
        category="tool",       # tool / modifier / boolean
        kind="tool",           # tool / modifier / boolean
        order=500,
        tool_id="my_tool",
        button_attr="btn_tool_my_tool",
        default_visible=False,
    )
)
```

3. The palette and configurable toolbar will pick it up automatically.

## UI behavior

- `+ Tools` opens a lightweight overlay built in `ui/toolbar_palette.py`.
- Search uses all words against code, name, category and description.
- Already-selected tools are shown with a check mark and cannot be re-added.
- The trash button toggles remove mode; clicking toolbar items removes them until the trash button is clicked again. Remove mode forces every configurable item to stay clickable and uses high-contrast removable styling.

## Persistence

The selected toolbar ids and registry version are stored in `UiLayoutState` through the normal UI preferences path.


## Current implementation notes

- Toolbar construction and trash-mode behavior live in `ui/configurable_toolbar.py`.
- `layout_panels.py` only places the toolbar in the top workspace row.
- Runtime tools can now be registered with `tooling.registry.register_tool_spec(...)`, or bundled with a toolbar item through `tooling.extension_api.ToolExtensionSpec` / `register_tool_extension(...)`.
- See `docs/adding_new_tools.md` for the recommended integration checklist.
