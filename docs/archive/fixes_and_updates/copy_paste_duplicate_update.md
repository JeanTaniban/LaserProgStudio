# Copy, paste, and view-based duplicate update

This update removes the remaining camera shortcut behavior from Ctrl+V and adds real clipboard-style duplication.

## Shortcuts

- Ctrl+C copies the current selected part or multi-selection.
- Ctrl+V pastes the copied part or multi-selection.
- Ctrl+D duplicates the current selected part or multi-selection immediately.
- V and Ctrl+V no longer trigger a camera preset. Camera changes remain available through the View buttons.

## Placement rule

New copies are offset from the source selection along the world axis that is most visible from the current camera and closest to screen-right. This keeps pasted/duplicated geometry out of the camera-depth direction.

The offset distance is:

```text
offset = 2 * bounds_size_along_selected_axis
```

If the measured size is degenerate, a 1 mm fallback is used so the copy never appears exactly on top of the source.

## Multi-selection

Copy, paste, and duplicate preserve multi-selection as a group. The newly created parts become the active selection. Repeated paste marches from the last pasted position instead of stacking every pasted copy on the same coordinates.
