# Native interaction styles

Creator tools can request all official grab/point/line styles through `tool_api.styles`.

```python
from laserprog_studio.tool_api import actors, styles

handle = actors.point(
    "handle.origin",
    (0, 0, 0),
    interaction="grabbable",
    point_style="target",
    line_style="guide",
    visual_state="auto",
)
```

## Point styles

Use `styles.point_style_choices()` to list the stable public choices.

Available ids:

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

## Line styles

Use `styles.line_style_choices()` to list the stable public choices.

Available ids:

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

## Visual states

Use `styles.visual_state_choices()` to expose the available states in an inspector or diagnostic panel.

Available ids:

- `auto`
- `fixed`
- `grabbable`
- `hover`
- `selected`
- `grabbed`
- `disabled`

`auto` is recommended for production tools. It lets the shared interaction layer choose the right state from hover/selection/grab flags.

Runtime feedback is not optional. A forced baseline state such as `visual_state="grabbable"` may define the idle appearance, but actual hover, selected and grabbed flags override it. This is especially important for `minimal`: the idle dot stays tiny/blue, the selected dot is yellow, and the grabbed/dragged dot is orange. Tool code must not keep a selected minimal dot in the idle color.

## Resolve a style manually

Most tools do not need this. Normal tools should request style ids on `actors.*` or official gizmos and let the native renderer resolve them. Render adapters and diagnostics can resolve a full visual recipe:

```python
visual = styles.resolve_actor_visual(
    interaction="grabbable",
    point_style_id="triad",
    line_style_id="guide",
    visual_state="hover",
)
```

The returned object contains:

- resolved point style id;
- resolved line style id;
- visual state;
- point color;
- radius in pixels;
- renderer-neutral line payload.

## Rule

Do not hard-code grab/hover/selected colors in individual tools. Use the shared style ids so the renderer can stay fast and consistent.


## Runtime ownership

Do not compute hover, selected or grabbed colors locally. The native Creator runtime sets the interaction state and the shared renderer resolves the final visual recipe. This keeps tools visually consistent with Tool Core Analysis and prevents slow custom repaint paths.
