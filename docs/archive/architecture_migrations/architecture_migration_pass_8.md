# Architecture Migration Pass 8 - Declarative tool panels

## Goal

Reduce the right-inspector tool-panel monolith and make future tool UI panels
more discoverable for external contributors.

Before this pass, `ui/tool_panels.py` mixed three responsibilities:

- building the right inspector shell;
- defining compact Qt helper rows/spin boxes;
- building every tool and modifier panel inline.

That made the file difficult to review and made the panel order an implicit list
of `addWidget(...)` calls.

## What changed

### `ToolPanelSpec` catalog

A new declarative catalog lives in:

```text
src/laserprog_studio/ui/tool_panel_catalog.py
```

It defines `ToolPanelSpec` entries for every stacked inspector panel. The
catalog records the tool key, label, builder method, panel index and family.
Those panel indices intentionally match the tool registry so the existing
`ToolLifecycleController` can continue to open panels by index.

### `ToolPanelFactory`

The actual panel builders moved to:

```text
src/laserprog_studio/ui/tool_panel_factory.py
```

`ToolPanelFactory` now owns:

- stacked-panel construction through `build_stack()`;
- key-based panel creation through `build_panel(key)`;
- fabrication panel builders;
- material and texture panel builders;
- modifier panel builders.

The existing window-like owner still receives the widget attributes, for example
`owner.joint_clearance` or `owner.texture_scale`, so legacy controllers remain
compatible during the migration.

### `UIToolPanelsMixin` shell

`ui/tool_panels.py` is now a much smaller shell. It still builds the right
inspector container, exposes compact Qt helper methods, and keeps legacy
`_panel_*` wrappers, but it no longer contains the actual tool-panel bodies.

This file dropped from roughly 877 lines to roughly 338 lines.

## Compatibility notes

The pass deliberately keeps old method names such as `_panel_material_tool()` and
`_panel_split_modifier()` as wrappers. Older tests, menu wiring and any external
experiments that call those methods still work.

The panel stack is now built from `iter_tool_panel_specs()`. Adding a future
panel should start by adding a `ToolPanelSpec`, then implementing the factory
builder, rather than manually appending another `addWidget(...)` call in the
inspector shell.

## Remaining work

`ToolPanelFactory` is still a compatibility factory: it writes widgets directly
onto the owner because many controllers still read those attributes. Later
passes should move the largest panels to declarative `ParameterPanelFactory`
forms or dedicated `StudioTool` UI bundles.
