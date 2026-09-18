# Pass173 - Creator UI direction clarity

## Problem

The previous passes made the Gizmo catalog consume public motifs, but the architecture was still easy to misunderstand. A developer could still confuse three different things:

- the diagnostic workbench that validates visuals;
- the public API that exposes approved visuals;
- the built-in catalog that displays them.

That confusion previously led to a hand-built catalog scene with generic points instead of the optimized Tool Core Analysis UI motifs.

## Direction

The direction is now explicit:

```text
Tool Core Analysis -> tool_api.ui_catalog / tool_api.ui_motifs -> Gizmo catalog -> Creator tools
```

- Tool Core Analysis remains the laboratory and visual reference.
- `tool_api.ui_catalog` is metadata only: families, descriptions, recipes and documentation.
- `tool_api.ui_motifs` is executable public API: it builds the approved motifs extracted from Tool Core Analysis.
- The Gizmo catalog is only a viewer with visibility toggles.
- Creator tools must use the public API motifs, styles, actors and manipulators instead of inventing local UI.

## Changes

- Added `CreatorUiDirectionLayer` plus `creator_ui_direction_layers()` and `creator_ui_direction_markdown()` to `tool_api.ui_catalog`.
- Re-exported those helpers from `tool_api.gizmos`.
- Added `docs/tool_creator/00_creator_ui_direction.md`.
- Updated the Tool Creator README, overlay/preview/gizmo documentation and Gizmo catalog documentation.
- Added regression tests that check the architecture direction and ensure the catalog remains a viewer rather than a second implementation.
