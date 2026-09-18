# Architecture Migration Pass 5 - Preview controllers

Pass 5 moves the preview session lifecycle and the legacy preview generators out
of the MainWindow mixin inheritance chain.

## Migrated controllers

- `PreviewController` owns preview staging, preview state refresh,
  `OperationResult` handling, commit-to-model and discard-only operations.
- `ToolPreviewController` is the routing point used by legacy Qt callbacks.
- `FabricationPreviewController` owns box, lay-flat and joint preview workflows.
- `ModifierPreviewController` owns simplify, relief, extrude-down and hollow
  preview workflows.

All of these controllers are composed from `AppContext` in `runtime_state.py`.

## Compatibility facades

The historical mixin files remain so existing UI signal connections and tool
lifecycle hooks keep their names:

- `controllers/preview_controller.py` delegates to `PreviewController`;
- `controllers/tool_previews.py` delegates to `ToolPreviewController`.

Those files should stay small. New preview behaviour should go into a controller,
service or `StudioTool`, not into a mixin.

## Headless import rule

Preview generator controllers avoid importing `_window_deps` at module import
time. Qt symbols such as `QMessageBox` and `QTimer` are resolved lazily only when
a UI preview operation runs. This keeps static architecture tests usable without
PySide6.

## Impact

This pass removes the core preview lifecycle and about 785 lines of preview
generator logic from active MainWindow mixins. The old `tool_previews.py` file is
now a narrow compatibility adapter, while the preview responsibilities are
discoverable by domain.

## Next target

The next recommended migration target is the tool lifecycle itself:

- `controllers/tool_lifecycle.py`;
- selected tool-open/close hooks that can become `StudioTool` methods.

That pass should reduce direct calls such as `_invoke_tool_hook(...)` and start
turning individual tools into explicit runtime objects.
