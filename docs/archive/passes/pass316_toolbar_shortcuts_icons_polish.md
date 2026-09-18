# Pass 316 — Toolbar shortcut and icon polish

## User-facing changes

- Unavailable toolbar actions now render as dark charcoal/grey chips instead of near-white chips.  The buttons stay event-enabled so they can still be reordered by drag/drop; action availability is still enforced through the `toolbarActionAvailable` property before execution.
- High-frequency shortcuts are routed through a permanent application event filter so focus widgets in the inspector cannot steal them:
  - `Tab` transform cycle is captured before the inspector moves focus row-by-row.
  - `Shift + number` toolbar selection is captured globally.
  - The preview/apply hold shortcut keeps using the same routing.
- Toolbar numeric shortcuts now use user-facing numbering: `Shift+1` opens the first visible toolbar item, `Shift+2` the second, and `Shift+0` the tenth.
- AZERTY top-row keys are accepted for toolbar shortcuts: `& = 1`, `é = 2`, `" = 3`, `' = 4`, `( = 5`, `- = 6`, `è = 7`, `_ = 8`, `ç = 9`, `à = 0`.
- The texture projection rotation drag filter now reuses the permanent shortcut event filter when present and no longer removes it at drag end.

## Icon refresh

The following toolbar icons were redrawn for clearer intent:

- Plan tracer 2D: visible line/path, rectangle, circle, and polygon sketch shapes.
- Lay flat: cube net / unfolded pattern.
- Split modifier: cuboid cut into two separated halves.
- Box generator: elongated rectangular cuboid instead of a cube.
- Primitives: cube + cylinder + sphere group.
- Vent generator: box/caisse with a visible vent port.

## Validation

- `python -m compileall` passed for the edited shortcut, toolbar, preferences, and texture global filter modules.
- `pytest -q tests/test_pass315_shortcuts_preferences.py` passed.
