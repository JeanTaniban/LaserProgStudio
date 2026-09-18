# Material render piece-only shadow fix

This update removes the Material render floor receiver from the UI/runtime and keeps only piece-to-piece VTK shadow maps.

## Root cause

The old `Sol de rendu` receiver slab was accidentally acting as a renderer invalidation step. Toggling it on/off forced VTK to rebuild the shadow-map pass, camera clipping range and light-space matrices. Without that extra actor transition, the first shadow-map frame could reuse stale matrices, making shadows appear offset on the objects.

## Fix

- Removed the visible `Sol de rendu` checkbox from the View/Material render panel.
- Pinned the legacy `material_floor_shadow` state to `False` so old sessions cannot recreate the floor.
- The material renderer now always removes any stale `material_render_floor` / `material_shadow_floor` actor.
- Added `prime_vtk_shadow_maps()` to explicitly invalidate and render the VTK shadow pass after enabling shadows:
  - reset camera clipping range;
  - mark camera, lights and renderer as modified;
  - force `SetUseShadows(True)` when available;
  - render once to build fresh shadow-map textures.
- Shadow-pass signatures now use `vtk_shadow_maps_piece_only_v3` and no longer contain a floor signature.

Result: real shadows no longer depend on the render floor workaround, and no floor shadow is drawn.
