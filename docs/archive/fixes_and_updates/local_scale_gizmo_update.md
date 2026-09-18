# Local scale gizmo update

The Scale transform now follows the selected part orientation instead of global world axes.

Changes:

- Scale axis handles use the mesh rotation quaternion to compute local X/Y/Z directions.
- The XY bounds frame is built from oriented local bounds, not world-aligned bounds.
- Dragging frame edges still uses Option B: the opposite local edge stays fixed.
- Scale drag applies along the same local axis that is displayed by the gizmo.
- Inspector Size X/Y/Z now uses oriented local dimensions, so values stay meaningful after rotating a part.

Translation and rotation gizmos are intentionally unchanged and still use world axes for this version.
