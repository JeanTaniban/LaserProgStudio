# Pass 19 - Selection box visibility and picking fix

Fixes the Shift+drag group selection regression.

## Changes

- Replaced theme-dependent `QRubberBand` with a custom transparent `SelectionBoxOverlay` widget.
- Converted VTK display coordinates to Qt logical widget coordinates before intersecting actor bounds.
- Handles high-DPI render windows where VTK pixels differ from Qt mouse coordinates.
- Added diagnostic logs for selection-box hits.

This keeps group selection in the controller layer while the visual overlay lives in `ui/`.
