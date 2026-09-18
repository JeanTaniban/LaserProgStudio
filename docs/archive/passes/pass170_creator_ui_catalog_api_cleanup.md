# Pass 170 - Creator UI catalog API cleanup

## Goal

The previous Gizmo catalog tool showed useful visual examples, but the public API still had an unclear boundary between optimized UI motifs and diagnostic/demo internals. This pass moves the official vocabulary to the Creator API level.

## Changes

- Added `laserprog_studio.tool_api.ui_catalog` as the public catalog for:
  - actor kinds;
  - actor interactions;
  - visual states;
  - point styles;
  - line styles;
  - manipulators;
  - preview primitives;
  - overlay windows.
- Updated `laserprog_studio.tool_api.gizmos` so catalog helpers come from the public API catalog rather than `tool_core.gizmos.catalog`.
- Updated the Gizmo catalog tool to consume `iter_creator_ui_families()` and to expose toggles for every public UI family.
- Added recommendation recipes that reference only official `tool_api.styles` point/line style ids.
- Exposed overlay specs through `tool_api.visual` so tool code does not need to import overlay specs from `tool_core` directly.

## Contract

New Creator tools should import optimized UI vocabulary from `laserprog_studio.tool_api`, not from diagnostic modules or rendering internals.
