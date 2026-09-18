# Pass 257 — Plan Tracer New Sketch preservation and hover cleanup

## Problem

The **New Sketch** branch called `_start_new_drawing_from_plan_trace_source()`, which copied the clicked mesh and removed every Plan Tracer metadata entry before replacing the document object. The visible solid remained, but its editable sketch was destroyed.

The initial editable-volume hover also created a yellow projected mesh (`plan_trace_2d.editable_hover`). The Edit branch hid it, but the New Sketch branch fell through to drawing without hiding it, leaving a persistent yellow outline/fill over the support part.

## Resolution

1. New Sketch no longer mutates the clicked document object.
2. The original editable source remains attached to the support mesh.
3. A support identifier is stored only in the temporary tool state.
4. Add creates a separate new volume because `editing_source_object_id` remains unset.
5. Subtract uses the current visible support mesh instead of a previous subtraction's stored intact mesh.
6. The editable hover projected primitive and state are cleared immediately when a drawing plane is locked.

## Safety and compatibility

- Edit retains its historical replace/resume behavior.
- Draft resume behavior is unchanged.
- Existing subtraction re-edit still uses its stored intact target.
- Only the New Sketch branch changes semantics.
- No scene polling, additional render loop or persistent diagnostics were added.
