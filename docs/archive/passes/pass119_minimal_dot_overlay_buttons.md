# Pass119 — minimal dot values and Blender-style popover buttons

## Minimal dot

The Tool Core minimal dot defaults are now fixed to:

- normal: 2 px
- hover/grab/selected: 4 px

The dot remains a real persistent geometry fallback rather than a raw OpenGL point sprite, so the renderer keeps control over color and apparent size.

The diagnostic sliders are retained only as a temporary override/test harness, but the core defaults are now the requested production values.

## Overlay drag stability

The Qt overlay adapter now uses one drag constraint during interactive movement:

- the Qt widget stores the local press offset;
- mouse move computes the new parent position directly;
- the core overlay spec is updated after the widget position is known.

This avoids the old behavior where the toolkit-independent drag offset and live Qt widget geometry could fight each other.

## Blender-style test popover

Middle click in Tool Core Diagnostic opens a non-draggable context popover next to the pointer. It includes dummy Blender-like option buttons and closes when the user clicks back in the viewport.
