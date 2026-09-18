# Configurable top toolbar

This update replaces the fixed top toolbar tool section with a configurable, registry-driven toolbar.

## UX

- A wide **+ Tools** button now sits after **Redo** and before **Transform**.
- Clicking it opens a popup palette with:
  - search input at the top;
  - scrollable list of available entries;
  - each entry shows a compact code, full name, category and short description.
- Clicking an entry adds it to the toolbar.
- The toolbar is grouped into three families:
  - **Tools**
  - **Modifiers**
  - **Booleans**
- A small **trash** button toggles remove mode. While it is active, all configurable toolbar items remain clickable, even tools that normally require a selected part, and every clicked item is removed until the trash button is clicked again.
- Maximum configurable toolbar items: **20**.
- The selected toolbar items are persisted in `settings/studio_ui_layout.json`.

## Architecture

The new registry lives in:

```text
src/laserprog_studio/ui/toolbar_catalog.py
```

New future toolbar entries should be added as `ToolbarItemSpec` objects with:

- stable `id`;
- compact `code` shown on the button;
- full `name`;
- one-line `description`;
- `category`: `tool`, `modifier`, or `boolean`;
- either `tool_id` for panel tools/modifiers or `callback_name` for immediate actions.

The top bar is rebuilt by `ConfigurableToolbarController.rebuild()` in `application/toolbar_controller.py`.
`ui/configurable_toolbar.py` is now only a compatibility facade for existing signals and legacy callers.
The controller still keeps old button attributes such as `btn_tool_material`, `btn_mod_repair`, and `btn_bool_subtract` populated dynamically for backwards compatibility.
