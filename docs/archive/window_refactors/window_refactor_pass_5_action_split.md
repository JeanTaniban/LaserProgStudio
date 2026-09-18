# Window refactor pass 5 — action controller split

This pass keeps the refactored `window.py`/mixin structure, but removes the largest remaining mixed-responsibility controller.

## What changed

The former `controllers/booleans_clipboard_history.py` mixed four different responsibilities:

- boolean operations;
- clipboard / duplicate / paste;
- project scene edits such as delete/new scene;
- undo/redo history helpers.

It is now only a small compatibility wrapper. New code uses focused mixins directly:

- `controllers/boolean_actions.py`
- `controllers/clipboard_actions.py`
- `controllers/scene_edit_actions.py`
- `controllers/history_actions.py`

`StudioControllersMixin` imports and composes these focused mixins explicitly.

## Why this matters

The previous file name was itself a smell: it described unrelated behaviors. Splitting it makes regressions easier to locate:

- boolean failures now start in `boolean_actions.py`;
- copy/paste/duplicate failures now start in `clipboard_actions.py`;
- undo/redo failures now start in `history_actions.py`;
- delete/new-scene behavior now starts in `scene_edit_actions.py`.

This is still a transitional mixin-based architecture, but the responsibilities are now clearer and easier to migrate later to real controller objects.

## Regression guards

The static verifier now checks that:

- the legacy file stays thin;
- operational methods do not drift back into the legacy wrapper;
- `StudioControllersMixin` uses the focused action mixins;
- clipboard static helper `_bounds_axis_size()` remains a `@staticmethod`.

Additional unit tests were added in `tests/test_action_controller_split_static.py`.
