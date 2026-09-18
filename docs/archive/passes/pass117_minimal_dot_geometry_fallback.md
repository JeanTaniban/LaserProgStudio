# Pass117 - Minimal dot geometry fallback

## Problem

The minimal handle still behaved like a tiny raw point on some machines: it was hard to size reliably and state color changes were not visible enough.

## Decision

The Tool Core keeps the public semantic style as `minimal`, but the live viewport painter no longer relies on a raw GL point for that style.  It renders a tiny persistent filled disc aligned with the axis-locked GUI plane.  This gives the user a simple dot while keeping full control over apparent size and color.

## Implementation

- `GizmoPointStyle.geometry_dot` was added.
- `minimal` keeps `guide_shape="none"` and `draw_core=True` for API compatibility.
- The live painter routes `minimal` handles to persistent `dotdisc_*` actors instead of point sprites.
- Dot discs are batched by style/state/size/color.
- Color, opacity and line width updates are applied in place on existing actors.
- No destructive clear/rebuild path was added.

## Why not raw points only?

VTK/PyVista point size is useful for simple point clouds, but OpenGL point size support can be limited by the driver and backend.  A tiny geometry disc is more deterministic for interactive GUI handles.
