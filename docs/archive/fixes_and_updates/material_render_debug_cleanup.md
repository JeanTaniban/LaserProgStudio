# Material render cleanup and diagnostics

This pass fixes material-render side effects leaking into Solid/Wireframe.

## Changes

- Added `rendering/material_scene.py` as the small central module for material-render settings, actor-count diagnostics and shadow reset helpers.
- Material render mode now owns all temporary scene side effects from one place: receiver floor, custom lights and optional shadows.
- Leaving Material mode always removes the receiver floor and disables shadows before returning VTK to automatic lights.
- Toggling `Ombres` or `Sol récepteur` now applies immediately and logs the cleanup/rebuild path.
- Rebuilds reset stale Python actor handles after `plotter.clear()`, so cached material floor handles cannot point to deleted props.
- Startup event filtering no longer crashes if Qt sends events before the PyVista plotter exists.

## Diagnostic log markers

Look for these tags in `diagnostics/laserprog_studio_v18.log`:

- `[DISPLAY_PIPELINE] set_display_mode ...`
- `[DISPLAY_PIPELINE] apply_display_mode ...`
- `[MATERIAL_RENDER] sync begin ...`
- `[MATERIAL_RENDER] floor cleanup ...`
- `[MATERIAL_RENDER] floor created ...`
- `[MATERIAL_RENDER] shadows enabled ...`
- `[MATERIAL_RENDER] shadows disabled ...`
- `[MATERIAL_RENDER] sync end material ...`
- `[MATERIAL_RENDER] sync end non-material ...`

These logs include renderer prop counts before/after cleanup so persistent ghost actors are easier to identify.
