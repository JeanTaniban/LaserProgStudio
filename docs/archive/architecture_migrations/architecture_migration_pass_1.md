# Architecture Migration Pass 1 — action controller extraction

Goal: make the first real move away from a many-mixin `MainWindow` architecture
without touching the fragile rendering, texture or gizmo subsystems.

## Inspection result

The project still contains many compatibility mixins. The safest high-impact
area for the first migration is the command layer connected to menu shortcuts:

- undo / redo;
- drag undo snapshot capture / commit;
- copy / paste / duplicate;
- delete selected;
- new scene.

These commands are important enough to prove the composition model, but isolated
enough to migrate without changing low-level VTK interaction.

## Changes made

A new package was added:

```text
src/laserprog_studio/application/
  __init__.py
  action_controller.py
```

It introduces:

- `LegacyWindowController` — temporary adapter around `AppContext.owner`;
- `HistoryController`;
- `ClipboardController`;
- `SceneEditController`;
- `StudioActionController`.

`runtime_state.initialize_runtime_state()` now creates:

```python
self.action_controller = StudioActionController.create(self.app_context)
```

The old files now act as compatibility facades:

```text
controllers/history_actions.py
controllers/clipboard_actions.py
controllers/scene_edit_actions.py
```

They keep existing QAction connections and shortcut behavior stable while the
real implementation lives in composed controllers.

## Contributor guardrails added

- `docs/architecture.md` defines the target architecture and the no-new-mixins
  rule.
- `tests/test_architecture_migration_pass1.py` verifies that the migrated action
  layer is composed from `AppContext` and that the old mixins stay lightweight.
- `scripts/audit_architecture_health.py` gives a quick static report of mixin
  count, large files and composition components.

## Next recommended pass

Migrate the configurable toolbar from `UIConfigurableToolbarMixin` into a
`ToolbarController` / `ToolbarState` pair. This is the next best target because
it is central to tool integration but less dangerous than the gizmo, texture
projection or mesh repair internals.
