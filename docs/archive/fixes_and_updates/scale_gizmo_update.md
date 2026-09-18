# Scale gizmo update

This update adds the first Scale transform gizmo.

## Behavior

- Transform mode `S` now displays scale handles.
- X, Y and Z scale handles use colored foreground axes with cube handles.
- Dragging an axis handle scales the selected part along that world axis from the part bounds center.
- An XY bounds frame is displayed around the selected part.
- Dragging a bounds-frame edge scales the selected part from the opposite edge.

## Frame edge behavior

The frame uses Option B:

- dragging `x_min` keeps `x_max` fixed;
- dragging `x_max` keeps `x_min` fixed;
- dragging `y_min` keeps `y_max` fixed;
- dragging `y_max` keeps `y_min` fixed.

This makes the frame feel like a direct stretching tool.

## Implementation notes

- The gizmo is rendered in the existing foreground VTK renderer.
- No camera observer is added.
- Hover uses the existing throttled gizmo picking path.
- Scaling is applied directly to mesh vertices.
- The initial implementation uses world-aligned bounds and world axes only.
