# Engraving role tool update

This update adds a 3D role painter for the engraving export pipeline.

## Roles

The exporter exposes `EngravingRole` and supports three role states:

- `outline`: green material, exported as a black contour.
- `fill`: red material, exported as a black filled area.
- `ignore`: neutral material, visible in preview and ignored by the black/white laser export.

The role is stored as the 3MF material color. No extra sidecar file is required.

## UI

A new `E` tool button opens the Engraving roles panel. Choose a role, then click parts in the 3D view to paint them.

## Parser fix

The engraving exporter now reads `basematerials` by XML local name, not by one strict namespace only. This keeps colors from LaserProg-generated 3MF files readable by the exporter.

## Transform/delete fix

Deleting a selected or dragged part cancels the active gizmo interaction and returns Transform to `N` / None mode.


## Preview behavior

Engraving role changes are now previewed first. Use `Apply` to commit the material color changes or `Cancel` to discard them.
