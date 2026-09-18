# V55 — Texture Projection attached-face saved colour fallback

## Problem

When **Texture Projection > Attach to mesh** was used on a picked face, the clicked face received the bitmap correctly, but uncovered faces could appear transparent or wrong-coloured on some VTK/PyVista builds.

The root cause was that an attached VTK texture is actor-wide. Even if only one face is intended to be textured, every point of the actor still needs valid texture coordinates and a stable fallback texel. Relying on clamp/border behaviour is not robust enough across VTK versions.

## Contract

Before applying a texture, LaserProg now stores the source model colour explicitly:

- `texture_pre_projection_role_color`
- `texture_pre_projection_material_color`
- compatibility aliases `texture_saved_*`

Uncovered faces of attached face projections sample an opaque padded texel using that saved colour. Clearing the texture restores the saved colour/material instead of keeping the temporary white texture material.

## Implementation notes

- `geometry_ops/texture_projection_decal.py`
  - saves pre-projection role/material colours;
  - preserves these values across reapply/switch mode;
  - restores them when texture metadata is cleared.

- `geometry_ops/texture_projection_operations.py`
  - keeps uncovered attached faces on `_border_uv()`;
  - shifts covered UVs into the real image area of the padded texture;
  - forces non-repeat mode when a face-attached mesh has uncovered faces.

- `application/texture_gizmo_live_update_service.py`
  - live TEX drag now uses the same coverage-masked UV computation as apply/preview for attached face projections.

- `rendering/textures.py`
  - border colour lookup prefers the saved pre-projection colour attributes.

## Tests

Added regressions in `tests/test_pass307_texture_projection_attach_pan_stretch.py` covering:

- saved source colour and material colour;
- role/material display border colour lookup;
- repeat forced off for covered/uncovered attached faces;
- reapply not turning fallback white;
- clear restoring the saved source colour/material.
