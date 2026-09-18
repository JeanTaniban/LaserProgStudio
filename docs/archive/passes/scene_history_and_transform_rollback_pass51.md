# Pass51 — Scene history entry point and transform rollback

## Decisions

- The visible history will be a global scene modification history, not a per-part history.
- The right Tool panel stays compact when no tool is active.
- A `History` button now opens a non-modal floating window, following the same UX pattern as tool help.
- The floating window is currently a prepared entry point; the semantic modification history will be connected by the future project/scene model.

## Transform rollback

Pass47/48 tried to improve translation performance by:

- caching translation smart-snap targets;
- moving actors with `actor.SetPosition(...)` during live translation;
- writing real mesh vertices only on mouse release;
- throttling inspector/render updates.

This degraded the user experience: Ctrl+Z missed translations, snapping felt less reliable, and the expected performance gain was not visible enough.

Translation drag now uses the authoritative path again:

- live drag writes real mesh vertices;
- polydata points are updated during the drag;
- smart snap uses the non-cached computation path;
- inspector/render updates happen during the drag, like before;
- the undo snapshot sees the real post-drag geometry.

## Files

- `src/laserprog_studio/controllers/transform_drag.py`
- `src/laserprog_studio/runtime_state.py`
- `src/laserprog_studio/ui/tool_panels.py`
- `src/laserprog_studio/application/preview_controller.py`
- `src/laserprog_studio/application/scene_history_controller.py`
- `src/laserprog_studio/application/__init__.py`

## Notes

The technical undo depth is now 30. The future semantic scene history should remain separate from the technical undo stack: semantic history ignores small transforms; Ctrl+Z tracks all scene changes.
