# Architecture Migration Pass 7 — BooleanController

## Goal

Pass 7 moves boolean mesh workflows out of the inherited MainWindow mixin layer
and into an explicit application controller.

## Inspection

Before this pass, `controllers/boolean_actions.py` was still a real mixin. It
owned the actual workflows for:

- subtracting the active cutter from touching parts;
- uniting selected parts;
- separating disconnected mesh islands;
- resolving the active cutter index;
- finding touching meshes by bounds;
- showing boolean-operation availability messages.

That made boolean actions harder to reason about for external contributors: the
behavior was reached through `StudioControllersMixin`, but depended on many
implicit MainWindow attributes.

## Changes

A new controller owns the workflows:

```text
src/laserprog_studio/application/boolean_controller.py
```

It exposes:

- `active_boolean_cutter_index()`;
- `blocked_message()`;
- `touching_mesh_indices()`;
- `subtract_touching()`;
- `union_selected()`;
- `separate_selected()`.

`runtime_state.py` now composes it explicitly:

```python
self.boolean_controller = BooleanController.create(self.app_context)
```

## Compatibility facade

`controllers/boolean_actions.py` remains only as a compatibility facade. It keeps
legacy method names used by actions, toolbar buttons and tests, but delegates to
`BooleanController`.

This preserves runtime behavior while continuing the migration from inheritance
to composition.

## Import hygiene

The controller avoids `from .._window_deps import *`. Qt widgets are imported
lazily through `_qmessagebox()` only when a user-facing boolean command needs to
show a message.

This keeps static architecture tests and headless inspection lighter.

## Next step

The next practical migration target is the material/engraving role area, or a
first extraction from `ui/tool_panels.py`. `tool_panels.py` is still one of the
largest files and directly affects how future tools are integrated.
