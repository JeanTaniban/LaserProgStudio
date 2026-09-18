# Pass 198 - Plan tracer face topology and selectable generated fills

## Scope

This pass continues the Plan tracer sketch kernel work after the point/edge/polyline foundation:

- closed compiled line loops now produce generated sketch faces;
- generated faces are registered as selectable Creator API actors;
- faces are rendered as filled Plan tracer previews;
- deleting a face hides/removes only the generated fill and preserves its boundary points/edges;
- line endpoints now reuse an existing snapped vertex immediately so chained lines can close loops reliably.

## Topology rules added

- A generated face stores a stable geometric signature in metadata.
- `SketchDocument.delete_face_only()` records that signature in `suppressed_face_signatures`.
- The face solver skips suppressed signatures so a deleted fill is not recreated by the next compile.
- Boundary geometry remains editable and can regenerate a new face if the topology changes enough to create a different signature.

## API additions

- `PLAN_TRACE_FACE_ROLE`
- `register_plan_face(...)`
- filled-polygon selection metadata via `filled_polygon_hit`

## Validation

- Full test suite: `754 passed, 3 skipped`.
