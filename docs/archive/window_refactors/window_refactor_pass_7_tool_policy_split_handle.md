# Window Refactor Pass 7 - Tool policy and split handle sizing

## Fixes

### Primitive tool selection policy

`Primitives` is a creation tool, not a target-modification tool. It must be available even when the scene is empty or when no part is selected.

The tool registry now declares:

```python
ToolSpec(
    id=TOOL_PRIMITIVE,
    selection_policy="none",
)
```

This prevents the generic tool lifecycle guard from showing the incorrect message: "Select at least one target part before opening Primitives."

### Split-plane handle thickness

The yellow split-plane arrow was visually too thick because its shaft/tip radii were directly proportional to the preview plane size.

The arrow length still follows the plane size so the handle remains easy to find, but the shaft/tip thickness is now computed by `_split_plane_handle_dimensions()` using the camera-visible height at the plane origin, capped by the plane-size basis.

This makes the arrow thinner by design and keeps its apparent thickness tied to the current camera framing instead of to the arbitrary cut-plane size.

## Regression guards

Added tests/static checks for:

- `Primitives` must not require selection.
- Split-plane arrow thickness must use `_camera_visible_height_at(origin)`.
- Old direct `size * 0.0030` / `size * 0.0100` radius logic must not come back.
