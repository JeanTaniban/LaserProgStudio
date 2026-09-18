# Pass 180 — Creator UI camera-pan fast path and clean ZIP root

## Issue

The Creator UI runtime had a good left-button camera-pan fast path, but
right/middle camera pans were still converted to `MouseButton.NONE` on mouse
move. That made the native Creator runtime treat the event as a hover move and
run a dense actor hit-test in the Gizmo Catalog on every raw camera-pan event.
The result was visible pan stutter even though actor drag was already fast.

The exported archive also still contained the legacy `LP120/` parent directory.

## Direction

Creator tools do not own camera-navigation performance. The native bridge must
short-circuit any button-down mouse move while no Creator actor is grabbed:

```text
mouse move + any viewport button down + no Creator grab
→ host camera/controller owns the event
→ no Creator hover hit-test
→ no Creator repaint
```

Only a real grabbed Creator actor enters the drag fast path. Normal hover is
allowed only when no mouse button is down.

## Files

- `src/laserprog_studio/application/creator_pointer_interaction.py`
- `tests/test_pass180_creator_camera_pan_fast_path.py`

The delivered ZIP is created from the project root contents directly, so it no
longer adds the useless `LP120/` wrapper directory.
