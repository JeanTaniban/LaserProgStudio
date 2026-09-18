# Window refactor Qt event bridge fix

## Symptom

After the window refactor, transform gizmos were still not visible and viewport selection stopped working.

## Root cause

`LaserProgStudioV18` correctly keeps `QMainWindow` as the first base class for PySide/VTK stability, but that also means Qt virtual methods exposed by `QMainWindow`/`QObject` shadow methods placed later in Python mixins.

The extracted `InteractionMixin.eventFilter()` was therefore not called by Qt even though it existed. The installed event filter fell back to the Qt base implementation, so mouse clicks no longer reached LaserProg's selection and gizmo picking code.

## Fix

`window.py` now keeps the professional refactored structure while defining explicit bridge methods directly on `LaserProgStudioV18`:

- `eventFilter()` -> `StudioControllersMixin.eventFilter()`
- `keyPressEvent()` -> `StudioControllersMixin.keyPressEvent()`
- `keyReleaseEvent()` -> `StudioControllersMixin.keyReleaseEvent()`
- `closeEvent()` -> `StudioControllersMixin.closeEvent()`

This preserves `QMainWindow` as the first base while restoring the behavior that existed when these methods lived directly in the monolithic `window.py`.

## Additional mixin safety

The extracted Qt event handlers no longer use zero-argument `super()` for Qt fallback calls. They explicitly call the Qt base methods (`QMainWindow.keyPressEvent`, `QMainWindow.keyReleaseEvent`, `QMainWindow.closeEvent`) so they remain safe when invoked through bridge methods.

## Regression guard

`scripts/verify_refactor_structure.py` now checks that these bridges remain present.
