# Pass113 — Tool Core handle vocabulary and simple overlays

## Purpose

This pass continues the Tool Core layer without migrating production tools yet.
It improves the shared gizmo vocabulary and adds a small declarative overlay
window API so future tools do not implement floating panels by hand.

## Handle changes

- `target` no longer draws the old outer ring. It now keeps only the target
  crosshair around the point.
- Added `minimal`, a dense-sketch handle for Plan tracer vertices and crowded
  edit points.
- Added `translate_arrow`, a cleaner transform-axis style arrow intended for
  translation and extrusion-height handles.
- Existing styles remain available: `solid`, `ring`, `diamond`, `square`,
  `arrow`, `axis`, `chevron`, `triad`.

All styles still use persistent actor updates. Hover/grab state must go through
`GizmoManager.update_interaction_state(...)`; tools should not clear and rebuild
viewport actors to change a handle state.

## Camera-sized guides

Guides continue to be recomputed through the persistent painter. This keeps the
visible size stable while avoiding actor churn. Future production painters should
reuse the same contract: persistent actors, point-only updates during drag, guide
geometry refreshed on camera live/end policy.

## Tool analysis and recommended forms

The new `tool_core.gizmos.catalog` module exposes a lightweight catalog of
recommended handle families by tool:

- Plan tracer: `minimal`, `target`, `ring`, `solid`.
- Translate transform: `translate_arrow`, `axis`, `triad`.
- Rotate transform: `ring`, `target`, `triad`.
- Scale transform: `square`, `diamond`, `axis`.
- Extrude: `translate_arrow`, `target`.
- Split plane: `axis`, `translate_arrow`, `ring`.
- Texture projector: `square`, `ring`, `target`.
- Selection: `solid`, `minimal`, `target`.

The catalog is intentionally data-only. Tools can query it without importing UI
or renderer code.

## Overlay window API

`tool_core.overlay` now contains:

- `OverlayFieldSpec`
- `OverlayWindowSpec`
- `OverlayManager.show_window(...)`
- `OverlayManager.show_message_window(...)`
- `OverlayManager.hide_window(...)`
- `OverlayManager.close_tool_windows(...)`
- `OverlayManager.close_transient_windows(...)`
- `OverlayManager.handle_click_outside(...)`
- `OverlayManager.set_window_position(...)`
- `OverlayManager.update_field(...)`

This prepares simple tool windows such as numeric inspectors, snap popovers,
confirm/cancel panels and hover detail popups without each tool building its own
state system.

## Production rules

1. Tools declare handle style IDs; they do not hand-code hover/grab colors.
2. Tools use `GizmoManager.update_interaction_state` for hover/grab/selection.
3. Tools request overlay windows through `OverlayManager`, not custom ad-hoc
   floating widget state.
4. Tool painters must keep actors persistent and mutate existing geometry.
5. Text overlays remain limited and semantic; do not update many labels on raw
   mouse move.
