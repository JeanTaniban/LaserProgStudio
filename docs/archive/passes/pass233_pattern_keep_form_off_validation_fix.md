# Pass 233 — Plan Tracer Pattern Keep forme OFF validation fix

## Bug

When Pattern was applied with **Keep forme OFF**, the preview/resulting face looked valid, but pressing **Apply**, **Add** or **Subtract** could make the motif face disappear and the tool stayed open.

## Cause

The Keep forme OFF path replaced the original selected face by direct `SketchFace` polygons only. These faces were visible immediately, but they were not backed by sketch boundary linework.

The validation paths compile the Plan Tracer sketch before extrusion/subtraction. The sketch compiler is linework-driven, so it cleared the direct faces and could not rebuild them. The operation then saw an empty sketch and aborted before closing the tool.

## Fix

- Material-result faces are now backed by explicit generated point/line contours.
- The old selected face boundary lines and orphan points are removed when Keep forme OFF replaces the contour.
- Generated material boundary vertices are marked hidden so dense motif contours do not flood the viewport with thousands of point handles.
- Hole loops from material-result polygons are added to `suppressed_face_signatures` so the next compile does not recreate the removed openings as filled inner faces.
- The preview face remains visually equivalent after the mandatory compile performed by Apply/Add/Subtract.

## Validation

- `pytest -q tests/test_pass232_plan_tracer_pattern_zero_margin_keep_form.py` → 2 passed
- Pattern/motif focused tests → 58 passed
- `python scripts/quality_gate.py` → OK
