# TEX live drag update

This update keeps TEX editing responsive by avoiding a full scene rebuild on every mouse event.

## Changes

- The center handle remains active for `Attach to mesh` and `Decal` placements.
- Rotation/scale drag now updates the active mesh/decal UVs in place.
- Center translation drag updates the stored TEX anchor and recomputes UVs in place.
- Existing VTK actors keep their texture; only the actor `TCoords` are replaced.
- A full preview rebuild is kept as a safety fallback if the fast path cannot resolve the active target.

## Result

Dragging TEX handles should no longer cause repeated texture disappearance/reappearance flashes.
