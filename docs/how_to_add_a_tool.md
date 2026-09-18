# How to add a Studio tool

This guide is kept as a short index. The detailed checklist now lives in
`docs/adding_new_tools.md`.

## Stable layers

1. **Tool id**: built-in ids live in `src/laserprog_studio/tooling/ids.py`.
2. **Runtime contract**: register a `ToolSpec` with
   `laserprog_studio.tooling.register_tool_spec(...)`.
3. **Toolbar contract**: register a `ToolbarItemSpec` with
   `laserprog_studio.ui.toolbar_catalog.register_toolbar_item(...)` if the tool
   should be available from **+ Tools** and the configurable top bar.
4. **Panel / parameters**: prefer `ParameterSpec` for simple inputs, and keep Qt
   widgets in `ui/tool_panels.py`.
5. **Operation logic**: keep mesh algorithms in `geometry_ops/`, `modifiers/`,
   `primitives/`, `rendering/` or another non-Qt module.

## Do not touch for normal tool work

- `window.py`: only the Qt shell and bridge methods.
- `layout_panels.py`: only global workspace layout. Toolbar behavior lives in
  `ui/configurable_toolbar.py`.
- Controller files unrelated to the new tool.

For a complete example and test checklist, read `docs/adding_new_tools.md`.
