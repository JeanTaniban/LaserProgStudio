# Source cleanup pass 229 — Texture projection creator split

`tooling/texture_projection_creator_tool.py` is now a public creator-tool facade
instead of a single 893-line implementation blob.

Runtime ownership is split into private modules:

- `tooling/texture_projection_creator_tool.py`: public Creator tool and legacy adapter surface.
- `tooling/_texture_projection_params.py`: texture asset import, booleans and `TextureProjectionParams` construction.
- `tooling/_texture_projection_operations.py`: preview/clear operations and selection validation.
- `tooling/_texture_projection_panel.py`: inspector panel declaration.
- `tooling/_texture_projection_geometry.py`: vector, mesh extent and display/world helpers.
- `tooling/_texture_projection_projector.py`: interactive viewport projector, handles, overlay and drag runtime.
- `tooling/_texture_projection_constants.py`: shared handle/window ids.

The public API remains compatible: `TextureProjectionCreatorTool`,
`TextureProjectionTool` and `texture_params_from_values` are still imported from
`tooling.texture_projection_creator_tool`.

Next cleanup should target `application/tool_core_diag_scene.py` or split
`tool_api/_ui_motif_builder.py` further by motif family.
