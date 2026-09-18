# Pass105 — Tool Core UI/Gizmo Showcase

## Goal

Continue the shared `tool_core` foundation with a complete diagnostic UI/gizmo
showcase before migrating real tools. The diagnostic tool now exposes visual
examples in the viewport so future tool rewrites can compare approaches without
using Plan Tracer, Transform or Extrude internals.

## UI/GUI principles applied

- One declarative overlay model for buttons and modes.
- Clear button states: default, hover, selected, disabled.
- Large hit targets for handles and snap points.
- Batched primitives for points and lines instead of one actor per UI element.
- Limited text labels; heavy text clouds must be batched or avoided.
- Position-only updates during drag; no actor churn in the interaction path.
- Full/expensive rebuilds only after an action completes.

## New files

- `src/laserprog_studio/tool_core/diagnostic/showcase.py`
- `src/laserprog_studio/application/tool_core_diag_scene.py`
- `tests/test_pass105_tool_core_ui_showcase.py`

## New diagnostic panel actions

- `UI showcase`
- `Handle states`
- `Primitives`
- `Text labels`
- `Stress`
- `Clear UI`

## Visual examples

The showcase creates:

- large handle state matrix;
- hover/selected/locked/snap/stress handles;
- line and polyline previews;
- circle and arc previews;
- translucent closed face preview;
- text labels for dimensions, constraints and warnings;
- stress handles updated with position-only operations.

## Performance direction

The live PyVista painter keeps actor count low:

- handles are grouped by visual state;
- line/arc/circle previews are drawn as one line batch;
- faces are separate translucent surfaces;
- text is intentionally limited and grouped;
- the diagnostic scene uses a dedicated actor prefix and can be cleared without
  touching the user's real scene.
