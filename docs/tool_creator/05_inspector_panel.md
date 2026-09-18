# 05 - Right Tool inspector

Use `ctx.inspector.set_panel(...)` to place controls in the right Tool area without importing Qt.

Recommended creator-facing style:

```python
from laserprog_studio.tool_api import inspector

ctx.inspector.set_panel(
    inspector.panel(
        "Vent Generator",
        id="vent_tool",
        owner_tool="vent_tool",
        sections=[
            inspector.section("Dimensions", [
                inspector.float_field("width", "Width", default=100.0, min_value=1.0, unit="mm"),
                inspector.float_field("height", "Height", default=40.0, min_value=1.0, unit="mm"),
                inspector.int_field("count", "Blade count", default=8, min_value=1),
            ]),
            inspector.section("Actions", [
                inspector.button("preview", "Preview"),
                inspector.button("apply", "Apply"),
            ]),
        ],
    )
)
```

Capitalised names remain available:

```python
inspector.Panel(...)
inspector.Section(...)
inspector.FloatField(...)
```

Read values:

```python
values = ctx.inspector.values()
width = ctx.inspector.value("width")
```

Update one or several values:

```python
ctx.inspector.update_value("width", 120.0)
ctx.inspector.update_values({"width": 120.0, "count": 12})
```

Trigger a declarative action in tests or adapters:

```python
event = ctx.inspector.trigger("apply")
```

The manager validates values and rejects duplicate field ids when the panel is created. This catches common external-tool mistakes early, before a Qt widget exists.

Typing in an inspector field must never rebuild the whole panel. The API separates:

- `layout_revision`: panel structure changed, rebuild is allowed;
- `value_revision`: user/display values changed, sync existing widgets in place;
- `state_revision`: enabled/visible/error state changed, sync existing widgets in place.

Tool code can safely update read-only reports and validation errors from an `on_change` callback; the native host preserves the focused editor and avoids normalising the active spinbox while the user is still typing.

## Automatic parameter persistence

Inspector values declared by a tool with `owner_tool=...` are persisted automatically.
When the user reopens the tool, visible user-facing parameters are restored before the panel is shown.

Rules for tool authors:

- put a stable `owner_tool` on every production panel;
- use read-only fields for reports/status, because they are never persisted;
- hidden bookkeeping fields such as selected object indices or cached face anchors are not persisted while hidden;
- keep non-user bookkeeping values hidden or read-only so they are not saved as user parameters.

This contract prevents tools from losing dimensions, tolerances and other user-entered values after close/reopen, without each tool writing its own settings file.

## Native AutoPreview

For light tools, the creator can ask the API to regenerate the preview automatically after inspector value changes. The tool declares the policy once on the panel; the runtime owns the debounce timer and triggers the existing preview action. Do not write a custom `QTimer` or call the preview callback manually from every field.

```python
from laserprog_studio.tool_api import inspector

ctx.inspector.set_panel(
    inspector.panel(
        "Light generator",
        id="example.light_generator",
        owner_tool=tool_id,
        auto_preview=inspector.auto_preview(
            action_id="preview",
            debounce_ms=250,
        ),
        sections=[
            inspector.section("Parameters", [
                inspector.float_field("width", "Width", default=80.0, unit="mm"),
                inspector.float_field("height", "Height", default=30.0, unit="mm"),
            ]),
            inspector.section("Preview", [
                inspector.button_row(
                    "actions",
                    "Actions",
                    buttons=(("preview", "Preview"),),
                    callbacks={"preview": lambda event: preview(ctx, event)},
                ),
            ]),
        ],
    )
)
```

The sequence is native:

```text
user edits an inspector value
    ↓
InspectorManager validates and stores the value
    ↓
the Qt/runtime bridge restarts the panel AutoPreview timer
    ↓ debounce_ms later
ctx.inspector.trigger(action_id)
```

Use `include_fields=(...)` or `exclude_fields=(...)` when only some values should retrigger preview. AutoPreview is meant for cheap previews. Heavy mesh operations should keep an explicit Preview button, or run through `ctx.jobs`.

Checklist rule: if a panel has AutoPreview, the tool still exposes a normal preview action; AutoPreview only triggers that action after a debounce. The tool does not own timing, stale-value filtering, or Qt signal wiring.

## Responsive layout contract

The right Tool zone can become narrow. External tools must assume that long labels, long choice captions and many action buttons may be rendered in a compact width.

Use these rules:

- prefer short field labels and move longer explanations into `tooltip` or `HelpText`;
- for dense action areas, use `button_row(..., columns=2)` or another small column count instead of assuming one horizontal row will always fit;
- keep read-only reports multiline instead of trying to force long status text into a single compact row.

Example:

```python
inspector.button_row(
    "actions",
    "Actions",
    buttons=(("preview", "Preview"), ("apply", "Apply"), ("export", "Export diagnostics")),
    columns=2,
)
```

The native Qt adapter now wraps dense button rows automatically, but creators should still declare a compact layout explicitly when the section is action-heavy.

## Qt adapter

The declaration remains Qt-free. The app can render it through:

```python
from laserprog_studio.ui.inspector_panel_adapter import InspectorPanelQtAdapter

widget = InspectorPanelQtAdapter.create_widget(ctx.inspector, parent=right_tool_area)
```

Tool code should still depend on `ctx.inspector`, not on this adapter.
