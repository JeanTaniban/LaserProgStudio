# Source cleanup pass 21 — Creator preview camera stability

## Goal

Creator API preview actions must be non-disruptive: clicking Preview stages the
candidate meshes but must not move, zoom, center or otherwise alter the current
camera. The user view is considered part of the editing context.

## Runtime change

Removed camera focus calls from migrated Creator preview paths:

- `PrimitiveCreatorTool._stage_preview(...)`
- `BoxCreatorTool._stage_preview(...)`
- `AcousticDiffuserCreatorTool._stage_preview(...)`
- `RepairMeshCreatorTool._preview_action(...)`
- `SimplifyCreatorTool._preview_action(...)`
- `HollowCreatorTool._preview_action(...)`

Preview still updates the staged mesh set and the scene selection, but leaves the
camera exactly where it was.

## Guard

Added `tests/test_pass164_creator_preview_no_camera_focus.py` to prevent
`ctx.view.focus_*` calls from returning inside migrated Creator preview methods.
