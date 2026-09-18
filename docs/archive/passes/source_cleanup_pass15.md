# Source cleanup pass 15 — finish the first Creator API migrations

This pass removes the compatibility shells that remained after migrating the first three built-in tools to the Creator API.

## Tools finalized

- Primitives
- Box Generator
- Acoustic Diffuser

## Removed legacy paths

- The old primitive window bridges (`add_primitive_to_scene`, `_make_primitive_mesh`).
- The legacy Box Generator Qt panel and preview-controller methods.
- The legacy Acoustic Diffuser Qt panel and `application/acoustic_diffuser_controller.py`.
- Tool-preview mixin/router entries for Box Generator and Acoustic Diffuser.
- Tool-panel facade methods for the migrated tools.

## Kept by design

Pure backend code remains in place and is still the implementation source for geometry/fabrication work:

- `primitives/`
- `fabrication/box_generator.py`
- `geometry_ops/acoustic_diffuser.py`

The clean path is now:

`CreatorTool -> ToolContext services -> pure backend module`

No migrated tool should call window methods or own a dedicated Qt panel anymore.
