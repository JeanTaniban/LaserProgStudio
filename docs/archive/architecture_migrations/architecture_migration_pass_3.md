# Architecture Migration Pass 3 — layout controller

Goal: move the tool-inspector / Light UI restoration workflow out of inherited
MainWindow behavior and into a composed controller, while keeping existing tool
lifecycle calls stable.

## Inspection result

`controllers/layout_restore.py` was already separated from `tool_lifecycle.py`,
but it was still an active mixin. It owned important behavior through implicit
`self` attributes:

- remember compact/light UI state before opening a tool;
- open the right inspector when a tool needs it;
- restore compact transform overlay mode after the tool closes;
- preserve or restore splitter sizes when a tool temporarily enlarged the right
  pane;
- coordinate with splitter drag events from the Light UI module.

This was safer than having the code inside tool lifecycle, but still hard for an
external contributor: a tool opening could mutate splitter state, tool state and
legacy restore flags without an explicit owner.

## Changes made

A composed controller now owns this workflow:

```text
src/laserprog_studio/application/layout_controller.py
```

It introduces:

- `LayoutController`;
- `InspectorRestoreSnapshot` for the temporary restore state;
- `remember_before_tool_open()`;
- `ensure_inspector_open()`;
- `restore_after_tool_close()`;
- `note_user_splitter_drag()`.

`runtime_state.initialize_runtime_state()` now creates:

```python
self.layout_controller = LayoutController.create(self.app_context)
```

`controllers/layout_restore.py` is now a compatibility facade. Existing calls
such as `_ensure_inspector_open()` and `_restore_inspector_mode_after_tool_close()`
still work, but they delegate to `LayoutController`.

## Compatibility bridge

The controller keeps synchronisation with the legacy window attributes:

```text
_restore_light_ui_after_tool
_restore_light_ui_sizes
_restore_splitter_after_tool_close
_splitter_user_dragged_during_tool
```

This avoids a risky rewrite of Light UI and tool lifecycle in one pass. New code
should use the controller methods instead of writing those attributes directly.

## Why this matters

Tool opening is now closer to a professional composition model:

```text
ToolLifecycleMixin compatibility call
       ↓
LayoutController
       ↓
InspectorRestoreSnapshot + AppContext
       ↓
legacy Qt splitter methods only where still required
```

This makes the next tool/plugin work cleaner because future tools can request an
inspector through a named controller instead of relying on hidden MainWindow
mixin methods.

## Guardrails added

- `tests/test_architecture_migration_pass3.py` checks that the controller owns
  the inspector workflow and the old mixin remains lightweight.
- `scripts/verify_refactor_structure.py` now verifies the controller, not the
  facade, for layout restoration details.
- `scripts/audit_architecture_health.py` reports the layout controller as a
  composition component.

## Next recommended pass

Migrate export/render commands next:

```text
controllers/exporting.py
controllers/render_output.py
        ↓
application/export_controller.py
```

This is a good next target because it is visible, useful for external
contributors, and less risky than moving texture projection, gizmo or deep VTK
interaction code.
