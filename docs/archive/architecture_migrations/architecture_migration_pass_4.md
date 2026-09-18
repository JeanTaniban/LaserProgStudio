# Architecture Migration Pass 4 - Export and render output controllers

Pass 4 moves another visible workflow out of inherited mixins and into explicit
application controllers.

## Migrated controllers

- `ExportController` now owns primitive insertion, 3MF export, the engraving
  export workspace, engraving raster generation, Falcon SVG export and engraving
  metadata export.
- `RenderOutputController` now owns render-camera helpers and the final render
  preview window workflow.

Both controllers are composed from `AppContext` in `runtime_state.py`.

## Compatibility facades

The legacy mixins still exist because menus, toolbar actions and older code call
methods by their historical names:

- `controllers/exporting.py` delegates to `ExportController`;
- `controllers/render_output.py` delegates to `RenderOutputController`.

Those files should remain small compatibility facade modules. New export or
render-output behavior should not be added to the mixins.

## Headless import rule

The new controllers intentionally avoid importing Qt-heavy symbols at module
import time. UI-only objects such as `QFileDialog`, `QMessageBox`, `QTimer` and
`RenderPreviewDialog` are resolved lazily when a UI operation runs. This keeps
architecture tests and lightweight CI environments independent from PySide6.

## Impact

This pass removes two functional areas from the MainWindow inheritance chain and
makes export/render-output responsibilities more discoverable for external
contributors. It also reduces the old export and render-output mixins to short
adapters.

## Next target

The next recommended migration target is the preview lifecycle:

- `controllers/preview_controller.py`;
- the safest parts of `controllers/tool_previews.py`.

That area is central for tools, but it should be migrated carefully because it
interacts with temporary meshes, active tools and apply/cancel workflows.
