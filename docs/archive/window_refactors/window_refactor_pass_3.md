# Window refactor pass 3 - main-window decomposition

This pass completes the previously-started decomposition of `src/laserprog_studio/window.py`.

## Result

`window.py` now contains only:

- shared imports through `_window_deps.py`;
- the `LaserProgStudioV18` constants;
- the constructor and runtime state initialization;
- composition of UI and controller mixins.

The former 7000-line monolith has been split into focused modules under:

- `src/laserprog_studio/ui/` for actions, menus, panels, tool widgets, floor grid, transform controls and light overlay UI;
- `src/laserprog_studio/controllers/` for interaction, scene state, camera navigation, tool previews, split-plane modifier, gizmos, transforms, engraving roles, booleans, clipboard/history and export workflows.

## Composition

The main window now inherits from:

```python
class LaserProgStudioV18(UIPanelsMixin, StudioControllersMixin, QMainWindow):
    ...
```

`UIPanelsMixin` is assembled in `ui/panels.py`.
`StudioControllersMixin` is assembled in `controllers/__init__.py`.

## Behavior-preserving approach

The methods were moved verbatim from the previous `window.py` into the new modules. The only functional path adjustment was relative boolean imports after moving boolean methods one package deeper:

```python
from ..boolean_ops import ...
```

`_window_deps.py` was also updated to include `QAbstractItemView` and `QItemSelectionModel`, because those symbols are now shared by the extracted UI/scene modules.

## Smoke checks performed

- `python -m compileall -q src`
- ModelStore 3MF smoke load/export using `examples/box.3mf`
- AST structure check with `scripts/verify_refactor_structure.py`

The GUI itself still requires the runtime desktop dependencies (`PySide6`, `pyvista`, `pyvistaqt`, `vtk`, `manifold3d`) to be installed on a machine with display support.

## Next recommended pass

The next useful pass is not another blind extraction. It should reduce coupling inside the largest extracted controllers:

1. `controllers/interaction.py`
2. `controllers/scene.py`
3. `controllers/booleans_clipboard_history.py`
4. `ui/tool_panels.py`

Recommended target: introduce small state dataclasses for transform drag state, split-plane state, light UI state and selection state. That would make testing easier without booting Qt/VTK.
