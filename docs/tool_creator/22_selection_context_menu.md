# Selection context menu contract

The viewport now has a selection-scoped context menu. It opens only on a short right click while at least one mesh is selected.

## Gesture contract

- Short right click on an existing selection: open the context menu next to the pointer.
- Right drag: keep camera pan behavior.
- Tiny pointer jitter is tolerated, but a move above the drag threshold cancels the menu candidate and starts pan.

This prevents conflict between camera navigation and context actions.

## Action contract

Context-menu actions live in `application/selection_context_actions.py`. The Qt layer only creates the menu and delegates to that controller. Add future actions there first so they can be tested without synthesizing Qt mouse events.

Current action:

- **Open in new scene**: copies the selected meshes, assigns fresh mesh ids, recenters the copied selection at world origin, creates a new scene, switches to it, and selects the copied meshes.

## Extension rules

- Do not mutate the original scene from a context action unless the action explicitly says so.
- Use fresh mesh ids for copied geometry.
- Keep expensive geometry work out of the mouse event handler; the handler should only decide whether to show the menu.
- Keep right-click drag thresholds strict, otherwise camera pan and menu opening will feel ambiguous.
