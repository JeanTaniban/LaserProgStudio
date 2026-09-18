# Architecture Migration Pass 2 — configurable toolbar controller

Goal: move the configurable top-toolbar workflow out of inherited UI behavior and
into a composed controller while keeping the current Qt signals and legacy button
attributes stable.

## Inspection result

`ui/configurable_toolbar.py` had already isolated the top toolbar from the large
workspace layout, but it was still an active mixin. It owned several unrelated
responsibilities at once:

- sanitising and persisting toolbar item ids;
- building dynamic Qt buttons;
- routing clicks to tools, modifiers and booleans;
- handling trash/remove mode visuals;
- opening the add-tool palette.

That made the file easier than the old monolithic layout, but it was still
inheritance-driven. Future contributors still had to understand that toolbar
state lived implicitly on `MainWindow` through mixin methods.

## Changes made

A composed controller now owns the workflow:

```text
src/laserprog_studio/application/toolbar_controller.py
```

It introduces:

- `ConfigurableToolbarController`;
- explicit setup/rebuild/add/remove/activate methods;
- the trash-mode styles and button availability override;
- palette opening and toolbar registry lookups.

`runtime_state.initialize_runtime_state()` now creates:

```python
self.toolbar_controller = ConfigurableToolbarController.create(self.app_context)
```

`ui/configurable_toolbar.py` is now a compatibility facade. Existing signal
connections can still call methods such as `_set_toolbar_remove_mode`,
`add_toolbar_item` and `open_toolbar_palette`, but those methods delegate to the
controller.

## Why this matters

Adding future tools should increasingly follow this chain:

```text
ToolSpec / StudioTool
       +
ToolbarItemSpec
       ↓
ConfigurableToolbarController
       ↓
legacy MainWindow attributes only where compatibility is still required
```

The toolbar is now closer to a plugin host than a handwritten set of inherited
button behaviors. The old attributes such as `btn_tool_material`,
`btn_mod_repair` and `btn_bool_union` are still populated dynamically, so the
existing lifecycle and selection-policy code keeps working while it is migrated.

## Guardrails added

- `tests/test_architecture_migration_pass2.py` checks that the controller owns
  the real toolbar workflow and that the old mixin remains lightweight.
- `scripts/verify_refactor_structure.py` now expects the controller as part of
  the refactor contract.
- `scripts/audit_architecture_health.py` reports the toolbar controller as a
  composition component.

## Next recommended pass

Migrate the layout restoration / inspector-open behavior next:

```text
controllers/layout_restore.py
       ↓
application/layout_controller.py or ui/layout_controller.py
```

That area is less risky than texture projection and gizmo internals, but it is
central to tool opening, right-panel behavior and Light UI. It is also still a
mixin that relies heavily on implicit `self` state.
