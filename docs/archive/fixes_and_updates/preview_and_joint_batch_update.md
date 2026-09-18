# Preview and joint batch update

## Preview contract

Primitive creation and engraving role painting now use the same preview workflow as the box, lay-flat, and joint tools.

- The first primitive or role change creates a pending preview.
- Additional changes are applied to the current preview, not directly to the committed model.
- `Apply` commits all pending changes in one operation.
- `Cancel` discards all pending changes and restores the committed model.

## Primitive tool

`Add to preview` appends the new primitive to the current preview mesh list. Multiple primitives can be added before pressing `Apply`.

## Engraving role tool

Clicking a part or using `Preview selected part` / `Set all to outline` now paints a preview copy of the model. The color is still the exported 3MF material signal:

- green: outline contour
- red: fill engraving
- neutral gray: ignored by the black/white laser export

## Joint builder

The joint builder now uses the current mesh list as input. If a preview already exists, the next joint is added on top of that preview instead of restarting from the committed model.

This allows this workflow:

1. Select two parts.
2. Click `Add joint to preview`.
3. Select another pair.
4. Click `Add joint to preview` again.
5. Repeat as needed.
6. Click `Apply` once at the end.

## Transform deletion safety

Deleting a part while a transform interaction is in progress cancels the drag state and returns Transform to `N` / None mode.
