# LaserProg v95 — Plan Tracer non-destructive New Sketch

## User-visible fixes

- Choosing **New Sketch** on a part that already contains an editable Plan Tracer sketch no longer removes that sketch/history from the support part.
- The clicked part is now treated only as a geometric support for the new independent sketch.
- Applying the new sketch with **Add** creates a separate Plan Tracer volume while the original part remains editable with its original sketch.
- The yellow editable-volume hover preview is hidden immediately after the drawing plane is locked, so it no longer remains over the support part while drawing.

## Subtract compatibility

When **New Sketch** is started on a previously subtracted Plan Tracer part, a later Subtract uses the current visible cut mesh as its base. It does not resurrect the older intact target stored in the previous subtraction history.

## Technical changes

- `_start_new_drawing_from_plan_trace_source()` is now a non-destructive compatibility hook and no longer replaces the source mesh or strips metadata.
- `_PlanTrace2DState.new_sketch_support_object_id` records the independent sketch support.
- `_subtract_targets()` distinguishes a new-sketch support from an explicitly reopened subtraction edit.
- The `plan_trace_2d.editable_hover` projected primitive is hidden and its hover state cleared when the plane is locked.

## Validation

- Existing source metadata is byte-for-byte equivalent after selecting **New Sketch**.
- Add creates a second volume and leaves the original source unchanged.
- The yellow hover primitive becomes invisible after the initial click.
- A new subtraction on an already-cut support uses the current visible mesh.
