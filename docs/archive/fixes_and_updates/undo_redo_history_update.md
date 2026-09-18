# Undo / redo history update

This update adds reliable scene history controls.

## Controls

- `Ctrl+Z`: undo the last committed scene action.
- `Ctrl+Y`: redo the last undone scene action.
- `Ctrl+Shift+Z`: alternate redo shortcut.
- `Undo` / `Redo` buttons are available in the top toolbar and the Project panel.

## History depth

The scene keeps at least 10 committed actions in the undo stack.

## Covered actions

Undo / redo now covers immediate scene operations such as:

- live inspector transforms;
- transform gizmo drags;
- duplicate;
- delete;
- boolean subtract / union;
- preview Apply operations from tools;
- new empty scene.

## Preview safety

Undo / redo is disabled while a tool or preview workflow is active. Apply or cancel the tool first, then use history. This avoids mixing tool-local preview state with committed scene history.

## Redo behavior

Any new committed action after an undo clears the redo stack, matching normal editor behavior.
