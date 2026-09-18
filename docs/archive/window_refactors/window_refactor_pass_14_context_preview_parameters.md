# Window refactor pass 14 - Context, PreviewController and ParameterPanelFactory

This pass prepares LaserProg Studio for larger extension work without adding the
future tools yet.

## Added

- `app_context.py` introduces `AppContext`, a migration bridge that exposes
  stable state objects to future tools/modifiers without passing the whole
  `QMainWindow` as an implicit global.
- `state/preview_state.py` stores user-facing preview metadata separately from
  `ModelStore`, which still owns the preview meshes.
- `controllers/preview_controller.py` centralizes preview helpers:
  `has_preview`, `set_preview_meshes`, `commit_preview_to_model`, and
  `discard_preview_only`.
- `parameters/panel_factory.py` adds `ParameterPanelFactory`, a lazy-Qt form
  generator for declarative `ParameterSpec` lists.
- `ToolSpec` can now carry parameter definitions and validate/default them.

## Why

Future features such as simplify, hollow, text relief, extrude-down, primitive
subdivisions and texture projection will all need the same preview/apply/cancel
workflow and compact parameter panels. Centralizing these contracts now prevents
those features from being hard-coded directly into `scene.py`, `tool_panels.py`
or `tool_lifecycle.py`.

## Added after validation

- `geometry_ops/result.py` introduces `OperationResult`, a standard return type
  for future pure geometry operations. This is the intended contract for
  simplify, hollow, relief, extrude-down and UV/texture projection operations.
- `PreviewControllerMixin.set_preview_result()` can consume an `OperationResult`
  and route success/warnings/errors through the same preview workflow.
