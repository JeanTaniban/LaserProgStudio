# Pass182 - AutoPreview and native overlay lifecycle

## Direction

The Creator API owns light-tool AutoPreview and overlay lifecycle. A tool author declares intent; the runtime handles timing, cleanup and widget behaviour.

## AutoPreview

A panel can now request native debounced preview regeneration:

```python
ctx.inspector.set_panel(
    inspector.panel(
        "My tool",
        id=tool_id,
        owner_tool=tool_id,
        auto_preview=inspector.auto_preview(action_id="preview", debounce_ms=250),
        sections=[...],
    )
)
```

The runtime restarts one debounce timer after user-editable inspector value changes and triggers the existing preview action. Tools must not create Qt timers or duplicate preview callbacks per field.

## Overlay lifecycle

`ctx.cleanup_tool(...)` now closes tool-owned overlay specs and synchronises the Qt overlay layer immediately. Leaving the Gizmo Catalog no longer leaves visible overlay widgets behind.

## Overlay overlap bug

The Qt overlay adapter now keeps the dragged overlay above sibling overlays while dragging, avoids re-raising siblings during a drag sync, repaints the parent region before/after moves, and fixes widget height to the visible frame. This prevents stale hit rectangles and paint artifacts when one overlay crosses another.
