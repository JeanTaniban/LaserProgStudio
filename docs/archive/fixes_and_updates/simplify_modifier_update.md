# Simplify modifier update

Mission 1 adds a new **Simplifier** modifier.

## UI

- New `SIM` button in the Modifiers toolbar.
- New right-side panel `Modifier - Simplifier`.
- Slider from 0 to 95%; larger value means stronger decimation.
- Live preview whenever the slider or preservation toggle changes.
- Toggle: `Garder forme extérieure / trous`.
- Report showing selected-object count and triangle count before/after.

## Behavior

- Applies to all selected objects.
- Preview uses committed meshes as the source, so changing the slider does not repeatedly decimate an already-decimated preview.
- Apply/Cancel reuse the existing preview lifecycle.
- With topology preservation enabled, meshes with open/non-manifold boundary edges are rejected. Closed objects with real through-holes remain valid.
- With topology preservation disabled, decimation is more aggressive and allows boundary vertex deletion.

## Main files

- `src/laserprog_studio/geometry_ops/simplify.py`
- `src/laserprog_studio/tooling/ids.py`
- `src/laserprog_studio/tooling/registry.py`
- `src/laserprog_studio/modifiers/registry.py`
- `src/laserprog_studio/ui/layout_panels.py`
- `src/laserprog_studio/ui/tool_panels.py`
- `src/laserprog_studio/controllers/tool_previews.py`
