# Window refactor clipboard staticmethod fix

## Problem

After the window refactor, copy/paste/duplicate still failed even after gizmos came back.
The remaining failure was another static-method regression introduced during extraction from the old monolithic `window.py`.

`BooleanClipboardHistoryMixin._bounds_axis_size()` was originally static. Without `@staticmethod`, calls like:

```python
self._bounds_axis_size(bounds, axis)
```

receive `self` implicitly and raise a `TypeError`. This breaks the camera-based duplicate/paste offset before any new mesh is appended.

A related audit also found static quaternion helpers in `TransformMathMixin` that had lost their decorators. They are restored too, because rotation/scale gizmo code relies on them.

## Fix

- Restored `@staticmethod` on `_bounds_axis_size`.
- Restored `@staticmethod` on the extracted quaternion/angle math helpers.
- Added explicit clipboard diagnostic logs for blocked checks.
- Extended `scripts/verify_refactor_structure.py` to guard these static methods.

## Expected behavior

- `Ctrl+C` copies the selected mesh(es).
- `Ctrl+V` pastes copied mesh(es) with a visible camera-based offset.
- `Ctrl+D` duplicates selected mesh(es) directly with the same visible offset.
- Selection moves to the newly appended mesh(es).
