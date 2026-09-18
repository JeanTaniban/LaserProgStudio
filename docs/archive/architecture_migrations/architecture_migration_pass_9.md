# Architecture Migration Pass 9 — Texture projection controller, toolbox state fix

## Why this pass exists

Pass 9 fixes a visible regression reported after the tool-lifecycle migration:
when a tool was closed, its button could remain checked in the toolbox even
though `active_tool` had returned to `TOOL_NONE`.

The root cause is Qt-specific: buttons live in exclusive `QButtonGroup` objects,
and the currently checked button may not clear with a simple
`button.setChecked(False)`. Tool close/apply/cancel now temporarily disables the
exclusive group while clearing checks.

This pass also starts the high-risk texture-projection migration. The file
`controllers/texture_projection_tool.py` was the largest remaining controller
mixin. The pass extracts the safe, non-gizmo workflows first, leaving direct
mouse-drag/gizmo code untouched.

## What moved

New controller:

- `application/texture_projection_controller.py`

It now owns:

- selected texture target resolution;
- texture file selection;
- texture asset registration;
- UI-to-`TextureProjectionParams` conversion;
- texture projection report updates;
- face-pick anchor helpers;
- preview generation;
- apply-from-pick workflow;
- clear selected texture projection workflow.

The legacy mixin keeps compatibility wrapper methods with the historical names.
The remaining TEX gizmo code still lives in `controllers/texture_projection_tool.py`
for now.

## Runtime composition

`runtime_state.initialize_runtime_state()` now composes:

```python
self.texture_projection_controller = TextureProjectionController.create(self.app_context)
```

This follows the same composition direction as the action, toolbar, layout,
preview, lifecycle and boolean controllers.

## Guardrails

- `TextureProjectionController` must not import `.._window_deps` directly.
- Qt file dialog access is lazy through `_qfiledialog()`.
- `TextureProjectionToolMixin` must keep shrinking and delegate selected TEX
  workflows to the composed controller.
- Tool close/apply/cancel must clear exclusive toolbox button groups through
  `ToolLifecycleController._clear_button_group_checks()`.

## Remaining TEX work

The remaining texture-projection file is still large because it owns gizmo and
live-update interaction code. Future passes should split it into focused pieces:

- texture target resolution;
- texture transform gizmo state;
- texture transform picking;
- fast live UV/decal update;
- VTK observer / global event filter lifecycle.
