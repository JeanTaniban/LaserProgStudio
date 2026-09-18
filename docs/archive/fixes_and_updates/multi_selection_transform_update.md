# Multi-selection transform update

This update adds Shift-click multi-selection for normal transform workflows.

## Behavior

- Regular click selects one part.
- Shift + click adds or removes a part from the current selection.
- The last selected part is the active part.
- The transform gizmo is centered on the full selection bounds.
- Translation, rotation, and scale apply to every selected part.

## Transform details

- Translation moves all selected parts together.
- Rotation rotates the full selection around the group center.
- Scale resizes the full selection around the group center or the opposite frame edge.
- For multi-part scale, the active part defines the local scale axes.
- The inspector shows group position and group dimensions. Rotation fields remain focused on the active part; editing rotation applies the resulting delta to the whole selection.

## Snapping

Translation snap works with multi-selection. Selected parts are ignored as snap targets, and the moving group bounds are used for grid and smart snap decisions.
