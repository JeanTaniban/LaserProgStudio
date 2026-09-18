# Window refactor pass 4 - stabilization and structure

This pass continues the LaserProg Studio V18 refactor without reverting the working
selection/gizmo/clipboard fixes.

## Main changes

- `window.py` is now a thin composition root again. Mutable runtime attributes were
  moved to `src/laserprog_studio/runtime_state.py` through `initialize_runtime_state()`.
- `controllers/interaction.py` was split into focused interaction modules:
  - `interaction_value_fields.py` for value-field click/select behavior.
  - `interaction_gizmo_refresh.py` for throttled transform-gizmo refreshes.
  - `interaction_picking.py` for mesh, gizmo and split-plane picking.
  - `interaction.py` now coordinates Qt events and keyboard shortcuts.
- Added pure, Qt-free geometry helpers in `src/laserprog_studio/services/geometry.py`.
  Clipboard duplication and scene bounds wrappers now delegate to these helpers.
- Added a first lightweight test suite under `tests/`:
  - geometry-service tests;
  - `ModelStore` preview/undo/redo test;
  - simple 3MF roundtrip smoke test;
  - static refactor verification test.
- Extended `scripts/verify_refactor_structure.py` so future refactors protect:
  - the Qt bridge methods in `window.py`;
  - the split interaction structure;
  - static helper decorators that previously broke gizmos and clipboard;
  - the runtime-state initializer.

## Small bug cleanup

- Fixed a diagnostic log line in `load_3d_model()` that referenced an undefined
  `reason` variable inside a swallowed exception block.

## Validation

The following checks were run after the pass:

```text
python -m compileall -q src scripts tests
python scripts/verify_refactor_structure.py
python -m unittest discover -s tests -v
```

All checks passed in the lightweight environment. The full Qt/PyVista window still
needs to be validated on a workstation with the GUI dependencies installed.
