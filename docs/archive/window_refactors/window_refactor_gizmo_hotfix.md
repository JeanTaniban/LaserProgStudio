# Window refactor gizmo hotfix

This hotfix keeps the refactored `window.py` / mixin structure but restores a safer Qt inheritance order.

## Problem

The first refactor pass declared the main window as:

```python
class LaserProgStudioV18(UIPanelsMixin, StudioControllersMixin, QMainWindow):
```

For PySide6 / Qt / VTK integration, the concrete Qt base must remain first in the MRO. Putting pure Python mixins before `QMainWindow` can break or destabilize Qt-side behavior and renderer/widget integration, including transform gizmo overlays.

## Fix

The main class now uses:

```python
class LaserProgStudioV18(QMainWindow, UIPanelsMixin, StudioControllersMixin):
```

The extracted modules are kept. The monolithic structure is not restored.

## Guardrail

`scripts/verify_refactor_structure.py` now statically checks that:

- `LaserProgStudioV18` inherits from `QMainWindow` first;
- `UIPanelsMixin` and `StudioControllersMixin` are still attached;
- gizmo/transform mixins are included in `StudioControllersMixin`;
- `window.py` only defines the constructor.
