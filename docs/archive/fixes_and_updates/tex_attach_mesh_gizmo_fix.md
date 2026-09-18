# TEX Attach to mesh gizmo fix

When **Attach to mesh** is enabled, the texture is merged into the source mesh and no separate decal mesh exists.

The TEX gizmo now targets both placement modes:

- decal placement: uses the decal mesh frame;
- attached placement: uses edit-frame metadata stored on the textured source mesh.

Attached meshes now keep the same editable TEX frame fields used by decals:

- `texture_decal_origin`
- `texture_decal_normal`
- `texture_decal_u_axis`
- `texture_decal_v_axis`
- `texture_decal_tile_width`
- `texture_decal_tile_height`

This lets the rotation/scale ring and center move handle remain available while the texture is attached to the mesh.
