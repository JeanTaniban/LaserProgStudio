# Pass115 — Minimal point and Blender-style popover

This pass keeps the Tool Core diagnostic layer focused and stable.

## Minimal handle

The `minimal` style is now a simple point/dot rendered through the normal point batch.
It no longer draws a square guide, ring, crosshair or other overlay geometry.
Its feedback is purely semantic color + radius:

- fixed
- grabbable
- hover
- grabbed
- selected

This makes it suitable for dense sketch points in Plan Tracer.

## Overlay stability

The Qt overlay adapter now synchronizes the logical overlay position with the real
widget position before starting a drag. Anchored movable overlays therefore no
longer start dragging from `(0, 0)`, which caused the teleporting/fighting effect.

The drag pointer is also converted through `mapToParent`, keeping pointer math in
one coordinate space.

## Blender-style viewport popover

The overlay layer now exposes `show_context_popover_at_cursor(...)`.
It creates a non-draggable, click-away `context_menu` window beside the pointer.
The Tool Core Diagnostic tool opens this popover on middle click with dummy options.
A viewport click outside closes it.

## Production rule

Tools should use:

- persistent gizmo handles for viewport points;
- `minimal` for dense sketch points;
- `show_context_popover_at_cursor` for transient viewport option popovers;
- draggable overlays only for persistent palettes/inspectors.
