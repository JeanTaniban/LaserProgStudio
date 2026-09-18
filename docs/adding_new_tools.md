# Adding new tools cleanly

This project now treats a tool as three separate contracts. Keeping these layers
separate makes the app easier to maintain and lets a future contributor add a
feature without editing the main window directly.

## 1. Tool id

Add a stable id in `src/laserprog_studio/tooling/ids.py` only when the tool is a
built-in feature. External/startup extensions may use their own string id.

```python
TOOL_MY_TOOL = "my_tool"
```

## 2. Runtime tool registration

For the cleanest integration, register a `ToolExtensionSpec` so the runtime tool
and optional toolbar item are added together. For runtime-only tools, call
`register_tool_spec(...)` directly.

The runtime object is optional: if omitted, LaserProg wraps the spec with
`LegacyToolAdapter` and calls the declared hooks on the main window context.

```python
from laserprog_studio.tooling import ToolSpec, register_tool_spec

register_tool_spec(
    ToolSpec(
        id="my_tool",
        label="My tool",
        category="tool",          # "tool" or "modifier"
        panel_index=14,            # index in the tool panel stack
        button_attr="btn_tool_my_tool",
        selection_policy="none",   # "none", "single" or "multi"
        open_hook="_initialize_my_tool",
        close_hook="_clear_my_tool_state",
        display_order=500,
    )
)
```

Use a custom object implementing `StudioTool` when the tool can be isolated from
window hooks. That is the preferred long-term shape for new complex tools.

## 3. Toolbar / palette registration

Register a `ToolbarItemSpec` if the tool should appear in the configurable top
bar and in the **+ Tools** palette.

```python
from laserprog_studio.ui.toolbar_catalog import ToolbarItemSpec, register_toolbar_item

register_toolbar_item(
    ToolbarItemSpec(
        id="tool:my_tool",
        code="MYT",
        name="My tool",
        description="Short user-facing description.",
        category="tool",          # "tool", "modifier" or "boolean"
        kind="tool",              # "tool", "modifier" or "boolean"
        order=500,
        tool_id="my_tool",
        button_attr="btn_tool_my_tool",
        default_visible=False,
    )
)
```

The toolbar UI is owned by `src/laserprog_studio/ui/configurable_toolbar.py`.
Do not add new toolbar button logic to `layout_panels.py`.

For a one-call integration, bundle both specs:

```python
from laserprog_studio.tooling.extension_api import ToolExtensionSpec, register_tool_extension

register_tool_extension(
    ToolExtensionSpec(tool=my_tool_spec, toolbar_item=my_toolbar_item_spec)
)
```

## 4. Parameters and panel

Prefer declarative `ParameterSpec` values for simple numeric/text/choice inputs.
This keeps validation testable without Qt and makes future parameter panels more
reusable.

For existing hand-written tools, add the Qt controls to `ui/tool_panels.py` and keep
operation logic in a controller or `geometry_ops/` module. The panel should read
and write parameters; it should not own mesh algorithms.

## 5. Tests to add

For each new tool, add at least:

- a registry test proving the `ToolSpec` and optional `ToolbarItemSpec` are valid;
- a pure operation test for geometry/export logic where possible;
- a lifecycle test if the tool opens previews, requires selection, or owns cleanup.

## Practical rules

- Keep stable ids stable; they are persisted in user preferences.
- Avoid editing `window.py`; it is only the Qt shell and bridge class.
- Avoid adding algorithms to UI files.
- If a tool is unavailable without a selected part, implement that with
  `selection_policy`; do not hard-code it in the button callback.
- If the tool has immediate behavior and no panel, register it as a toolbar
  `kind="boolean"` or create a small action controller.
