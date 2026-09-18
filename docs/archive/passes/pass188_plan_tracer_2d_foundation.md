# Pass188 — Plan tracer 2D foundation

This pass restarts `Plan tracer` on top of the Creator API instead of the legacy planar hook path.

## What changed

- `plan_trace` now resolves to `PlanTrace2DTool`, a `CreatorStudioToolAdapter` around `PlanTrace2DCreatorTool`.
- The built-in registry no longer attaches `_initialize_plan_trace_tool` / `_clear_planar_tool_state` to Plan tracer.  Those legacy hooks remain available only where older planar tools still need them.
- `tool_api.planar_drawing` exposes the official locked-plane drawing helpers.
- The first user action picks the drawing height from a face/object raycast fallback chain.
- The tool locks the drawing plane to the nearest camera-oriented planar view.
- The overlay toolbox is declared through `ctx.overlay` and uses exclusive grouped buttons.
- The active drawing cursor uses the official `diamond` style.
- Placed points use official grabbable `minimal dot` actors.
- Smart snap runs through the shared scene cache and includes already placed plan points.

## Scope

Only `Point` placement is implemented.  `Modify`, `Line`, `Rectangle`, `Circle` and `Half-circle` exist in the toolbox as the intended UX skeleton.  `Escape` switches to `Modify`.

## Runtime rule

Plan tracer must not render its own dots or build custom Qt/PyVista UI.  It declares actors and overlays; the native Creator runtime owns hover/select/grab, empty-click clearing, fast drag refresh, overlay lifecycle and repaint policy.
