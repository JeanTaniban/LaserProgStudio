# Pass131 – Native interaction styles

Pass131 restores the handle/grab/point design catalog as a first-class Creator API surface.

## What changed

- Added `laserprog_studio.tool_api.styles` as the public style catalog.
- Exposed all native point/handle styles:
  - `solid`
  - `ring`
  - `target`
  - `diamond`
  - `square`
  - `arrow`
  - `axis`
  - `chevron`
  - `triad`
  - `minimal`
  - `translate_arrow`
- Added native line styles:
  - `solid`
  - `selectable`
  - `grabbable`
  - `hover`
  - `selected`
  - `grabbed`
  - `fixed`
  - `guide`
  - `construction`
  - `axis`
  - `preview`
  - `warning`
  - `error`
- Added interaction visual states:
  - `auto`
  - `fixed`
  - `grabbable`
  - `hover`
  - `selected`
  - `grabbed`
  - `disabled`
- Actor factories now accept style metadata directly:

```python
actors.point(
    "p1",
    (0, 0, 0),
    interaction="grabbable",
    point_style="triad",
    line_style="guide",
    visual_state="auto",
)
```

## Diagnostic Lab

The Tool Core Diagnostic panel now exposes enum lists for:

- actor kind;
- interaction contract;
- move preset;
- point style;
- line style;
- visual state.

The API benchmark also includes native style resolution so every point/line/state combination is validated through the public API, not through hard-coded diagnostic colors.

## Policy

Creator tools should select semantic styles from `tool_api.styles` and should not hard-code hover/grab/selected colors in their own controllers.

