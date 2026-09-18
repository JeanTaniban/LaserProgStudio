# Split plane relative position and forward handle

This update improves the Split by plane modifier.

## Relative position

The plane Position fields are now offsets relative to the current selected part or selected group center.

Example:

- Position offset X/Y/Z = 0/0/0 places the cutting plane at the selected part/group center.
- Changing the selection moves the zero reference to the new selection center.

If no part is selected, the zero reference falls back to the scene center.

## Manual forward movement

The split plane now has a yellow forward handle. Dragging this handle slides the cutting plane along its local forward/normal axis.

The drag updates the same Position offset fields, so the UI and 3D handle stay synchronized.

## Notes

The split math still uses the final world-space plane origin and normal. Only the UI position values are now expressed relative to the selected geometry.
