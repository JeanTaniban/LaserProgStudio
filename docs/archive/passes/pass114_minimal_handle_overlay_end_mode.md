# Pass114 — Minimal handle, overlay types and end-only camera sizing

## Goal

Continue the Tool Core GUI/Gizmo layer after Pass113 with production-oriented defaults:

- keep the persistent painter model that avoids flicker;
- make the minimal handle a true single-square marker;
- keep camera-dependent GUI sizing on the end-of-camera-move refresh path;
- add reusable overlay types for future tools.

## Gizmo changes

`DEFAULT_POINT_STYLES["minimal"]` now uses:

- `guide_shape="minimal_square"`;
- `draw_core=False`.

This means the minimal handle is rendered as one square only. It does not draw the normal point/sphere core and it does not add a ring/cross overlay. The square color follows the semantic state:

- fixed;
- grabbable;
- hover;
- grabbed;
- selected;
- disabled.

The persistent painter still updates existing actors and PolyData instead of rebuilding the diagnostic scene.

## Camera GUI sizing

The diagnostic controller now keeps camera sizing in end-only mode.

Continuous live refresh is intentionally disabled for this layer because the end mode proved more stable and avoids unnecessary camera-move updates. Existing hook names are preserved so integration points do not break, but `refresh_camera_size_live_if_enabled()` returns `False`.

## Overlay changes

The overlay core now supports several reusable overlay kinds:

- `palette`;
- `popover`;
- `tooltip`;
- `inspector`;
- `modal`;
- `context_menu`.

New shared manager helpers:

- `show_popover_at_cursor(...)`;
- `show_tooltip(...)`;
- `begin_window_drag(...)`;
- `drag_window(...)`;
- `end_window_drag(...)`.

These APIs let a tool create Blender-style popovers under the mouse without directly instantiating Qt widgets.

## Diagnostic tool

The Tool Core Diagnostic panel adds `Overlay demo`, which creates:

- a movable palette;
- an inspector;
- a cursor popover;
- a tooltip.

The Qt adapter can now move overlay windows and writes the final position back into `OverlayManager`.
