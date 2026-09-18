# TEX attach-to-mesh live drag deep fix

## Root causes found

1. **Attached texture translation was mathematically cancelled**  
   In `compute_projected_uvs()`, when `preserve_aspect=True`, the planar UV code always re-centered UVs on the selected face bounding-box centre (`ctu/ctv`).  
   During Attach-to-mesh centre-handle drag, `projection_origin` changed correctly, but `ctu/ctv` changed by the same amount, so the final UVs stayed effectively identical.  
   Result: the blue centre handle could be grabbed, but the texture did not move.

2. **Full preview rebuilds were still reachable during mouse drag**  
   If a fast live update failed, the drag handler called `generate_texture_projection_preview()`. That deep-copies meshes, rebuilds the scene and recreates gizmo actors.  
   Result: texture/gizmo blinking and heavy drag stutter.

3. **Move drag refreshed the gizmo repeatedly**  
   The centre-handle move path requested `update_texture_rotation_gizmo()` during drag. That clears/recreates the ring and centre sphere.  
   Result: the gizmo itself flickered even when the texture fast-path succeeded.

## Fix

- If `projection_origin` is explicitly provided, it is now treated as the texture centre in attached-to-mesh planar UVs.
- The auto-face-centre behaviour is kept only when no explicit origin exists.
- Full preview rebuilds are no longer called from mouse-move events.
- If the live UV update fails, the tool marks a fallback flag and performs at most one safe rebuild at drag end.
- The move handle no longer refreshes/recreates the gizmo during each drag sample.
- High-frequency VTK/poll mouse logs are now debug-only.

## Regression test

Added `test_attached_texture_origin_move_changes_uvs()` to ensure moving the attached projection origin changes UV coordinates.
