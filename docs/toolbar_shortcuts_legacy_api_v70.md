# v70 toolbar, shortcuts, and legacy gizmo API cleanup

## Toolbar defaults

The production toolbar now defaults to this visible order:

1. Box generator
2. Plan tracer 2D
3. Joint builder
4. Texture projection
5. Lay flat
6. Engraving roles
7. Split modifier
8. Boolean Subtract
9. Boolean Union
10. Boolean Separate

The registry version was bumped to `4`, so old packaged toolbar layouts are reset once to this production order. User drag/drop edits made afterwards are persisted normally.

## Drag/drop unavailable buttons

Toolbar buttons remain enabled for pointer input even when the underlying action is unavailable. Availability is stored on `toolbarActionAvailable`; clicking an unavailable button shows a short status message, but dragging still works. This allows disabled modifiers and booleans to be reordered or dropped on the trash.

## Retired product tools

`Tool Core Diagnostic` and `Gizmo catalog` are no longer registered as product tools and are no longer available in the toolbar/palette. Compatibility modules can remain for historical tests and docs, but the Studio registry and product audits no longer expose them.

## Icons

Toolbar icons were redrawn as minimal 128 px symbols with clear silhouettes. Boolean icons are now especially distinct:

- Subtract: block + red cutter + minus.
- Union: overlapping shapes + plus.
- Separate: two blocks with outward arrows.

## Shortcuts

Preferences now contains a `Shortcuts` section.

Defaults:

- Toolbar item selection: `Shift + number`, where `Shift+1` selects the first visible toolbar item and `Shift+0` selects the tenth. AZERTY top-row symbols are accepted (`&=1`, `é=2`, `"=3`, etc.).
- Transform cycle: `Tab` quick taps. One tap = Translate, two taps = Rotate, three taps = Scale. Holding for 0.5 s = Neutral.
- Tool preview/apply: `Left Alt`. Quick press triggers preview when the active tool exposes a preview action. Holding for 0.5 s applies/validates the active tool.

The hold threshold and multi-press window are configurable.

## Legacy gizmo API audit

`scripts/audit_legacy_gizmo_api.py` checks production tooling for direct calls to the retired authoring API:

- `ctx.preview`
- `ctx.gizmos`
- `ctx.actor_registry`
- direct imports from `tool_core.gizmos` / `tool_core.preview`

The public `tool_api` and internal application backends may still use the low-level runtime implementation. Production tools/modifiers/booleans must not call it directly.
